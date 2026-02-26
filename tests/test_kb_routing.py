"""Tests for KB/save intent routing behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.bot import JarvisBot
from jarvis.config import Settings


@pytest.fixture
def settings(tmp_path):
    db_path = tmp_path / "test.db"
    return Settings(
        telegram_bot_id="test_token",
        telegram_user_id=123456789,
        telegram_polling_interval=1.0,
        telegram_polling_timeout=30,
        opencode_url="http://localhost:4096",
        opencode_server_password="test_password",
        database_path=str(db_path),
        enable_message_audit=True,
    )


def test_save_intent_detects_url_only_message(settings) -> None:
    bot = JarvisBot(settings)

    assert bot._is_save_intent("https://example.com/article") is True
    assert bot._is_save_intent("save this https://example.com/article for read later") is True
    assert bot._is_save_intent("save this for later") is False


def test_bookmark_query_matching_still_works(settings) -> None:
    bot = JarvisBot(settings)

    assert bot._is_bookmark_query("What did I save last week?") is True
    assert bot._is_bookmark_query("save https://example.com/article") is False


@pytest.mark.asyncio
async def test_process_input_prefers_save_handler_for_save_intent(settings) -> None:
    bot = JarvisBot(settings)
    bot.model_selector = None
    bot.events.handle_interaction_input = AsyncMock(return_value=False)
    bot._is_save_intent = MagicMock(return_value=True)
    bot._handle_save_intent = AsyncMock(return_value=True)
    bot._is_bookmark_query = MagicMock(return_value=False)

    update = MagicMock()
    update.effective_message.chat_id = 100
    update.effective_message.message_id = 200
    bot.opencode = MagicMock()

    result = await bot._process_input(
        update, user_id=123, session_id="sess-1", text="https://x.com"
    )

    assert result is None
    bot._handle_save_intent.assert_awaited_once()
