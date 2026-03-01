"""Tests for memory and private-mode routing behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.bot import JarvisBot
from jarvis.config import Settings


@pytest.fixture
def settings(tmp_path):
    """Create test settings with temporary storage."""
    db_path = tmp_path / "test.db"
    return Settings(
        telegram_bot_id="test_token",
        telegram_user_id=123456789,
        telegram_polling_interval=1.0,
        telegram_polling_timeout=30,
        opencode_url="http://localhost:4096",
        opencode_server_password="test_password",
        database_path=str(db_path),
        vault_root=str(tmp_path / "vault"),
        enable_message_audit=True,
    )


def test_private_intent_detection(settings) -> None:
    """Private marker detection recognizes supported prefixes."""
    bot = JarvisBot(settings)
    assert bot._is_private_intent("private: summarize this") is True
    assert bot._is_private_intent("<private> summarize this") is True
    assert bot._is_private_intent("/private summarize this") is True
    assert bot._is_private_intent("summarize this") is False


@pytest.mark.asyncio
async def test_memory_intent_is_handled_locally(settings) -> None:
    """Remember intent stores a memory without calling OpenCode."""
    bot = JarvisBot(settings)
    bot._send_feedback_message = AsyncMock()
    bot.opencode = MagicMock()
    bot.opencode.send_message = AsyncMock(
        return_value=(
            [
                {
                    "type": "text",
                    "text": '{"action":"remember","payload":"Tocqueville warns","needs_confirmation":false}',
                }
            ],
            {},
        )
    )

    update = MagicMock()
    update.effective_message.chat_id = 100
    update.effective_message.message_id = 200

    handled = await bot._handle_memory_intent(
        update,
        user_id=123,
        session_id="sess-memory",
        text="remember Tocqueville warns",
    )

    assert handled is True
    bot._send_feedback_message.assert_awaited_once()
    assert bot.memory_store is not None
    assert bot.memory_store.search("Tocqueville")


def test_incoming_message_log_can_be_skipped_for_private(settings) -> None:
    """Private turns bypass audit persistence."""
    bot = JarvisBot(settings)
    bot.db.add_user(settings.telegram_user_id)

    before_count = bot.db.get_user_message_count(settings.telegram_user_id)
    bot._log_incoming_message(settings.telegram_user_id, "private: secret", persist=False)
    after_count = bot.db.get_user_message_count(settings.telegram_user_id)

    assert before_count == after_count
