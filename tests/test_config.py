"""Tests for configuration module."""

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
        monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "https://test.tailnet.ts.net/webhook")
        monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "test_password")

        settings = get_settings()

        assert settings.telegram_bot_id == "test_token_123"
        assert settings.telegram_user_id == 123456789
        assert settings.telegram_webhook_url == "https://test.tailnet.ts.net/webhook"
        assert settings.opencode_server_password == "test_password"
        # Check defaults
        assert settings.telegram_webhook_port == 8080
        assert settings.log_level == "INFO"
        assert settings.jarvis_env == "production"

    def test_log_level_validation(self, monkeypatch):
        """Test log level validation accepts valid values."""
        monkeypatch.setenv("TELEGRAM_BOT_ID", "test")
        monkeypatch.setenv("TELEGRAM_USER_ID", "123")
        monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "https://test/webhook")
        monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "test")
        monkeypatch.setenv("LOG_LEVEL", "debug")  # lowercase should work

        settings = get_settings()
        assert settings.log_level == "DEBUG"

    def test_log_level_validation_rejects_invalid(self, monkeypatch):
        """Test log level validation rejects invalid values."""
        monkeypatch.setenv("TELEGRAM_BOT_ID", "test")
        monkeypatch.setenv("TELEGRAM_USER_ID", "123")
        monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "https://test/webhook")
        monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "test")
        monkeypatch.setenv("LOG_LEVEL", "INVALID")

        with pytest.raises(ValueError, match="log_level must be one of"):
            get_settings()

    def test_user_id_validation_rejects_negative(self, monkeypatch):
        """Test user ID validation rejects negative values."""
        monkeypatch.setenv("TELEGRAM_BOT_ID", "test")
        monkeypatch.setenv("TELEGRAM_USER_ID", "-1")
        monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "https://test/webhook")
        monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "test")

        with pytest.raises(ValueError, match="telegram_user_id must be positive"):
            get_settings()

    def test_port_validation_rejects_invalid(self, monkeypatch):
        """Test port validation rejects out-of-range values."""
        monkeypatch.setenv("TELEGRAM_BOT_ID", "test")
        monkeypatch.setenv("TELEGRAM_USER_ID", "123")
        monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "https://test/webhook")
        monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "test")
        monkeypatch.setenv("TELEGRAM_WEBHOOK_PORT", "99999")

        with pytest.raises(ValueError, match="Port must be between 1-65535"):
            get_settings()

    def test_settings_uses_defaults(self, monkeypatch):
        """Test that default values are applied when not specified."""
        monkeypatch.setenv("TELEGRAM_BOT_ID", "test")
        monkeypatch.setenv("TELEGRAM_USER_ID", "123")
        monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "https://test/webhook")
        monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "test")

        settings = get_settings()

        assert settings.telegram_webhook_port == 8080
        assert settings.opencode_url == "http://opencode:4096"
        assert settings.session_storage_path == "/app/data/sessions.json"
