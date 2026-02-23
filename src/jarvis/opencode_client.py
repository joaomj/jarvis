"""HTTP client for OpenCode Server API."""

from __future__ import annotations

from typing import Any

import httpx

from jarvis.exceptions import OpenCodeError
from jarvis.logging_config import get_logger
from jarvis.opencode_response import (
    parse_model_string,
    response_text,
    status_error_preview,
    used_model,
)

logger = get_logger(__name__)


class OpenCodeClient:
    """Async HTTP client for OpenCode Server API."""

    def __init__(self, base_url: str, password: str, log_level: str = "INFO") -> None:
        self.base_url = base_url.rstrip("/")
        self.auth = ("opencode", password)
        self.client = httpx.AsyncClient(auth=self.auth, timeout=60.0)
        self._log_level = log_level.upper()
        logger.info(
            "opencode_client_initialized", base_url=self.base_url, log_level=self._log_level
        )

    async def close(self) -> None:
        """Close HTTP client resources."""
        await self.client.aclose()
        logger.info("opencode_client_closed")

    async def health_check(self) -> tuple[bool, str]:
        """Check if OpenCode Server is healthy."""
        try:
            response = await self.client.get(f"{self.base_url}/global/health")
            response.raise_for_status()
            data = response.json()
            healthy = data.get("healthy", False)
            version = data.get("version", "unknown")
            reason = f"OK (v{version})" if healthy else f"Server reports unhealthy (v{version})"
            logger.info("health_check_complete", healthy=healthy, version=version)
            return healthy, reason
        except httpx.HTTPStatusError as error:
            error_msg = f"HTTP {error.response.status_code}: {error.response.text[:100]}"
            logger.error(
                "health_check_failed", status_code=error.response.status_code, error=str(error)
            )
            return False, error_msg
        except httpx.HTTPError as error:
            error_msg = f"Connection error: {str(error)[:100]}"
            logger.error("health_check_failed", error=str(error))
            return False, error_msg

    async def create_session(self, title: str) -> str:
        """Create a new OpenCode session."""
        try:
            response = await self.client.post(f"{self.base_url}/session", json={"title": title})
            response.raise_for_status()
            session_id = response.json()["id"]
            logger.info("session_created", session_id=session_id, title=title)
            return session_id
        except httpx.HTTPStatusError as error:
            logger.error(
                "session_creation_failed",
                status_code=error.response.status_code,
                error=str(error),
            )
            raise OpenCodeError(
                f"Failed to create session: {error}",
                status_code=error.response.status_code,
            ) from error
        except (KeyError, httpx.HTTPError) as error:
            logger.error("session_creation_error", error=str(error))
            raise OpenCodeError(f"Failed to create session: {error}") from error

    async def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions from OpenCode."""
        try:
            response = await self.client.get(f"{self.base_url}/session")
            response.raise_for_status()
            sessions = response.json()
            logger.info("sessions_listed", count=len(sessions))
            return sessions
        except httpx.HTTPStatusError as error:
            logger.error("sessions_list_failed", status_code=error.response.status_code)
            raise OpenCodeError(
                f"Failed to list sessions: {error}",
                status_code=error.response.status_code,
            ) from error
        except httpx.HTTPError as error:
            logger.error("sessions_list_error", error=str(error))
            raise OpenCodeError(f"Failed to list sessions: {error}") from error

    async def send_message(
        self,
        session_id: str,
        text: str,
        model: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Send a regular message to OpenCode."""
        payload: dict[str, Any] = {"parts": [{"type": "text", "text": text}]}
        if model:
            payload["model"] = parse_model_string(model)

        return await self._send_with_payload(
            endpoint=f"/session/{session_id}/message",
            payload=payload,
            event_name="message_sent",
            error_name="message_send_failed",
            base_error="Failed to send message",
            session_id=session_id,
        )

    async def send_command(
        self,
        session_id: str,
        command: str,
        arguments: str = "",
        model: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Execute a slash command in OpenCode."""
        payload: dict[str, Any] = {"command": command, "arguments": arguments}
        if model:
            payload["model"] = parse_model_string(model)

        return await self._send_with_payload(
            endpoint=f"/session/{session_id}/command",
            payload=payload,
            event_name="command_executed",
            error_name="command_execution_failed",
            base_error="Failed to execute command",
            session_id=session_id,
            command=command,
        )

    async def _send_with_payload(  # noqa: PLR0913
        self,
        endpoint: str,
        payload: dict[str, Any],
        event_name: str,
        error_name: str,
        base_error: str,
        session_id: str,
        command: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Send payload to OpenCode and normalize logging/error behavior."""
        try:
            response = await self.client.post(f"{self.base_url}{endpoint}", json=payload)
            response.raise_for_status()
            data = response.json()
            parts = data.get("parts", [])
            info = data.get("info", {})
            self._log_success(event_name, session_id, parts, info, command=command)
            return parts, info
        except httpx.HTTPStatusError as error:
            preview = status_error_preview(error)
            error_msg = f"{base_error}: HTTP {error.response.status_code}"
            if preview:
                error_msg = f"{error_msg} - {preview}"

            log_data: dict[str, Any] = {
                "session_id": session_id,
                "status_code": error.response.status_code,
                "response_preview": preview[:200] if preview else None,
            }
            if command is not None:
                log_data["command"] = command

            logger.error(error_name, **log_data)
            raise OpenCodeError(error_msg, status_code=error.response.status_code) from error
        except httpx.HTTPError as error:
            log_data = {"session_id": session_id, "error": str(error)}
            if command is not None:
                log_data["command"] = command
                logger.error("command_execution_error", **log_data)
                raise OpenCodeError(f"Failed to execute command: {error}") from error

            logger.error("message_send_error", **log_data)
            raise OpenCodeError(f"Failed to send message: {error}") from error

    def _log_success(
        self,
        event_name: str,
        session_id: str,
        parts: list[dict[str, Any]],
        info: dict[str, Any],
        command: str | None = None,
    ) -> None:
        """Log successful OpenCode responses."""
        content = response_text(parts)
        model_name, agent = used_model(info)
        log_data: dict[str, Any] = {
            "session_id": session_id,
            "response_parts": len(parts),
            "model": model_name,
            "agent": agent,
            "content_preview": content[:200] if content else "",
        }
        if command is not None:
            log_data["command"] = command
        if self._log_level == "DEBUG":
            log_data["content_full"] = content
        logger.info(event_name, **log_data)
