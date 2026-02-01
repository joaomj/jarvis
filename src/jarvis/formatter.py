"""Response formatting for Telegram messages.

Handles:
- Text chunking (Telegram max 4096 chars per message)
- Markdown formatting conversion
- Code block handling
- Special character escaping for Telegram MarkdownV2
"""

import re

from jarvis.logging import get_logger

logger = get_logger(__name__)

# Telegram limits
MAX_MESSAGE_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024


class ResponseFormatter:
    """Format OpenCode responses for Telegram.

    Handles chunking long messages and escaping special characters
    for Telegram's MarkdownV2 format.
    """

    @staticmethod
    def escape_markdown(text: str) -> str:
        """Escape special characters for Telegram MarkdownV2.

        In MarkdownV2 mode, these characters must be escaped:
        _ * [ ] ( ) ~ ` > # + - = | { } . !

        Args:
            text: Raw text to escape.

        Returns:
            str: Escaped text safe for Telegram MarkdownV2.
        """
        # Characters that need escaping in MarkdownV2
        escape_chars = r"_\*\[\]\(\)~`>#\+\-=\|{}\.!"
        # Use regex to escape each special character
        return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

    @classmethod
    def chunk_message(cls, text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
        """Split long message into chunks for Telegram.

        Attempts to split at word boundaries or code block boundaries
        to avoid breaking formatting.

        Args:
            text: Message text to chunk.
            max_length: Maximum chunk length (default 4096).

        Returns:
            list[str]: List of message chunks.
        """
        if len(text) <= max_length:
            return [text]

        chunks = []
        remaining = text

        while remaining:
            if len(remaining) <= max_length:
                chunks.append(remaining)
                break

            # Try to find a good split point
            chunk = remaining[:max_length]

            # Look for code block boundary first
            if "```" in chunk:
                # Find the last complete code block
                last_close = chunk.rfind("```")
                if last_close > max_length * 0.3:  # At least 30% of chunk
                    split_point = last_close + 3
                else:
                    # Find last newline
                    split_point = chunk.rfind("\n")
                    if split_point == -1:
                        split_point = max_length
            else:
                # Find last newline or space for word boundary
                split_point = chunk.rfind("\n")
                if split_point == -1 or split_point < max_length * 0.5:
                    split_point = chunk.rfind(" ")
                    if split_point == -1 or split_point < max_length * 0.5:
                        split_point = max_length

            chunks.append(remaining[:split_point])
            remaining = remaining[split_point:].lstrip()

        logger.info("message_chunked", original_length=len(text), chunks=len(chunks))
        return chunks

    @classmethod
    def format_response(
        cls,
        parts: list[dict],
        escape_markdown: bool = True,
    ) -> list[str]:
        """Format OpenCode response parts for Telegram.

        Args:
            parts: List of response parts from OpenCode.
            escape_markdown: Whether to escape markdown characters.

        Returns:
            list[str]: List of formatted message chunks ready to send.
        """
        formatted_parts = []

        for part in parts:
            if part.get("type") == "text":
                text = part.get("text", "")
                if escape_markdown:
                    text = cls.escape_markdown(text)

                # Chunk if necessary
                chunks = cls.chunk_message(text)
                formatted_parts.extend(chunks)
            elif part.get("type") == "tool_result":
                # Tool results might need special formatting
                result_text = str(part.get("result", ""))
                if result_text:
                    if escape_markdown:
                        result_text = cls.escape_markdown(result_text)
                    formatted_parts.extend(cls.chunk_message(result_text))

        if not formatted_parts:
            # Return empty indicator if no parts
            return ["_No response_"]

        return formatted_parts

    @staticmethod
    def format_error_message(error: str) -> str:
        """Format an error message for Telegram.

        Args:
            error: Error message text.

        Returns:
            str: Formatted error message.
        """
        # Escape and wrap in italics
        escaped = ResponseFormatter.escape_markdown(error)
        return f"⚠️ _{escaped}_"
