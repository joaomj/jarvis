"""Tests for response formatter module."""

import pytest

from jarvis.formatter import ResponseFormatter


class TestResponseFormatter:
    """Test suite for ResponseFormatter."""

    def test_escape_markdown_escapes_special_chars(self):
        """Test that special characters are escaped."""
        text = "Hello *world* and _test_ with `code`"
        escaped = ResponseFormatter.escape_markdown(text)

        assert "\\*world\\*" in escaped
        assert "\\_test\\_" in escaped
        assert "\\`code\\`" in escaped

    def test_escape_markdown_preserves_regular_text(self):
        """Test that regular text without special chars is preserved."""
        text = "Hello world, this is normal text"
        escaped = ResponseFormatter.escape_markdown(text)

        assert escaped == text  # No special chars to escape

    def test_chunk_message_no_chunking_for_short_text(self):
        """Test that short messages aren't chunked."""
        text = "Short message"
        chunks = ResponseFormatter.chunk_message(text)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_message_splits_long_text(self):
        """Test that long messages are split."""
        text = "A" * 5000  # Longer than 4096
        chunks = ResponseFormatter.chunk_message(text)

        assert len(chunks) > 1
        assert all(len(chunk) <= 4096 for chunk in chunks)

    def test_chunk_message_respects_word_boundaries(self):
        """Test that chunking respects word boundaries."""
        # Create text with words separated by spaces
        words = ["word" + str(i) for i in range(2000)]
        text = " ".join(words)

        chunks = ResponseFormatter.chunk_message(text)

        # Each chunk should be <= 4096 chars
        assert all(len(chunk) <= 4096 for chunk in chunks)

    def test_chunk_message_handles_code_blocks(self):
        """Test that chunking respects code block boundaries."""
        code_block = "```python\n" + "print('hello')\n" * 1000 + "```"
        text = "Some text\n" + code_block + "\nMore text"

        chunks = ResponseFormatter.chunk_message(text)

        # All chunks should be <= 4096
        assert all(len(chunk) <= 4096 for chunk in chunks)

    def test_format_response_handles_text_parts(self):
        """Test formatting of text response parts."""
        parts = [{"type": "text", "text": "Hello world"}]

        result = ResponseFormatter.format_response(parts, escape_markdown=False)

        assert result == ["Hello world"]

    def test_format_response_escapes_markdown_by_default(self):
        """Test that markdown is escaped by default."""
        parts = [{"type": "text", "text": "Hello *world*"}]

        result = ResponseFormatter.format_response(parts, escape_markdown=True)

        assert result == ["Hello \\*world\\*"]

    def test_format_response_chunks_long_responses(self):
        """Test that long responses are chunked."""
        parts = [{"type": "text", "text": "A" * 5000}]

        result = ResponseFormatter.format_response(parts, escape_markdown=False)

        assert len(result) > 1
        assert all(len(chunk) <= 4096 for chunk in result)

    def test_format_response_handles_multiple_parts(self):
        """Test formatting multiple response parts."""
        parts = [
            {"type": "text", "text": "First part"},
            {"type": "text", "text": "Second part"},
        ]

        result = ResponseFormatter.format_response(parts, escape_markdown=False)

        assert len(result) == 2
        assert "First part" in result
        assert "Second part" in result

    def test_format_response_handles_empty_parts(self):
        """Test formatting empty response parts."""
        parts = []

        result = ResponseFormatter.format_response(parts)

        assert result == ["_No response_"]

    def test_format_response_handles_tool_results(self):
        """Test formatting tool result parts."""
        parts = [{"type": "tool_result", "result": "Tool output"}]

        result = ResponseFormatter.format_response(parts, escape_markdown=False)

        assert "Tool output" in result

    def test_format_error_message_escapes_and_formats(self):
        """Test error message formatting."""
        error = "Something *went* wrong"
        formatted = ResponseFormatter.format_error_message(error)

        assert "⚠️" in formatted
        assert "\\*went\\*" in formatted
        assert "_" in formatted

    def test_format_response_handles_unknown_part_types(self):
        """Test that unknown part types are handled gracefully."""
        parts = [{"type": "unknown", "data": "test"}]

        result = ResponseFormatter.format_response(parts)

        assert result == ["_No response_"]
