"""HTTP client for OpenCode Server API.

Thin wrapper around httpx for async HTTP communication with OpenCode Server.
Handles authentication, session management, and response parsing.

API Reference: https://opencode.ai/docs/server
"""

from typing import Any

import httpx
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class OpenCodeError(Exception):
    """Base exception for OpenCode API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class OpenCodeClient:
    """Async HTTP client for OpenCode Server API.

    Responsibilities:
    - Health checks
    - Session creation and management
    - Message/command sending
    - Response parsing

    Example:
        >>> client = OpenCodeClient("http://opencode:4096", "password")
        >>> await client.health_check()
        True
        >>> session_id = await client.create_session("user-123")
        >>> response = await client.send_message(session_id, "Hello")
    """

    def __init__(self, base_url: str, password: str):
        """Initialize client with authentication.

        Args:
            base_url: OpenCode Server URL (e.g., http://opencode:4096).
            password: Server password for basic auth.
        """
        self.base_url = base_url.rstrip("/")
        self.auth = ("opencode", password)
        self.client = httpx.AsyncClient(auth=self.auth, timeout=60.0)
        logger.info(
            "opencode_client_initialized",
            base_url=self.base_url,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
        logger.info("opencode_client_closed")

    async def health_check(self) -> bool:
        """Check if OpenCode Server is healthy.

        Returns:
            bool: True if healthy, False otherwise.
        """
        try:
            response = await self.client.get(f"{self.base_url}/global/health")
            response.raise_for_status()
            data = response.json()
            healthy = data.get("healthy", False)
            logger.info(
                "health_check_complete",
                healthy=healthy,
                version=data.get("version", "unknown"),
            )
            return healthy
        except httpx.HTTPError as e:
            logger.error("health_check_failed", error=str(e))
            return False

    async def create_session(self, title: str) -> str:
        """Create a new session.

        Args:
            title: Session title (e.g., "jarvis-user-{user_id}").

        Returns:
            str: Session ID.

        Raises:
            OpenCodeError: If creation fails.
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/session",
                json={"title": title},
            )
            response.raise_for_status()
            data = response.json()
            session_id = data["id"]
            logger.info(
                "session_created",
                session_id=session_id,
                title=title,
            )
            return session_id
        except httpx.HTTPStatusError as e:
            logger.error(
                "session_creation_failed",
                status_code=e.response.status_code,
                error=str(e),
            )
            raise OpenCodeError(
                f"Failed to create session: {e}",
                status_code=e.response.status_code,
            ) from e
        except (KeyError, httpx.HTTPError) as e:
            logger.error("session_creation_error", error=str(e))
            raise OpenCodeError(f"Failed to create session: {e}") from e

    async def send_message(
        self,
        session_id: str,
        text: str,
    ) -> list[dict[str, Any]]:
        """Send a regular message to OpenCode.

        Args:
            session_id: OpenCode session ID.
            text: Message text (can include @file references).

        Returns:
            list: Response parts from OpenCode.

        Raises:
            OpenCodeError: If sending fails.
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/session/{session_id}/message",
                json={
                    "parts": [{"type": "text", "text": text}],
                },
            )
            response.raise_for_status()
            data = response.json()
            parts = data.get("parts", [])
            logger.info(
                "message_sent",
                session_id=session_id,
                response_parts=len(parts),
            )
            return parts
        except httpx.HTTPStatusError as e:
            logger.error(
                "message_send_failed",
                session_id=session_id,
                status_code=e.response.status_code,
            )
            raise OpenCodeError(
                f"Failed to send message: {e}",
                status_code=e.response.status_code,
            ) from e
        except httpx.HTTPError as e:
            logger.error("message_send_error", session_id=session_id, error=str(e))
            raise OpenCodeError(f"Failed to send message: {e}") from e

    async def send_command(
        self,
        session_id: str,
        command: str,
        arguments: str = "",
    ) -> list[dict[str, Any]]:
        """Execute a slash command in OpenCode.

        Args:
            session_id: OpenCode session ID.
            command: Command name (without /, e.g., "undo", "share").
            arguments: Optional command arguments.

        Returns:
            list: Response parts from OpenCode.

        Raises:
            OpenCodeError: If command execution fails.
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/session/{session_id}/command",
                json={
                    "command": command,
                    "arguments": arguments,
                },
            )
            response.raise_for_status()
            data = response.json()
            parts = data.get("parts", [])
            logger.info(
                "command_executed",
                session_id=session_id,
                command=command,
                response_parts=len(parts),
            )
            return parts
        except httpx.HTTPStatusError as e:
            logger.error(
                "command_execution_failed",
                session_id=session_id,
                command=command,
                status_code=e.response.status_code,
            )
            raise OpenCodeError(
                f"Failed to execute command: {e}",
                status_code=e.response.status_code,
            ) from e
        except httpx.HTTPError as e:
            logger.error(
                "command_execution_error",
                session_id=session_id,
                command=command,
                error=str(e),
            )
            raise OpenCodeError(f"Failed to execute command: {e}") from e
