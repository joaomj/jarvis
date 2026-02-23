"""Tests for OpenCode HTTP client error handling."""

import httpx
import pytest
import respx

from jarvis.opencode_client import OpenCodeClient, OpenCodeError


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
    async def test_send_command_failure(self, client):
        """Test command execution raises OpenCodeError on failure."""
        respx.post("http://localhost:4096/session/ses-123/command").mock(
            return_value=httpx.Response(500)
        )

        with pytest.raises(OpenCodeError, match="Failed to execute command"):
            await client.send_command("ses-123", "undo")
