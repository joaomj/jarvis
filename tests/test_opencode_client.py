"""Tests for OpenCode HTTP client error handling."""

import httpx
import pytest
import respx

from jarvis.opencode_client import OpenCodeClient, OpenCodeError
from jarvis.opencode_events import parse_sse_event_block


class TestOpenCodeClientErrors:
    """Test suite for OpenCodeClient error handling."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return OpenCodeClient("http://localhost:4096", "test_password")

    @respx.mock
    async def test_health_check_failure(self, client):
        """Test health check returns False with error reason."""
        respx.get("http://localhost:4096/global/health").mock(return_value=httpx.Response(500))

        healthy, reason = await client.health_check()

        assert healthy is False
        assert "HTTP 500" in reason

    @respx.mock
    async def test_create_session_failure(self, client):
        """Test session creation raises OpenCodeError on failure."""
        respx.post("http://localhost:4096/session").mock(
            return_value=httpx.Response(500, text="Server error")
        )

        with pytest.raises(OpenCodeError, match="Failed to create session"):
            await client.create_session("test")

    @respx.mock
    async def test_send_message_failure(self, client):
        """Test send message raises OpenCodeError on failure."""
        respx.post("http://localhost:4096/session/ses-123/message").mock(
            return_value=httpx.Response(500)
        )

        with pytest.raises(OpenCodeError, match="Failed to send message"):
            await client.send_message("ses-123", "Hello")

    @respx.mock
    async def test_send_message_with_agent(self, client):
        """send_message forwards explicit agent in payload."""
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            import json

            captured.update(json.loads(request.content.decode("utf-8")))
            return httpx.Response(
                200,
                json={
                    "message": {
                        "parts": [{"type": "text", "text": "ok"}],
                        "info": {"modelID": "gpt-4o", "providerID": "openai"},
                    }
                },
            )

        respx.post("http://localhost:4096/session/ses-123/message").mock(side_effect=handler)

        await client.send_message("ses-123", "Hello", agent="dr-gate")

        assert captured.get("agent") == "dr-gate"

    @respx.mock
    async def test_send_command_failure(self, client):
        """Test command execution raises OpenCodeError on failure."""
        respx.post("http://localhost:4096/session/ses-123/command").mock(
            return_value=httpx.Response(500)
        )

        with pytest.raises(OpenCodeError, match="Failed to execute command"):
            await client.send_command("ses-123", "undo")

    @respx.mock
    async def test_prompt_async_success(self, client):
        """Test async prompt endpoint accepts request."""
        route = respx.post("http://localhost:4096/session/ses-123/prompt_async").mock(
            return_value=httpx.Response(204)
        )

        await client.prompt_async("ses-123", "Hello")

        assert route.called

    @respx.mock
    async def test_prompt_async_failure(self, client):
        """Test async prompt raises OpenCodeError on failure."""
        respx.post("http://localhost:4096/session/ses-123/prompt_async").mock(
            return_value=httpx.Response(500)
        )

        with pytest.raises(OpenCodeError, match="Failed to send async prompt"):
            await client.prompt_async("ses-123", "Hello")

    @respx.mock
    async def test_question_reply_success(self, client):
        """Test replying to question request."""
        route = respx.post("http://localhost:4096/question/req-123/reply").mock(
            return_value=httpx.Response(200, json=True)
        )

        result = await client.question_reply("req-123", [["A"]])

        assert route.called
        assert result is True

    @respx.mock
    async def test_permission_reply_success(self, client):
        """Test replying to permission request."""
        route = respx.post("http://localhost:4096/permission/perm-123/reply").mock(
            return_value=httpx.Response(200, json=True)
        )

        result = await client.permission_reply("perm-123", "once")

        assert route.called
        assert result is True


class TestOpenCodeEvents:
    """Test SSE event parsing helpers."""

    def test_parse_sse_event_block_valid(self):
        """Valid SSE block parses to dictionary event payload."""
        lines = [
            "event: message.updated",
            'data: {"type":"message.updated","properties":{"id":"msg_1"}}',
        ]

        parsed = parse_sse_event_block(lines)

        assert parsed is not None
        assert parsed["type"] == "message.updated"
        assert parsed["properties"]["id"] == "msg_1"

    def test_parse_sse_event_block_invalid_json_returns_none(self):
        """Invalid SSE JSON payload is ignored."""
        lines = ["event: broken", "data: {not-json"]

        parsed = parse_sse_event_block(lines)

        assert parsed is None

    def test_parse_sse_event_block_missing_data_returns_none(self):
        """SSE block without data lines is ignored."""
        lines = ["event: ping", "id: 1"]

        parsed = parse_sse_event_block(lines)

        assert parsed is None
