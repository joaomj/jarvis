"""HTTP client for OpenCode Server API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from jarvis.exceptions import OpenCodeError
from jarvis.logging_config import get_logger
from jarvis.opencode_events import parse_sse_event_block
from jarvis.opencode_questions import (
    PermissionParams,
    permission_reply,
    question_reject,
    question_reply,
)
from jarvis.opencode_request_helpers import send_with_payload
from jarvis.opencode_response import parse_model_string, status_error_preview

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

    async def get_session_messages(self, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent messages for a session."""
        try:
            response = await self.client.get(
                f"{self.base_url}/session/{session_id}/message",
                params={"limit": limit},
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except httpx.HTTPStatusError as error:
            logger.error(
                "session_messages_failed",
                session_id=session_id,
                status_code=error.response.status_code,
            )
            raise OpenCodeError(
                f"Failed to fetch session messages: HTTP {error.response.status_code}",
                status_code=error.response.status_code,
            ) from error
        except httpx.HTTPError as error:
            logger.error("session_messages_error", session_id=session_id, error=str(error))
            raise OpenCodeError(f"Failed to fetch session messages: {error}") from error

    async def send_message(
        self,
        session_id: str,
        text: str,
        model: str | None = None,
        agent: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Send a regular message to OpenCode."""
        payload: dict[str, Any] = {"parts": [{"type": "text", "text": text}]}
        if model:
            payload["model"] = parse_model_string(model)
        if agent:
            payload["agent"] = agent

        return await send_with_payload(
            client=self.client,
            base_url=self.base_url,
            endpoint=f"/session/{session_id}/message",
            payload=payload,
            event_name="message_sent",
            error_name="message_send_failed",
            base_error="Failed to send message",
            session_id=session_id,
            command=None,
            log_level=self._log_level,
            logger=logger,
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

        return await send_with_payload(
            client=self.client,
            base_url=self.base_url,
            endpoint=f"/session/{session_id}/command",
            payload=payload,
            event_name="command_executed",
            error_name="command_execution_failed",
            base_error="Failed to execute command",
            session_id=session_id,
            command=command,
            log_level=self._log_level,
            logger=logger,
        )

    async def prompt_async(
        self,
        session_id: str,
        text: str,
        model: str | None = None,
        agent: str | None = None,
        system: str | None = None,
    ) -> None:
        """Send message asynchronously without waiting for final response."""
        payload: dict[str, Any] = {"parts": [{"type": "text", "text": text}]}
        if model:
            payload["model"] = parse_model_string(model)
        if agent:
            payload["agent"] = agent
        if system:
            payload["system"] = system

        try:
            response = await self.client.post(
                f"{self.base_url}/session/{session_id}/prompt_async",
                json=payload,
            )
            response.raise_for_status()
            logger.info("prompt_async_sent", session_id=session_id, agent=agent)
        except httpx.HTTPStatusError as error:
            preview = status_error_preview(error)
            error_msg = f"Failed to send async prompt: HTTP {error.response.status_code}"
            if preview:
                error_msg = f"{error_msg} - {preview}"
            logger.error(
                "prompt_async_failed",
                session_id=session_id,
                status_code=error.response.status_code,
                response_preview=preview[:200] if preview else None,
            )
            raise OpenCodeError(error_msg, status_code=error.response.status_code) from error
        except httpx.HTTPError as error:
            logger.error("prompt_async_error", session_id=session_id, error=str(error))
            raise OpenCodeError(f"Failed to send async prompt: {error}") from error

    async def stream_events(self, directory: str | None = None) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to OpenCode SSE event stream and yield parsed events."""
        params = {"directory": directory} if directory else None

        try:
            async with self.client.stream(
                "GET",
                f"{self.base_url}/event",
                params=params,
                headers={"Accept": "text/event-stream"},
            ) as response:
                response.raise_for_status()
                block: list[str] = []
                async for line in response.aiter_lines():
                    if line == "":
                        event = parse_sse_event_block(block)
                        if event is not None:
                            yield event
                        block.clear()
                        continue
                    if not line.startswith(":"):
                        block.append(line)

                if block:
                    event = parse_sse_event_block(block)
                    if event is not None:
                        yield event
        except httpx.HTTPStatusError as error:
            preview = status_error_preview(error)
            logger.error(
                "events_stream_failed",
                status_code=error.response.status_code,
                response_preview=preview[:200] if preview else None,
                directory=directory,
            )
            error_msg = f"Failed to subscribe to events: HTTP {error.response.status_code}"
            raise OpenCodeError(error_msg, status_code=error.response.status_code) from error
        except httpx.HTTPError as error:
            logger.error("events_stream_error", error=str(error), directory=directory)
            raise OpenCodeError(f"Failed to subscribe to events: {error}") from error

    async def question_reply(
        self,
        request_id: str,
        answers: list[list[str]],
        directory: str | None = None,
    ) -> bool:
        return await question_reply(
            client=self.client,
            base_url=self.base_url,
            request_id=request_id,
            answers=answers,
            directory=directory,
        )

    async def list_commands(self) -> list[dict[str, Any]]:
        try:
            response = await self.client.get(f"{self.base_url}/command")
            response.raise_for_status()
            commands = response.json()
            logger.info("commands_listed", count=len(commands))
            return commands if isinstance(commands, list) else []
        except httpx.HTTPStatusError as error:
            logger.error("commands_list_failed", status_code=error.response.status_code)
            raise OpenCodeError(
                f"Failed to list commands: {error}", status_code=error.response.status_code
            ) from error
        except httpx.HTTPError as error:
            logger.error("commands_list_error", error=str(error))
            raise OpenCodeError(f"Failed to list commands: {error}") from error

    async def question_reject(self, request_id: str, directory: str | None = None) -> bool:
        return await question_reject(self.client, self.base_url, request_id, directory)

    async def permission_reply(
        self, request_id: str, reply: str, message: str | None = None, directory: str | None = None
    ) -> bool:
        params = PermissionParams(message=message, directory=directory)
        return await permission_reply(self.client, self.base_url, request_id, reply, params)
