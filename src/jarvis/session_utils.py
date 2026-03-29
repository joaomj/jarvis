"""Session-related utility functions."""

from __future__ import annotations

import re
from typing import Any


def extract_session_id_from_new_response(response_parts: list[dict[str, Any]]) -> str | None:
    """Extract new session ID from /new command response.

    Args:
        response_parts: Response parts from OpenCode send_command

    Returns:
        New session ID if found, None otherwise
    """
    for part in response_parts:
        if part.get("type") == "text":
            text = part.get("text", "")
            # Look for session ID pattern in response
            # Typical format: "Created new session: <session_id>" or just the ID
            # Match common session ID patterns (UUID-like or hash strings)
            match = re.search(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", text)
            if match:
                return match.group(0)
            # Also try to find any long alphanumeric string that could be a session ID
            match = re.search(r"\b([a-f0-9]{24,32})\b", text)
            if match:
                return match.group(1)
    return None
