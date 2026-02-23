"""Helpers for parsing OpenCode server-sent events."""

from __future__ import annotations

import json
from typing import Any


def parse_sse_event_block(lines: list[str]) -> dict[str, Any] | None:
    """Parse one SSE event block into a JSON object.

    Args:
        lines: Raw lines for one SSE block, excluding the trailing blank line.

    Returns:
        Parsed JSON dictionary when present and valid, otherwise ``None``.
    """
    if not lines:
        return None

    data_lines = [line[5:].lstrip() for line in lines if line.startswith("data:")]
    if not data_lines:
        return None

    payload = "\n".join(data_lines).strip()
    if not payload:
        return None

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None
