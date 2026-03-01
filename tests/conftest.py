"""Shared fixtures for integration-style tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from jarvis.config import Settings
from tests.harness.fake_opencode_server import FakeOpenCodeServer, build_opencode_client
from tests.harness.fake_telegram import FakeTelegramApp, FakeTelegramBot


@pytest.fixture
def integration_settings(tmp_path: pytest.TempPathFactory) -> Settings:
    """Build test settings with isolated DB and vault roots."""
    db_path = tmp_path / "jarvis-test.db"
    return Settings(
        telegram_bot_id="test_token",
        telegram_user_id=123456789,
        telegram_polling_interval=1.0,
        telegram_polling_timeout=30,
        opencode_url="http://opencode.test",
        opencode_server_password="test_password",
        database_path=str(db_path),
        enable_message_audit=True,
        vault_root=str(tmp_path / "vault"),
        kb_content_dir=str(tmp_path / "vault" / "sources"),
    )


@pytest.fixture
def fake_telegram_bot() -> FakeTelegramBot:
    """Provide deterministic fake Telegram bot API."""
    return FakeTelegramBot()


@pytest.fixture
def fake_telegram_app(fake_telegram_bot: FakeTelegramBot) -> FakeTelegramApp:
    """Provide fake Telegram application wrapper."""
    return FakeTelegramApp(bot=fake_telegram_bot)


@pytest.fixture
def fake_opencode_server() -> FakeOpenCodeServer:
    """Provide in-process fake OpenCode ASGI server."""
    return FakeOpenCodeServer()


@pytest.fixture
async def fake_opencode_client(
    fake_opencode_server: FakeOpenCodeServer,
) -> AsyncIterator:
    """Provide OpenCodeClient bound to fake OpenCode server."""
    client = await build_opencode_client(fake_opencode_server)
    try:
        yield client
    finally:
        await client.close()
