"""Tests for Telegram bot polling mode."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.bot import JarvisBot
from jarvis.config import Settings
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
            telegram_polling_interval=0.5,
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

    def test_bot_initialization(self, settings):
        """Test bot initializes with polling settings."""
        bot = JarvisBot(settings)
        assert bot.settings.telegram_user_id == 123456789
        assert bot.session_manager is None
        assert bot.polling is None

    @pytest.mark.asyncio
    async def test_initialize_creates_database(self, settings):
        """Test initialization creates SQLite database."""
        with patch("jarvis.bot.OpenCodeClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.health_check = AsyncMock(return_value=(True, "OK (v1.0.0)"))
            mock_client.return_value = mock_instance
            bot = JarvisBot(settings)
            await bot.initialize()
            assert Path(settings.database_path).exists()

    @pytest.mark.asyncio
    async def test_is_authorized_checks_database(self, settings):
        """Test authorization uses SQLite."""
        bot = JarvisBot(settings)
        assert bot._is_authorized(123456789) is False
        bot.db.add_user(123456789)
        assert bot._is_authorized(123456789) is True
        assert bot._is_authorized(999999) is False

    @pytest.mark.asyncio
    async def test_message_audit_logging(self, settings):
        """Test messages are logged to database."""
        bot = JarvisBot(settings)
        bot.db.add_user(123456789)
        bot.db.log_message(123456789, "in", "Hello test message")
        assert bot.db.get_user_message_count(123456789) == 1

    @pytest.mark.asyncio
    async def test_handle_update_rejects_unauthorized(self, settings, mock_opencode):
        """Test unauthorized users are rejected."""
        bot = JarvisBot(settings)
        bot.opencode = mock_opencode

        mock_update = MagicMock()
        mock_update.callback_query = None
        mock_update.effective_user.id = 999999
        mock_update.effective_message.text = "Hello"

        await bot._handle_update(mock_update)
        mock_opencode.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_session_command_creates_session(self, settings):
        """Test /new command creates session and stores session ID."""
        from jarvis.handlers.commands import handle_intercept_command

        mock_opencode = MagicMock()
        mock_opencode.create_session = AsyncMock(return_value="test-session-123")
        mock_opencode.send_message = AsyncMock(
            return_value=[{"type": "text", "text": "Session started"}]
        )

        bot = JarvisBot(settings)
        bot.opencode = mock_opencode
        bot.session_manager = SessionManager(mock_opencode, bot.db)
        bot.db.add_user(12345)

        result = await handle_intercept_command("new", "Test Session", 12345, bot)
        mock_opencode.create_session.assert_called_once_with(title="Test Session")
        assert "test-session-123" in result
        assert bot.session_manager.get_session(12345) == "test-session-123"
