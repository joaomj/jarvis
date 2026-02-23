"""Helpers for OpenCode response parsing and logging."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

import httpx


def parse_model_string(model: str) -> dict[str, str]:
    """Parse ``provider/model`` into OpenCode model payload."""
    if "/" in model:
        provider, model_id = model.split("/", 1)
        return {"providerID": provider, "modelID": model_id}
    return {"modelID": model}


def response_text(parts: list[dict[str, Any]]) -> str:
    """Join textual response parts into one string."""
    return "\n".join(part.get("text", "") for part in parts if part.get("type") == "text")


def used_model(info: dict[str, Any]) -> tuple[str, str]:
    """Return ``(model, agent)`` from OpenCode info payload."""
    model_id = info.get("modelID", "")
    provider_id = info.get("providerID", "")
    agent = info.get("agent", "")
    return (f"{provider_id}/{model_id}" if provider_id else model_id), agent


def status_error_preview(error: httpx.HTTPStatusError, max_chars: int = 500) -> str:
    """Best-effort response body preview for HTTP status errors."""
    preview = ""
    with suppress(Exception):
        preview = error.response.text[:max_chars]
    return preview
