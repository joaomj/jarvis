"""Contract tests for OpenCode HTTP client against fake server."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from jarvis.opencode_client import OpenCodeClient, OpenCodeError
from jarvis.opencode_events import parse_sse_event_block
from tests.harness.fake_opencode_server import FakeOpenCodeServer, build_opencode_client


@pytest.mark.integration
class TestOpenCodeClientContracts:
    """Contract tests for OpenCodeClient over in-process HTTP transport."""

    @pytest.fixture
    def server(self, fake_opencode_server: FakeOpenCodeServer) -> FakeOpenCodeServer:
        """Provide fake OpenCode ASGI server."""
        return fake_opencode_server

    @pytest.fixture
    async def client(self, server: FakeOpenCodeServer) -> AsyncIterator[OpenCodeClient]:
        """Provide OpenCodeClient bound to fake OpenCode server."""
        client = await build_opencode_client(server)
        try:
            yield client
        finally:
            await client.close()

    async def test_health_check_failure(self) -> None:
        """Health check reports HTTP failures with status information."""
        failing_server = FakeOpenCodeServer()
        failing_server.set_failure("GET", "/global/health", status_code=500, body="down")
        client = await build_opencode_client(failing_server)
        try:
            healthy, reason = await client.health_check()
        finally:
            await client.close()

        assert healthy is False
        assert "HTTP 500" in reason

    async def test_create_session_failure(self) -> None:
        """Create session raises OpenCodeError on status failures."""
        failing_server = FakeOpenCodeServer()
        failing_server.set_failure("POST", "/session", status_code=500, body="Server error")
        client = await build_opencode_client(failing_server)
        try:
            with pytest.raises(OpenCodeError, match="Failed to create session"):
                await client.create_session("test")
        finally:
            await client.close()

    async def test_send_message_payload_includes_agent_and_model(
        self,
        client: OpenCodeClient,
        server: FakeOpenCodeServer,
    ) -> None:
        """send_message forwards explicit agent and parsed model payload."""
        await client.send_message(
            session_id="ses-123",
            text="Hello",
            model="openai/gpt-4o",
            agent="dr-gate",
        )

        payload = server.message_payloads["ses-123"][0]
        assert payload["agent"] == "dr-gate"
        assert payload["model"] == {"providerID": "openai", "modelID": "gpt-4o"}

    async def test_prompt_async_posts_payload_to_async_endpoint(
        self,
        client: OpenCodeClient,
        server: FakeOpenCodeServer,
    ) -> None:
        """prompt_async posts request body and handles 204 responses."""
        await client.prompt_async(
            session_id="ses-async",
            text="Hello async",
            model="openai/gpt-4o-mini",
            agent="dr-planner",
        )

        payload = server.prompt_payloads["ses-async"][0]
        assert payload["agent"] == "dr-planner"
        assert payload["model"] == {"providerID": "openai", "modelID": "gpt-4o-mini"}

    async def test_stream_events_parses_partial_chunks_and_multiple_blocks(
        self,
        client: OpenCodeClient,
        server: FakeOpenCodeServer,
    ) -> None:
        """SSE parser handles chunk boundaries across multiple event blocks."""
        server.queue_sse_chunks(
            [
                'event: message.updated\ndata: {"type":"message.updated",',
                '"properties":{"id":"m1"}}\n\n',
                (
                    "event: permission.asked\n"
                    'data: {"type":"permission.asked","properties":{"id":"perm-1"}}\n\n'
                ),
            ]
        )

        events = [event async for event in client.stream_events()]

        assert [event["type"] for event in events] == ["message.updated", "permission.asked"]
        assert events[0]["properties"]["id"] == "m1"
        assert events[1]["properties"]["id"] == "perm-1"

    async def test_http_error_includes_response_preview(
        self,
        client: OpenCodeClient,
        server: FakeOpenCodeServer,
    ) -> None:
        """HTTP status errors include body preview in raised message."""
        server.set_failure(
            "POST",
            "/session/ses-500/prompt_async",
            status_code=500,
            body="upstream timeout while writing stream",
        )

        with pytest.raises(OpenCodeError, match="upstream timeout while writing stream"):
            await client.prompt_async("ses-500", "hello")

    async def test_question_and_permission_replies_post_boolean_payloads(
        self,
        client: OpenCodeClient,
        server: FakeOpenCodeServer,
    ) -> None:
        """question_reply and permission_reply hit expected endpoints."""
        question_ok = await client.question_reply("req-1", [["A"]])
        permission_ok = await client.permission_reply("perm-1", "once")

        assert question_ok is True
        assert permission_ok is True
        assert server.question_replies["req-1"][0]["answers"] == [["A"]]
        assert server.permission_replies["perm-1"][0]["reply"] == "once"


@pytest.mark.fast
class TestOpenCodeEvents:
    """Test SSE event parsing helpers."""

    def test_parse_sse_event_block_valid(self) -> None:
        """Valid SSE block parses to dictionary event payload."""
        lines = [
            "event: message.updated",
            'data: {"type":"message.updated","properties":{"id":"msg_1"}}',
        ]

        parsed = parse_sse_event_block(lines)

        assert parsed is not None
        assert parsed["type"] == "message.updated"
        assert parsed["properties"]["id"] == "msg_1"

    def test_parse_sse_event_block_invalid_json_returns_none(self) -> None:
        """Invalid SSE JSON payload is ignored."""
        lines = ["event: broken", "data: {not-json"]

        parsed = parse_sse_event_block(lines)

        assert parsed is None

    def test_parse_sse_event_block_missing_data_returns_none(self) -> None:
        """SSE block without data lines is ignored."""
        lines = ["event: ping", "id: 1"]

        parsed = parse_sse_event_block(lines)

        assert parsed is None
