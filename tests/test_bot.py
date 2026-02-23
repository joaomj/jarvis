"""Tests for Telegram bot polling mode."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.bot import JarvisBot
from jarvis.config import Settings
from jarvis.database import Database
from jarvis.session_manager import SessionManager


class TestJarvisBotPolling:
    """Test suite for polling-based JarvisBot."""

    @pytest.fixture
    def settings(self, tmp_path):
        """Create test settings with temp database."""
        db_path = tmp_path / "test.db"
        return Settings(
            telegram_bot_id="test_token",
            telegram_user_id=123456789,
            telegram_polling_interval=0.5,  # Fast for tests (min 0.5s)
            telegram_polling_timeout=10,
            opencode_url="http://localhost:4096",
            opencode_server_password="test_password",
            database_path=str(db_path),
            enable_message_audit=True,
        )

    @pytest.fixture
    def mock_opencode(self):
        """Create mock OpenCode client."""
        mock = MagicMock()
        mock.health_check = AsyncMock(return_value=True)
        mock.create_session = AsyncMock(return_value="test-session-id")
        mock.send_message = AsyncMock(return_value=[{"type": "text", "text": "Response"}])
        mock.send_command = AsyncMock(return_value=[{"type": "text", "text": "Command response"}])
        mock.close = AsyncMock()
        return mock

    @pytest.fixture
    def bot(self, settings):
        """Create test bot instance."""
        return JarvisBot(settings)

    def test_bot_initialization(self, settings):
        """Test bot initializes with polling settings."""
        bot = JarvisBot(settings)
        assert bot.settings.telegram_user_id == 123456789
        assert bot.session_manager is None  # Set during initialize()
        assert bot.polling is None

    @pytest.mark.asyncio
    async def test_initialize_creates_database(self, settings):
        """Test initialization creates SQLite database."""
        with patch("jarvis.bot.OpenCodeClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.health_check = AsyncMock(return_value=(True, "OK (v1.0.0)"))
            mock_instance.get_config = AsyncMock(return_value={})
            mock_instance.get_current_model = MagicMock(return_value=None)
            mock_client.return_value = mock_instance

            bot = JarvisBot(settings)
            await bot.initialize()

            assert Path(settings.database_path).exists()

    @pytest.mark.asyncio
    async def test_is_authorized_checks_database(self, settings):
        """Test authorization uses SQLite."""
        bot = JarvisBot(settings)

        # User not in DB yet
        assert bot._is_authorized(123456789) is False

        # Add user
        bot.db.add_user(123456789)

        # Now authorized
        assert bot._is_authorized(123456789) is True
        assert bot._is_authorized(999999) is False

    @pytest.mark.asyncio
    async def test_message_audit_logging(self, settings):
        """Test messages are logged to database."""
        bot = JarvisBot(settings)
        bot.db.add_user(123456789)

        # Log a message
        bot.db.log_message(123456789, "in", "Hello test message")

        # Verify count
        count = bot.db.get_user_message_count(123456789)
        assert count == 1

    @pytest.mark.asyncio
    async def test_handle_update_rejects_unauthorized(self, settings, mock_opencode):
        """Test unauthorized users are rejected."""
        bot = JarvisBot(settings)
        bot.opencode = mock_opencode

        # Create mock update
        mock_update = MagicMock()
        mock_update.callback_query = None
        mock_update.effective_user.id = 999999  # Not authorized
        mock_update.effective_message.text = "Hello"

        await bot._handle_update(mock_update)

        # Should not process - no opencode calls
        mock_opencode.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_session_command_creates_session(self, settings):
        """Test /new command creates session and stores session ID."""
        from jarvis.handlers.commands import handle_intercept_command

        mock_opencode = MagicMock()
        mock_opencode.create_session = AsyncMock(return_value="test-session-123")
        mock_opencode.send_message = AsyncMock(return_value=[{"type": "text", "text": "Session started"}])

        bot = JarvisBot(settings)
        bot.opencode = mock_opencode
        bot.session_manager = SessionManager(mock_opencode, bot.db)
        bot.db.add_user(12345)

        result = await handle_intercept_command("new", "Test Session", 12345, bot)

        mock_opencode.create_session.assert_called_once_with(title="Test Session")
        assert "test-session-123" in result
        assert bot.session_manager.get_session(12345) == "test-session-123"


class TestPollingEngine:
    """Tests for polling engine."""

    @pytest.fixture
    def mock_app(self):
        """Create mock Telegram application."""
        mock = MagicMock()
        mock.bot.get_updates = AsyncMock(return_value=[])
        return mock

    @pytest.mark.asyncio
    async def test_polling_loop_fetches_updates(self, mock_app):
        """Test polling engine fetches updates."""
        from jarvis.polling_engine import PollingEngine

        engine = PollingEngine(mock_app, interval=0.01, timeout=5)

        # Mock to stop after one iteration
        call_count = 0

        async def stop_after_one(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                engine.stop()
            return []

        mock_app.bot.get_updates = stop_after_one

        handler = AsyncMock()
        await engine.start(handler)

        # Verify get_updates was called
        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_polling_backoff_on_error(self, mock_app):
        """Test exponential backoff on errors."""
        from jarvis.polling_engine import PollingEngine

        engine = PollingEngine(mock_app, interval=0.01, timeout=5)

        # Make get_updates fail
        mock_app.bot.get_updates = AsyncMock(side_effect=Exception("Network error"))

        # Run briefly then stop
        async def run_with_timeout():
            handler = AsyncMock()
            try:
                await asyncio.wait_for(engine.start(handler), timeout=0.1)
            except TimeoutError:
                engine.stop()

        await run_with_timeout()

        # Verify backoff counter increased
        assert engine._backoff > 1

    @pytest.mark.asyncio
    async def test_polling_requests_callback_query(self, mock_app):
        """Test polling engine requests callback_query updates."""
        from jarvis.polling_engine import PollingEngine

        engine = PollingEngine(mock_app, interval=0.01, timeout=5)

        call_count = 0
        captured_kwargs = {}

        async def capture_get_updates(*args, **kwargs):
            nonlocal call_count, captured_kwargs
            call_count += 1
            captured_kwargs = kwargs
            if call_count >= 1:
                engine.stop()
            return []

        mock_app.bot.get_updates = capture_get_updates

        handler = AsyncMock()
        await engine.start(handler)

        assert "allowed_updates" in captured_kwargs
        assert "callback_query" in captured_kwargs["allowed_updates"]
        assert "message" in captured_kwargs["allowed_updates"]


class TestDatabase:
    """Tests for database layer."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database."""
        db_path = tmp_path / "test.db"
        return Database(str(db_path))

    def test_database_creation(self, db, tmp_path):
        """Test database file is created."""
        assert Path(db.db_path).exists()

    def test_user_management(self, db):
        """Test adding and checking users."""
        # New user not allowed
        assert db.is_user_allowed(123) is False

        # Add user
        db.add_user(123)

        # Now allowed
        assert db.is_user_allowed(123) is True

    def test_message_logging(self, db):
        """Test message audit trail."""
        db.add_user(123)

        # Log messages
        db.log_message(123, "in", "Hello")
        db.log_message(123, "out", "Hi there")

        # Verify count
        assert db.get_user_message_count(123) == 2


class TestFeedbackOperations:
    """Tests for feedback operations."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database."""
        db_path = tmp_path / "test.db"
        return Database(str(db_path))

    def test_create_turn(self, db):
        """Test creating a feedback turn record."""
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
        assert turn["response_text"] == "AI stands for Artificial Intelligence."
        assert turn["vote"] is None

    def test_set_out_message_id(self, db):
        """Test setting outgoing message ID."""
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

    def test_record_vote_authorized(self, db):
        """Test recording vote by authorized user."""
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

    def test_record_vote_unauthorized(self, db):
        """Test that unauthorized user cannot vote."""
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

    def test_record_vote_overwrite(self, db):
        """Test that vote can be overwritten (last vote wins)."""
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

        parts = [
            {"type": "text", "text": "First chunk"},
            {"type": "text", "text": "Second chunk"},
        ]

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

        parts = [{"type": "text", "text": "Response"}]

        await bot._send_response(mock_update, parts, turn_id)

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

        parts = [{"type": "text", "text": "Response"}]

        await bot._send_response(mock_update, parts, turn_id=None)

        call = mock_msg.reply_text.call_args
        assert call.kwargs.get("reply_markup") is None
