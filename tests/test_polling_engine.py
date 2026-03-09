"""Tests for polling engine behavior."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.polling_engine import PollingEngine


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
        engine = PollingEngine(mock_app, interval=0.01, timeout=5)
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
        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_polling_backoff_on_error(self, mock_app):
        """Test exponential backoff on errors."""
        engine = PollingEngine(mock_app, interval=0.01, timeout=5)
        mock_app.bot.get_updates = AsyncMock(side_effect=Exception("Network error"))

        async def run_with_timeout() -> None:
            handler = AsyncMock()
            try:
                await asyncio.wait_for(engine.start(handler), timeout=0.1)
            except TimeoutError:
                engine.stop()

        await run_with_timeout()
        assert engine._backoff > 1

    @pytest.mark.asyncio
    async def test_polling_requests_callback_query(self, mock_app):
        """Test polling engine requests callback_query updates."""
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
