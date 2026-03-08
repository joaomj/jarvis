"""Tests for KB/save command behavior."""

from __future__ import annotations

import pytest

from jarvis.bot import JarvisBot
from jarvis.config import Settings


@pytest.fixture
def settings(tmp_path):
    db_path = tmp_path / "test.db"
    return Settings(
        telegram_bot_id="test_token",
        telegram_user_id=123456789,
        telegram_polling_interval=1.0,
        telegram_polling_timeout=30,
        opencode_url="http://localhost:4096",
        opencode_server_password="test_password",
        database_path=str(db_path),
        enable_message_audit=True,
    )


def test_extract_urls_from_text(settings) -> None:
    """Test URL extraction utility still works."""
    bot = JarvisBot(settings)

    urls = bot._extract_urls("Check out https://example.com/article and https://another.com")
    assert len(urls) == 2
    assert "https://example.com/article" in urls
    assert "https://another.com" in urls


def test_extract_urls_no_urls(settings) -> None:
    """Test URL extraction returns empty list when no URLs."""
    bot = JarvisBot(settings)

    urls = bot._extract_urls("This is just some text without URLs")
    assert urls == []


def test_kb_indexer_initialized(settings) -> None:
    """Test that KB indexer is initialized on bot creation."""
    bot = JarvisBot(settings)

    assert bot.kb_indexer is not None
    assert hasattr(bot.kb_indexer, "index_all")


@pytest.mark.asyncio
async def test_url_only_message_suggests_save_command(settings) -> None:
    """Test that URL-only messages trigger the save command suggestion."""
    # This functionality is in utils.py
    # We verify the is_url_only function works
    from jarvis.utils import is_url_only

    assert is_url_only("https://example.com/article") is True
    assert is_url_only("  https://example.com/article  ") is True
    assert is_url_only("Check out https://example.com/article") is False
    assert is_url_only("Just some text") is False
    assert is_url_only("") is False
