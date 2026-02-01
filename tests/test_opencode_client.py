"""Tests for OpenCode HTTP client."""

import httpx
import pytest
import respx

from jarvis.opencode_client import OpenCodeClient, OpenCodeError


class TestOpenCodeClient:
    """Test suite for OpenCodeClient."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return OpenCodeClient("http://localhost:4096", "test_password")

    @respx.mock
    async def test_health_check_success(self, client):
        """Test health check returns True when server is healthy."""
        route = respx.get("http://localhost:4096/global/health").mock(
            return_value=httpx.Response(200, json={"healthy": True, "version": "1.0.0"})
        )

        result = await client.health_check()

        assert result is True
        assert route.called

    @respx.mock
    async def test_health_check_failure(self, client):
        """Test health check returns False on error."""
        respx.get("http://localhost:4096/global/health").mock(
            return_value=httpx.Response(500)
        )

        result = await client.health_check()

        assert result is False

    @respx.mock
    async def test_create_session_success(self, client):
        """Test session creation returns session ID."""
        route = respx.post("http://localhost:4096/session").mock(
            return_value=httpx.Response(200, json={"id": "ses-123", "title": "test"})
        )

        session_id = await client.create_session("test-session")

        assert session_id == "ses-123"
        assert route.called
        # Verify request body (JSON has no spaces)
        request = route.calls[0].request
        assert b'"title":"test-session"' in request.content

    @respx.mock
    async def test_create_session_failure(self, client):
        """Test session creation raises OpenCodeError on failure."""
        respx.post("http://localhost:4096/session").mock(
            return_value=httpx.Response(500, text="Server error")
        )

        with pytest.raises(OpenCodeError, match="Failed to create session"):
            await client.create_session("test")

    @respx.mock
    async def test_send_message_success(self, client):
        """Test sending message returns response parts."""
        route = respx.post("http://localhost:4096/session/ses-123/message").mock(
            return_value=httpx.Response(
                200,
                json={
                    "info": {"id": "msg-456"},
                    "parts": [{"type": "text", "text": "Hello back"}],
                }
            )
        )

        parts = await client.send_message("ses-123", "Hello")

        assert len(parts) == 1
        assert parts[0]["text"] == "Hello back"
        assert route.called

    @respx.mock
    async def test_send_message_failure(self, client):
        """Test send message raises OpenCodeError on failure."""
        respx.post("http://localhost:4096/session/ses-123/message").mock(
            return_value=httpx.Response(500)
        )

        with pytest.raises(OpenCodeError, match="Failed to send message"):
            await client.send_message("ses-123", "Hello")

    @respx.mock
    async def test_send_command_success(self, client):
        """Test executing command returns response parts."""
        route = respx.post("http://localhost:4096/session/ses-123/command").mock(
            return_value=httpx.Response(
                200,
                json={
                    "info": {"id": "msg-789"},
                    "parts": [{"type": "text", "text": "Changes reverted"}],
                }
            )
        )

        parts = await client.send_command("ses-123", "undo")

        assert len(parts) == 1
        assert parts[0]["text"] == "Changes reverted"
        assert route.called
        # Verify request body (JSON has no spaces)
        request = route.calls[0].request
        assert b'"command":"undo"' in request.content

    @respx.mock
    async def test_send_command_with_arguments(self, client):
        """Test command execution with arguments."""
        route = respx.post("http://localhost:4096/session/ses-123/command").mock(
            return_value=httpx.Response(200, json={"parts": []})
        )

        await client.send_command("ses-123", "share", "--public")

        request = route.calls[0].request
        assert b'"command":"share"' in request.content
        assert b'"arguments":"--public"' in request.content

    @respx.mock
    async def test_send_command_failure(self, client):
        """Test command execution raises OpenCodeError on failure."""
        respx.post("http://localhost:4096/session/ses-123/command").mock(
            return_value=httpx.Response(500)
        )

        with pytest.raises(OpenCodeError, match="Failed to execute command"):
            await client.send_command("ses-123", "undo")

    async def test_client_uses_basic_auth(self):
        """Test client uses basic auth with correct credentials."""
        client = OpenCodeClient("http://localhost:4096", "test_password")

        # Check auth is configured
        assert client.auth == ("opencode", "test_password")
        assert client.client.auth == ("opencode", "test_password")
