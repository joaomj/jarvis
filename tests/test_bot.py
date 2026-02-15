"""Tests for Telegram bot polling mode."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Message, Update, User

from jarvis.bot import JarvisBot
from jarvis.config import Settings
from jarvis.database import Database


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
        assert bot.sessions == {}
        assert bot.polling is None

    @pytest.mark.asyncio
    async def test_initialize_creates_database(self, settings):
        """Test initialization creates SQLite database."""
        with patch("jarvis.bot.OpenCodeClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.health_check = AsyncMock(return_value=True)
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
        mock_update.effective_user.id = 999999  # Not authorized
        mock_update.effective_message.text = "Hello"
        
        await bot._handle_update(mock_update)
        
        # Should not process - no opencode calls
        mock_opencode.send_message.assert_not_called()


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
            except asyncio.TimeoutError:
                engine.stop()
        
        await run_with_timeout()
        
        # Verify backoff counter increased
        assert engine._backoff > 1


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
