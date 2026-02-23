"""HTTP client for OpenCode Server API.

Thin wrapper around httpx for async HTTP communication with OpenCode Server.
Handles authentication, session management, and response parsing.

API Reference: https://opencode.ai/docs/server
"""

from typing import Any

import httpx

from jarvis.exceptions import OpenCodeError
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


def _parse_model_string(model: str) -> dict[str, str]:
    """Parse model string into OpenCode API format.

    Args:
        model: Model in format "provider/model" or just "model".

    Returns:
        dict: {"providerID": "...", "modelID": "..."} or {"modelID": "..."}

    Example:
        >>> _parse_model_string("opencode/glm-5")
        {"providerID": "opencode", "modelID": "glm-5"}
        >>> _parse_model_string("glm-5")
        {"modelID": "glm-5"}
    """
    if "/" in model:
        provider, model_id = model.split("/", 1)
        return {"providerID": provider, "modelID": model_id}
    return {"modelID": model}


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

    def __init__(self, base_url: str, password: str, log_level: str = "INFO"):
        """Initialize client with authentication.

        Args:
            base_url: OpenCode Server URL (e.g., http://opencode:4096).
            password: Server password for basic auth.
            log_level: Logging level for response content (INFO or DEBUG).
        """
        self.base_url = base_url.rstrip("/")
        self.auth = ("opencode", password)
        self.client = httpx.AsyncClient(auth=self.auth, timeout=60.0)
        self._log_level = log_level.upper()
        logger.info(
            "opencode_client_initialized",
            base_url=self.base_url,
            log_level=self._log_level,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
        logger.info("opencode_client_closed")

    async def health_check(self) -> tuple[bool, str]:
        """Check if OpenCode Server is healthy.

        Returns:
            tuple: (healthy: bool, reason: str)
        """
        try:
            response = await self.client.get(f"{self.base_url}/global/health")
            response.raise_for_status()
            data = response.json()
            healthy = data.get("healthy", False)
            version = data.get("version", "unknown")
            reason = f"OK (v{version})" if healthy else f"Server reports unhealthy (v{version})"
            logger.info(
                "health_check_complete",
                healthy=healthy,
                version=version,
            )
            return healthy, reason
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text[:100]}"
            logger.error("health_check_failed", status_code=e.response.status_code, error=str(e))
            return False, error_msg
        except httpx.HTTPError as e:
            error_msg = f"Connection error: {str(e)[:100]}"
            logger.error("health_check_failed", error=str(e))
            return False, error_msg

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

    async def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions.

        Returns:
            list: All sessions from OpenCode.

        Raises:
            OpenCodeError: If listing fails.
        """
        try:
            response = await self.client.get(f"{self.base_url}/session")
            response.raise_for_status()
            sessions = response.json()
            logger.info(
                "sessions_listed",
                count=len(sessions),
            )
            return sessions
        except httpx.HTTPStatusError as e:
            logger.error(
                "sessions_list_failed",
                status_code=e.response.status_code,
            )
            raise OpenCodeError(
                f"Failed to list sessions: {e}",
                status_code=e.response.status_code,
            ) from e
        except httpx.HTTPError as e:
            logger.error("sessions_list_error", error=str(e))
            raise OpenCodeError(f"Failed to list sessions: {e}") from e

    async def send_message(
        self,
        session_id: str,
        text: str,
        model: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Send a regular message to OpenCode.

        Args:
            session_id: OpenCode session ID.
            text: Message text (can include @file references).
            model: Optional model ID in format "provider/model" or "model".

        Returns:
            tuple: (response parts, info dict with model/agent details).

        Raises:
            OpenCodeError: If sending fails.
        """
        payload: dict[str, Any] = {
            "parts": [{"type": "text", "text": text}],
        }
        if model:
            payload["model"] = _parse_model_string(model)

        try:
            response = await self.client.post(
                f"{self.base_url}/session/{session_id}/message",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            parts = data.get("parts", [])
            info = data.get("info", {})

            model_id = info.get("modelID", "")
            provider_id = info.get("providerID", "")
            agent = info.get("agent", "")
            used_model = f"{provider_id}/{model_id}" if provider_id else model_id

            content_text = "\n".join(
                p.get("text", "")
                for p in parts
                if p.get("type") == "text"
            )
            preview = content_text[:200] if content_text else ""

            log_data = {
                "session_id": session_id,
                "response_parts": len(parts),
                "model": used_model,
                "agent": agent,
                "content_preview": preview,
            }
            if self._log_level == "DEBUG":
                log_data["content_full"] = content_text

            logger.info("message_sent", **log_data)
            return parts, info
        except httpx.HTTPStatusError as e:
            # Try to get response body for better error messages
            response_text = ""
            try:
                response_text = e.response.text[:500]  # Limit length
            except Exception:
                pass  # If we can't read the body, continue without it

            error_msg = f"Failed to send message: HTTP {e.response.status_code}"
            if response_text:
                error_msg += f" - {response_text}"

            logger.error(
                "message_send_failed",
                session_id=session_id,
                status_code=e.response.status_code,
                response_preview=response_text[:200] if response_text else None,
            )
            raise OpenCodeError(error_msg, status_code=e.response.status_code) from e
        except httpx.HTTPError as e:
            logger.error("message_send_error", session_id=session_id, error=str(e))
            raise OpenCodeError(f"Failed to send message: {e}") from e

    async def send_command(
        self,
        session_id: str,
        command: str,
        arguments: str = "",
        model: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Execute a slash command in OpenCode.

        Args:
            session_id: OpenCode session ID.
            command: Command name (without /, e.g., "undo", "share").
            arguments: Optional command arguments.
            model: Optional model ID in format "provider/model" or "model".

        Returns:
            tuple: (response parts, info dict with model/agent details).

        Raises:
            OpenCodeError: If command execution fails.
        """
        payload: dict[str, Any] = {
            "command": command,
            "arguments": arguments,
        }
        if model:
            payload["model"] = _parse_model_string(model)

        try:
            response = await self.client.post(
                f"{self.base_url}/session/{session_id}/command",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            parts = data.get("parts", [])
            info = data.get("info", {})

            model_id = info.get("modelID", "")
            provider_id = info.get("providerID", "")
            agent = info.get("agent", "")
            used_model = f"{provider_id}/{model_id}" if provider_id else model_id

            content_text = "\n".join(
                p.get("text", "")
                for p in parts
                if p.get("type") == "text"
            )
            preview = content_text[:200] if content_text else ""

            log_data = {
                "session_id": session_id,
                "command": command,
                "response_parts": len(parts),
                "model": used_model,
                "agent": agent,
                "content_preview": preview,
            }
            if self._log_level == "DEBUG":
                log_data["content_full"] = content_text

            logger.info("command_executed", **log_data)
            return parts, info
        except httpx.HTTPStatusError as e:
            # Try to get response body for better error messages
            response_text = ""
            try:
                response_text = e.response.text[:500]  # Limit length
            except Exception:
                pass  # If we can't read the body, continue without it

            error_msg = f"Failed to execute command: HTTP {e.response.status_code}"
            if response_text:
                error_msg += f" - {response_text}"

            logger.error(
                "command_execution_failed",
                session_id=session_id,
                command=command,
                status_code=e.response.status_code,
                response_preview=response_text[:200] if response_text else None,
            )
            raise OpenCodeError(error_msg, status_code=e.response.status_code) from e
        except httpx.HTTPError as e:
            logger.error(
                "command_execution_error",
                session_id=session_id,
                command=command,
                error=str(e),
            )
            raise OpenCodeError(f"Failed to execute command: {e}") from e
