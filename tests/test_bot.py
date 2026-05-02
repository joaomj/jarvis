"""Tests for bot entry point wiring."""
from pathlib import Path

from src.bot import create_app
from src.config import Settings
from src.telegram_gateway import TelegramGateway


def test_create_app_returns_wired_components():
    """create_app wires all dependencies correctly."""
    settings = Settings(
        telegram_bot_token="test:token",
        telegram_user_id=12345,
        database_path=":memory:",
        soul_path=str(Path.cwd() / "soul" / "SOUL.md"),
    )
    app = create_app(settings)
    assert "settings" in app
    assert "memory" in app
    assert "conversation" in app
    assert "skill_loader" in app
    assert "agent" in app
    assert "gateway" in app
    assert "polling" in app
    assert isinstance(app["gateway"], TelegramGateway)
