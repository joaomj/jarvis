"""Utility functions for the bridge."""

import re

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def is_url_only(text: str) -> bool:
    """Check if message contains only a URL."""
    text = text.strip()
    if not text:
        return False
    urls = URL_RE.findall(text)
    return len(urls) == 1 and urls[0] == text


def format_opencode_markdown(text: str) -> str:
    """Format OpenCode markdown for Telegram HTML.

    Converts OpenCode's markdown syntax to Telegram's HTML subset.

    Args:
        text: Raw markdown text from OpenCode

    Returns:
        Formatted HTML text safe for Telegram
    """
    if not text:
        return ""

    # Escape HTML special characters first
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")

    # Convert markdown bold (**text**) to HTML
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)

    # Convert markdown italic (*text* or _text_) to HTML
    text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)
    text = re.sub(r"_(.*?)_", r"<i>\1</i>", text)

    # Convert inline code (`text`) to HTML
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # Convert code blocks (```text```) to HTML
    text = re.sub(
        r"```(\w+)?\n(.*?)```",
        r"<pre><code>\2</code></pre>",
        text,
        flags=re.DOTALL,
    )

    return text


def truncate_text(text: str, max_length: int = 4000) -> str:
    """Truncate text to fit Telegram message limits.

    Args:
        text: Text to truncate
        max_length: Maximum allowed length (default 4000 for safety)

    Returns:
        Truncated text with ellipsis if needed
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - 3] + "..."


def chunk_message(text: str, chunk_size: int = 4000) -> list[str]:
    """Split long message into chunks for Telegram.

    Args:
        text: Long message text
        chunk_size: Size of each chunk

    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    for i in range(0, len(text), chunk_size):
        chunk = text[i : i + chunk_size]
        chunks.append(chunk)

    return chunks
