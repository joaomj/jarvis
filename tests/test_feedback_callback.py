"""Tests for feedback callback handling."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.bot import JarvisBot
from jarvis.config import Settings


class TestFeedbackCallback:
    """Tests for feedback callback handling."""

    @pytest.fixture
    def settings(self, tmp_path):
        """Create test settings with temp database."""
        db_path = tmp_path / "test.db"
        return Settings(
            telegram_bot_id="test_token",
            telegram_user_id=123456789,
            telegram_polling_interval=0.5,
            telegram_polling_timeout=10,
            opencode_url="http://localhost:4096",
            opencode_server_password="test_password",
            database_path=str(db_path),
            enable_message_audit=True,
        )

    @pytest.fixture
    def bot(self, settings):
        """Create test bot instance."""
        return JarvisBot(settings)

    @pytest.mark.asyncio
    async def test_callback_updates_vote(self, bot):
        """Test callback query updates vote in database."""
        bot.db.add_user(123456789)
        turn_id = bot.db.create_turn(
            telegram_user_id=123456789,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )

        mock_callback = MagicMock()
        mock_callback.from_user.id = 123456789
        mock_callback.data = f"fb:{turn_id}:up"
        mock_callback.answer = AsyncMock()
        mock_callback.edit_message_reply_markup = AsyncMock()

        mock_update = MagicMock()
        mock_update.callback_query = mock_callback
        mock_update.effective_user = None
        mock_update.effective_message = None

        await bot._handle_update(mock_update)
        turn = bot.db.get_turn(turn_id)
        assert turn["vote"] == 1
        mock_callback.answer.assert_called_once()
        mock_callback.edit_message_reply_markup.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_unauthorized_user(self, bot):
        """Test unauthorized user cannot vote."""
        bot.db.add_user(123456789)
        turn_id = bot.db.create_turn(
            telegram_user_id=123456789,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )

        mock_callback = MagicMock()
        mock_callback.from_user.id = 999999
        mock_callback.data = f"fb:{turn_id}:up"
        mock_callback.answer = AsyncMock()
        mock_callback.edit_message_reply_markup = AsyncMock()

        mock_update = MagicMock()
        mock_update.callback_query = mock_callback

        await bot._handle_update(mock_update)
        turn = bot.db.get_turn(turn_id)
        assert turn["vote"] is None

    @pytest.mark.asyncio
    async def test_callback_invalid_format(self, bot):
        """Test invalid callback data is ignored."""
        bot.db.add_user(123456789)
        mock_callback = MagicMock()
        mock_callback.from_user.id = 123456789
        mock_callback.data = "invalid_data"
        mock_callback.answer = AsyncMock()

        mock_update = MagicMock()
        mock_update.callback_query = mock_callback
        await bot._handle_update(mock_update)
        mock_callback.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_downvote(self, bot):
        """Test downvote records -1."""
        bot.db.add_user(123456789)
        turn_id = bot.db.create_turn(
            telegram_user_id=123456789,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )

        mock_callback = MagicMock()
        mock_callback.from_user.id = 123456789
        mock_callback.data = f"fb:{turn_id}:down"
        mock_callback.answer = AsyncMock()
        mock_callback.edit_message_reply_markup = AsyncMock()

        mock_update = MagicMock()
        mock_update.callback_query = mock_callback
        await bot._handle_update(mock_update)

        turn = bot.db.get_turn(turn_id)
        assert turn["vote"] == -1
