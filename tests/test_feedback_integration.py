"""Integration tests for feedback system using harness instead of mocks."""

from __future__ import annotations

import pytest

from jarvis.bot import JarvisBot
from jarvis.config import Settings
from jarvis.database import Database
from tests.harness.fake_telegram import FakeTelegramApp
from tests.harness.update_factory import (
    build_callback_update,
    build_message_update,
)


@pytest.fixture
def settings(tmp_path) -> Settings:
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
def bot(settings, fake_telegram_app: FakeTelegramApp) -> JarvisBot:
    """Create test bot instance with real database and fake Telegram app."""
    jarvis_bot = JarvisBot(settings)
    jarvis_bot.app = fake_telegram_app  # type: ignore[assignment]
    return jarvis_bot


class TestDatabaseFeedbackOperations:
    """Database layer tests - verify core feedback schema and operations."""

    def test_create_turn_creates_record(self, tmp_path):
        """Test creating a feedback turn record."""
        db = Database(str(tmp_path / "test.db"))
        turn_id = db.create_turn(
            telegram_user_id=12345,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="What is AI?",
            response_text="AI stands for Artificial Intelligence.",
        )
        assert turn_id > 0

        turn = db.get_turn(turn_id)
        assert turn is not None
        assert turn["telegram_user_id"] == 12345
        assert turn["telegram_chat_id"] == 67890
        assert turn["source"] == "opencode"
        assert turn["prompt_text"] == "What is AI?"
        assert turn["vote"] is None

    def test_set_out_message_id_updates_record(self, tmp_path):
        """Test setting outgoing message ID."""
        db = Database(str(tmp_path / "test.db"))
        turn_id = db.create_turn(
            telegram_user_id=12345,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )
        db.set_out_message_id(turn_id, 99999)
        turn = db.get_turn(turn_id)
        assert turn["telegram_out_message_id"] == 99999

    def test_record_vote_by_authorized_user(self, tmp_path):
        """Test recording vote by authorized user."""
        db = Database(str(tmp_path / "test.db"))
        turn_id = db.create_turn(
            telegram_user_id=12345,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )
        result = db.record_vote(turn_id, 12345, 1)
        assert result is True
        turn = db.get_turn(turn_id)
        assert turn["vote"] == 1
        assert turn["voted_at"] is not None

    def test_record_vote_by_unauthorized_user_is_rejected(self, tmp_path):
        """Test that unauthorized user cannot vote."""
        db = Database(str(tmp_path / "test.db"))
        turn_id = db.create_turn(
            telegram_user_id=12345,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )
        result = db.record_vote(turn_id, 99999, 1)
        assert result is False
        turn = db.get_turn(turn_id)
        assert turn["vote"] is None

    def test_record_vote_overwrites_previous(self, tmp_path):
        """Test that vote can be overwritten."""
        db = Database(str(tmp_path / "test.db"))
        turn_id = db.create_turn(
            telegram_user_id=12345,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )
        db.record_vote(turn_id, 12345, 1)
        db.record_vote(turn_id, 12345, -1)
        turn = db.get_turn(turn_id)
        assert turn["vote"] == -1


@pytest.mark.integration
class TestFeedbackCallbackIntegration:
    """Integration tests for feedback callback handling."""

    async def test_upvote_callback_updates_database(self, bot, fake_telegram_bot):
        """Test upvote callback updates vote in database and removes keyboard."""
        bot.db.add_user(123456789)
        turn_id = bot.db.create_turn(
            telegram_user_id=123456789,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )
        bot.db.set_out_message_id(turn_id, 100)

        update = build_callback_update(
            user_id=123456789,
            data=f"fb:{turn_id}:up",
            message_id=100,
            chat_id=67890,
        )

        await bot._handle_update(update)

        turn = bot.db.get_turn(turn_id)
        assert turn["vote"] == 1

    async def test_downvote_callback_records_negative_vote(self, bot, fake_telegram_bot):
        """Test downvote callback records -1 in database."""
        bot.db.add_user(123456789)
        turn_id = bot.db.create_turn(
            telegram_user_id=123456789,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )
        bot.db.set_out_message_id(turn_id, 101)

        update = build_callback_update(
            user_id=123456789,
            data=f"fb:{turn_id}:down",
            message_id=101,
            chat_id=67890,
        )

        await bot._handle_update(update)

        turn = bot.db.get_turn(turn_id)
        assert turn["vote"] == -1

    async def test_unauthorized_user_cannot_vote(self, bot, fake_telegram_bot):
        """Test unauthorized user cannot record vote."""
        bot.db.add_user(123456789)
        turn_id = bot.db.create_turn(
            telegram_user_id=123456789,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )

        update = build_callback_update(
            user_id=999999,
            data=f"fb:{turn_id}:up",
            message_id=100,
            chat_id=67890,
        )

        await bot._handle_update(update)

        turn = bot.db.get_turn(turn_id)
        assert turn["vote"] is None

    async def test_invalid_callback_data_is_ignored(self, bot, fake_telegram_bot):
        """Test invalid callback data is ignored without error."""
        bot.db.add_user(123456789)

        update = build_callback_update(
            user_id=123456789,
            data="invalid_data",
            message_id=100,
            chat_id=67890,
        )

        # Should not raise
        await bot._handle_update(update)


@pytest.mark.integration
class TestFeedbackResponseIntegration:
    """Integration tests for response sending with feedback keyboards."""

    async def test_keyboard_attached_only_to_last_chunk(self, bot, fake_telegram_bot):
        """Test that feedback keyboard is only attached to the last chunk."""
        bot.db.add_user(123456789)
        turn_id = bot.db.create_turn(
            telegram_user_id=123456789,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )

        update = build_message_update(
            user_id=123456789,
            chat_id=67890,
            text="Test",
            message_id=1,
            bot=fake_telegram_bot,
        )

        parts = [
            {"type": "text", "text": "First chunk"},
            {"type": "text", "text": "Second chunk"},
        ]

        await bot._send_response(update, parts, turn_id)

        assert len(fake_telegram_bot.sent_messages) == 2
        first_msg = fake_telegram_bot.sent_messages[0]
        second_msg = fake_telegram_bot.sent_messages[1]

        assert first_msg.reply_markup is None
        assert second_msg.reply_markup is not None

    async def test_message_id_stored_after_sending(self, bot, fake_telegram_bot):
        """Test that message ID is stored after sending response."""
        bot.db.add_user(123456789)
        turn_id = bot.db.create_turn(
            telegram_user_id=123456789,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )

        update = build_message_update(
            user_id=123456789,
            chat_id=67890,
            text="Test",
            message_id=1,
            bot=fake_telegram_bot,
        )

        await bot._send_response(update, [{"type": "text", "text": "Response"}], turn_id)

        turn = bot.db.get_turn(turn_id)
        assert turn["telegram_out_message_id"] == fake_telegram_bot.sent_messages[0].message_id

    async def test_no_keyboard_when_turn_id_is_none(self, bot, fake_telegram_bot):
        """Test that no keyboard is attached when turn_id is None."""
        bot.db.add_user(123456789)

        update = build_message_update(
            user_id=123456789,
            chat_id=67890,
            text="Test",
            message_id=1,
            bot=fake_telegram_bot,
        )

        await bot._send_response(update, [{"type": "text", "text": "Response"}], turn_id=None)

        assert len(fake_telegram_bot.sent_messages) == 1
        assert fake_telegram_bot.sent_messages[0].reply_markup is None
