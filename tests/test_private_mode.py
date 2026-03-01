"""Tests for private turn persistence behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.event_processor import EventProcessor, PendingPrompt


@pytest.mark.asyncio
async def test_private_pending_prompt_skips_turn_creation() -> None:
    """Private async completions are sent without creating feedback turns."""
    bot = MagicMock()
    bot.settings = SimpleNamespace(telegram_user_id=123)
    bot._is_authorized = MagicMock(return_value=True)
    bot.app = MagicMock()
    bot.app.bot.send_message = AsyncMock()
    bot._send_response_to_chat = AsyncMock()
    bot._on_save_completed = AsyncMock()
    bot.db.create_turn = MagicMock()
    bot.opencode = MagicMock()
    bot.opencode.get_session_messages = AsyncMock(
        return_value=[
            {
                "info": {
                    "role": "assistant",
                    "modelID": "gpt-4o",
                    "providerID": "openai",
                    "agent": "build",
                },
                "parts": [{"type": "text", "text": "done"}],
            }
        ]
    )

    processor = EventProcessor(bot)
    pending = PendingPrompt(
        user_id=123,
        chat_id=100,
        in_message_id=200,
        prompt_text="private prompt",
        is_private=True,
    )

    await processor._send_completed_response("session-1", pending)

    bot.db.create_turn.assert_not_called()
    bot._send_response_to_chat.assert_awaited_once()
    _, kwargs = bot._send_response_to_chat.await_args
    assert kwargs["turn_id"] is None
