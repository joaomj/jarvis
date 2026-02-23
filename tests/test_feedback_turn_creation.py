"""Tests for turn creation during response handling."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.bot import JarvisBot
from jarvis.config import Settings


class TestFeedbackTurnCreation:
    """Tests for turn creation during response handling."""

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
    async def test_send_response_attaches_keyboard_only_on_last_chunk(self, bot):
        """Test that feedback keyboard is only attached to the last chunk."""
        bot.db.add_user(123456789)
        turn_id = bot.db.create_turn(
            telegram_user_id=123456789,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )

        mock_msg = MagicMock()
        mock_msg.reply_text = AsyncMock(return_value=MagicMock(message_id=123))
        mock_update = MagicMock()
        mock_update.effective_message = mock_msg
        mock_update.callback_query = None
        parts = [{"type": "text", "text": "First chunk"}, {"type": "text", "text": "Second chunk"}]

        await bot._send_response(mock_update, parts, turn_id)
        assert mock_msg.reply_text.call_count == 2

        first_call = mock_msg.reply_text.call_args_list[0]
        second_call = mock_msg.reply_text.call_args_list[1]
        assert first_call.kwargs.get("reply_markup") is None
        assert second_call.kwargs.get("reply_markup") is not None

    @pytest.mark.asyncio
    async def test_send_response_stores_message_id(self, bot):
        """Test that message ID is stored after sending."""
        bot.db.add_user(123456789)
        turn_id = bot.db.create_turn(
            telegram_user_id=123456789,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )

        mock_msg = MagicMock()
        mock_msg.reply_text = AsyncMock(return_value=MagicMock(message_id=999))
        mock_update = MagicMock()
        mock_update.effective_message = mock_msg
        mock_update.callback_query = None

        await bot._send_response(mock_update, [{"type": "text", "text": "Response"}], turn_id)
        turn = bot.db.get_turn(turn_id)
        assert turn["telegram_out_message_id"] == 999

    @pytest.mark.asyncio
    async def test_send_response_without_turn_id_no_keyboard(self, bot):
        """Test that no keyboard is attached when turn_id is None."""
        mock_msg = MagicMock()
        mock_msg.reply_text = AsyncMock(return_value=MagicMock(message_id=123))
        mock_update = MagicMock()
        mock_update.effective_message = mock_msg
        mock_update.callback_query = None

        await bot._send_response(mock_update, [{"type": "text", "text": "Response"}], turn_id=None)
        assert mock_msg.reply_text.call_args.kwargs.get("reply_markup") is None
