"""Shared request helpers for OpenCode client."""

from __future__ import annotations

from typing import Any

import httpx

from jarvis.exceptions import OpenCodeError
from jarvis.opencode_response import response_text, status_error_preview, used_model


async def post_boolean(  # noqa: PLR0913
    *,
    client: httpx.AsyncClient,
    base_url: str,
    endpoint: str,
    payload: dict[str, Any],
    params: dict[str, str] | None,
    error_prefix: str,
) -> bool:
    """Post payload to endpoint and return boolean response."""
    try:
        response = await client.post(f"{base_url}{endpoint}", params=params, json=payload)
        response.raise_for_status()
        return bool(response.json())
    except httpx.HTTPStatusError as error:
        preview = status_error_preview(error)
        msg = f"{error_prefix}: HTTP {error.response.status_code}"
        if preview:
            msg = f"{msg} - {preview}"
        raise OpenCodeError(msg, status_code=error.response.status_code) from error
    except httpx.HTTPError as error:
        raise OpenCodeError(f"{error_prefix}: {error}") from error


async def send_with_payload(  # noqa: PLR0913
    *,
    client: httpx.AsyncClient,
    base_url: str,
    payload: dict[str, Any],
    endpoint: str,
    event_name: str,
    error_name: str,
    base_error: str,
    session_id: str,
    command: str | None,
    log_level: str,
    logger: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Send payload and normalize logging/error behavior."""
    try:
        response = await client.post(f"{base_url}{endpoint}", json=payload)
        response.raise_for_status()
        data = response.json()
        parts = data.get("parts", [])
        info = data.get("info", {})
        _log_success(
            event_name=event_name,
            session_id=session_id,
            parts=parts,
            info=info,
            command=command,
            log_level=log_level,
            logger=logger,
        )
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


def _log_success(  # noqa: PLR0913
    *,
    event_name: str,
    session_id: str,
    parts: list[dict[str, Any]],
    info: dict[str, Any],
    command: str | None,
    log_level: str,
    logger: Any,
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
    if log_level == "DEBUG":
        log_data["content_full"] = content
    logger.info(event_name, **log_data)
