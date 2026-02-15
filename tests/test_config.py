"""Tests for configuration module with polling settings."""

import os

import pytest

from jarvis.config import Settings, get_settings


class TestSettings:
    """Test suite for Settings configuration."""

    def test_settings_loads_from_env_vars(self, monkeypatch):
        """Test that settings loads correctly from environment variables."""
        # Set required env vars
        monkeypatch.setenv("TELEGRAM_BOT_ID", "test_token_123")
        monkeypatch.setenv("TELEGRAM_USER_ID", "123456789")
        monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "test_password")

        settings = get_settings()

        assert settings.telegram_bot_id == "test_token_123"
        assert settings.telegram_user_id == 123456789
        assert settings.opencode_server_password == "test_password"
        # Check polling defaults
        assert settings.telegram_polling_interval == 1.0
        assert settings.telegram_polling_timeout == 30
        assert settings.log_level == "INFO"
        assert settings.jarvis_env == "production"
        assert settings.database_path == ".jarvis/jarvis.db"
        assert settings.enable_message_audit is True

    def test_log_level_validation(self, monkeypatch):
        """Test log level validation accepts valid values."""
        monkeypatch.setenv("TELEGRAM_BOT_ID", "test")
        monkeypatch.setenv("TELEGRAM_USER_ID", "123")
        monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "test")
        monkeypatch.setenv("LOG_LEVEL", "debug")  # lowercase should work

        settings = get_settings()
        assert settings.log_level == "DEBUG"

    def test_log_level_validation_rejects_invalid(self, monkeypatch):
        """Test log level validation rejects invalid values."""
        monkeypatch.setenv("TELEGRAM_BOT_ID", "test")
        monkeypatch.setenv("TELEGRAM_USER_ID", "123")
        monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "test")
        monkeypatch.setenv("LOG_LEVEL", "INVALID")

        with pytest.raises(ValueError, match="log_level must be one of"):
            get_settings()

    def test_user_id_validation_rejects_negative(self, monkeypatch):
        """Test user ID validation rejects negative values."""
        monkeypatch.setenv("TELEGRAM_BOT_ID", "test")
        monkeypatch.setenv("TELEGRAM_USER_ID", "-1")
        monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "test")

        with pytest.raises(ValueError, match="telegram_user_id must be positive"):
            get_settings()

    def test_polling_interval_validation(self, monkeypatch):
        """Test polling interval validation."""
        monkeypatch.setenv("TELEGRAM_BOT_ID", "test")
        monkeypatch.setenv("TELEGRAM_USER_ID", "123")
        monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "test")
        monkeypatch.setenv("TELEGRAM_POLLING_INTERVAL", "0.5")

        # Should accept 0.5 seconds (minimum)
        settings = get_settings()
        assert settings.telegram_polling_interval == 0.5

    def test_polling_interval_rejects_too_fast(self, monkeypatch):
        """Test polling interval rejects values too fast."""
        monkeypatch.setenv("TELEGRAM_BOT_ID", "test")
        monkeypatch.setenv("TELEGRAM_USER_ID", "123")
        monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "test")
        monkeypatch.setenv("TELEGRAM_POLLING_INTERVAL", "0.1")  # Too fast

        with pytest.raises(ValueError, match="polling_interval must be >= 0.5s"):
            get_settings()

    def test_polling_timeout_validation(self, monkeypatch):
        """Test polling timeout validation."""
        monkeypatch.setenv("TELEGRAM_BOT_ID", "test")
        monkeypatch.setenv("TELEGRAM_USER_ID", "123")
        monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "test")
        monkeypatch.setenv("TELEGRAM_POLLING_TIMEOUT", "200")  # Too long

        with pytest.raises(ValueError, match="polling_timeout must be 10-120s"):
            get_settings()

    def test_settings_uses_defaults(self, monkeypatch):
        """Test that default values are applied when not specified."""
        monkeypatch.setenv("TELEGRAM_BOT_ID", "test")
        monkeypatch.setenv("TELEGRAM_USER_ID", "123")
        monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "test")
        # Ensure we're not overriding defaults
        monkeypatch.delenv("OPENCODE_URL", raising=False)
        monkeypatch.delenv("TELEGRAM_POLLING_INTERVAL", raising=False)
        monkeypatch.delenv("TELEGRAM_POLLING_TIMEOUT", raising=False)

        settings = get_settings()

        assert settings.telegram_polling_interval == 1.0
        assert settings.telegram_polling_timeout == 30
        # Note: opencode_url default only works if not set in .env
        # assert settings.opencode_url == "http://localhost:4096"
        assert settings.database_path == ".jarvis/jarvis.db"
        assert settings.enable_message_audit is True
