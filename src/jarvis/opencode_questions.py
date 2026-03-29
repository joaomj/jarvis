"""OpenCode question and permission handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jarvis.opencode_request_helpers import post_boolean


@dataclass
class PermissionParams:
    """Parameters for permission reply."""

    message: str | None = None
    directory: str | None = None


async def question_reply(
    client,
    base_url: str,
    request_id: str,
    answers: list[list[str]],
    directory: str | None = None,
) -> bool:
    params = {"directory": directory} if directory else None
    payload = {"answers": answers}
    return await post_boolean(
        client=client,
        base_url=base_url,
        endpoint=f"/question/{request_id}/reply",
        payload=payload,
        params=params,
        error_prefix="Failed to reply to question",
    )


async def question_reject(
    client,
    base_url: str,
    request_id: str,
    directory: str | None = None,
) -> bool:
    params = {"directory": directory} if directory else None
    return await post_boolean(
        client=client,
        base_url=base_url,
        endpoint=f"/question/{request_id}/reject",
        payload={},
        params=params,
        error_prefix="Failed to reject question",
    )


async def permission_reply(
    client,
    base_url: str,
    request_id: str,
    reply: str,
    params: PermissionParams | None = None,
) -> bool:
    query_params = {"directory": params.directory} if params and params.directory else None
    payload: dict[str, Any] = {"reply": reply}
    if params and params.message:
        payload["message"] = params.message
    return await post_boolean(
        client=client,
        base_url=base_url,
        endpoint=f"/permission/{request_id}/reply",
        payload=payload,
        params=query_params,
        error_prefix="Failed to reply to permission request",
    )
