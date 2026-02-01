"""Tests for Telegram bot module."""

import pytest
from telegram import Message, Update, User

from jarvis.bot import JarvisBot
from jarvis.config import Settings


class MockMessage:
    """Mock Telegram message for testing."""

    def __init__(self, text: str = ""):
        self.text = text
        self.replies = []

    async def reply_text(self, text: str, **kwargs) -> None:
        """Mock reply method."""
        self.replies.append(text)


class MockUser:
    """Mock Telegram user for testing."""

    def __init__(self, user_id: int):
        self.id = user_id


class MockUpdate:
    """Mock Telegram update for testing."""

    def __init__(self, user_id: int, text: str = ""):
        self.effective_user = MockUser(user_id)
        self.effective_message = MockMessage(text)


class MockContext:
    """Mock Telegram context for testing."""

    pass


class TestJarvisBot:
    """Test suite for JarvisBot."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            telegram_bot_id="test_token",
            telegram_user_id=123456789,
            telegram_webhook_url="https://test.webhook",
            telegram_webhook_port=8080,
            opencode_url="http://localhost:4096",
            opencode_server_password="test_password",
        )

    @pytest.fixture
    def bot(self, settings):
        """Create test bot."""
        return JarvisBot(settings)

    def test_bot_initialization(self, bot):
        """Test bot initializes with correct settings."""
        assert bot.allowed_user_id == 123456789
        assert bot.sessions == {}

    def test_is_authorized_allows_configured_user(self, bot):
        """Test authorized user is recognized."""
        assert bot._is_authorized(123456789) is True

    def test_is_authorized_rejects_other_users(self, bot):
        """Test unauthorized users are rejected."""
        assert bot._is_authorized(999999999) is False
        assert bot._is_authorized(0) is False

    def test_is_authorized_rejects_negative_user_id(self, bot):
        """Test negative user IDs are rejected."""
        assert bot._is_authorized(-1) is False

    @pytest.mark.asyncio
    async def test_save_and_load_sessions(self, bot, tmp_path, monkeypatch):
        """Test session persistence works."""
        # Mock storage path
        storage_path = tmp_path / "sessions.json"
        monkeypatch.setattr(
            bot.settings, "session_storage_path", str(storage_path)
        )

        # Set some sessions
        bot.sessions = {123456789: "ses-abc", 987654321: "ses-def"}

        # Save
        await bot._save_sessions()

        # Clear
        bot.sessions = {}

        # Load
        await bot._load_sessions()

        assert bot.sessions == {123456789: "ses-abc", 987654321: "ses-def"}

    @pytest.mark.asyncio
    async def test_load_sessions_handles_missing_file(self, bot):
        """Test loading with no existing file initializes empty."""
        await bot._load_sessions()
        assert bot.sessions == {}

    @pytest.mark.asyncio
    async def test_get_or_create_session_creates_new(self, bot, monkeypatch):
        """Test session creation for new user."""
        # Mock opencode client
        mock_opencode = type(
            "MockOpenCode",
            (),
            {
                "create_session": lambda *args, **kwargs: asyncio.coroutine(
                    lambda: "new-session-id"
                )()
            },
        )()
        bot.opencode = mock_opencode

        import asyncio

        mock_opencode.create_session = lambda title: asyncio.Future()
        mock_opencode.create_session.return_value = "new-session-id"

        session_id = await bot._get_or_create_session(123456789)

        assert session_id == "new-session-id"
        assert bot.sessions[123456789] == "new-session-id"

    def test_format_response_chunks_long_messages(self, bot):
        """Test long responses are chunked."""
        parts = [{"type": "text", "text": "A" * 5000}]

        # Mock the formatter's behavior
        chunks = bot.formatter.format_response(parts, escape_markdown=False)

        assert len(chunks) > 1

    @pytest.mark.asyncio
    async def test_handle_message_rejects_unauthorized(self, bot):
        """Test unauthorized users are silently ignored."""
        update = MockUpdate(user_id=999999999, text="Hello")
        context = MockContext()

        # Should not raise
        await bot._handle_message(update, context)

        # No reply should be sent
        assert len(update.effective_message.replies) == 0

    @pytest.mark.asyncio
    async def test_handle_message_accepts_authorized(self, bot, monkeypatch):
        """Test authorized users get responses."""
        update = MockUpdate(user_id=123456789, text="Hello")
        context = MockContext()

        # Mock session
        bot.sessions[123456789] = "test-session"

        # Mock opencode
        import asyncio

        mock_opencode = type(
            "MockOpenCode",
            (),
            {
                "send_message": lambda *args, **kwargs: asyncio.coroutine(
                    lambda: [{"type": "text", "text": "Response"}]
                )()
            },
        )()
        bot.opencode = mock_opencode

        # Mock send_message
        mock_opencode.send_message = lambda session, text: asyncio.Future()
        mock_opencode.send_message.return_value = [
            {"type": "text", "text": "Response"}
        ]

        await bot._handle_message(update, context)

        # Reply should be sent
        assert len(update.effective_message.replies) > 0
