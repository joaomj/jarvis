"""Tests for config module (pydantic-settings)."""
from pathlib import Path

import pytest

from src.config import Settings


def test_settings_defaults():
    """Settings can be constructed only with required env vars."""
    s = Settings(
        telegram_bot_token="test:token",
        telegram_user_id=12345,
    )
    assert s.telegram_bot_token == "test:token"
    assert s.telegram_user_id == 12345
    assert s.model == "opencode-go:deepseek-v4-flash"
    assert s.log_level == "INFO"
    assert s.alfred_env == "production"
    assert float(s.telegram_polling_interval) >= 0.5


def test_settings_log_level_validation():
    """Invalid log level raises ValueError."""
    with pytest.raises(ValueError, match="log_level"):
        Settings(
            telegram_bot_token="test:token",
            telegram_user_id=12345,
            log_level="INVALID",
        )


def test_settings_user_id_validation():
    """Non-positive user_id raises ValueError."""
    with pytest.raises(ValueError, match="telegram_user_id"):
        Settings(
            telegram_bot_token="test:token",
            telegram_user_id=0,
        )


def test_settings_expands_user_paths():
    """Paths with ~ get expanded."""
    s = Settings(
        telegram_bot_token="test:token",
        telegram_user_id=12345,
        soul_path="~/my_soul.md",
    )
    assert "~" not in s.soul_path
    assert Path(s.soul_path).is_absolute()
