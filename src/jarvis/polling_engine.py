"""Polling engine for Telegram bot.

Handles getUpdates loop with backoff and graceful shutdown.
"""

import asyncio
from collections.abc import Awaitable, Callable

from telegram import Update
from telegram.ext import Application

from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class PollingEngine:
    """Telegram polling loop manager."""

    def __init__(
        self,
        app: Application,
        interval: float = 2.0,
        timeout: int = 30,
        max_backoff_level: int = 6,
        max_backoff_seconds: int = 60,
    ):
        """Initialize polling engine.

        Args:
            app: Telegram application instance.
            interval: Seconds between poll requests.
            timeout: Timeout for getUpdates request.
            max_backoff_level: Max exponential backoff level.
            max_backoff_seconds: Cap for backoff delay.
        """
        self.app = app
        self.interval = interval
        self.timeout = timeout
        self._running = False
        self._offset = 0
        self._backoff = 1
        self._max_backoff_level = max_backoff_level
        self._max_backoff_seconds = max_backoff_seconds

    async def start(
        self,
        message_handler: Callable[[Update], Awaitable[None]]
    ) -> None:
        """Start polling loop.

        Args:
            message_handler: Callback for processing updates.
        """
        self._running = True
        logger.info("polling_started", interval=self.interval)

        while self._running:
            try:
                updates = await self._fetch_updates()
                await self._process_updates(updates, message_handler)
                self._backoff = 1  # Reset backoff on success

            except Exception as e:
                await self._handle_error(e)

    async def _fetch_updates(self) -> list[Update]:
        """Fetch updates from Telegram.

        Returns:
            List of updates.
        """
        return await self.app.bot.get_updates(
            offset=self._offset,
            limit=100,
            timeout=self.timeout,
            allowed_updates=["message", "callback_query"],
        )

    async def _process_updates(
        self,
        updates: list[Update],
        handler: Callable[[Update], Awaitable[None]]
    ) -> None:
        """Process fetched updates.

        Args:
            updates: List of updates.
            handler: Message handler callback.
        """
        if not updates:
            await asyncio.sleep(self.interval)
            return

        for update in updates:
            try:
                await handler(update)
                self._offset = update.update_id + 1
            except Exception as e:
                logger.error(
                    "update_processing_error",
                    update_id=update.update_id,
                    error=str(e)
                )
                # Continue with next update, don't increment offset
                # So we retry this update

    async def _handle_error(self, error: Exception) -> None:
        """Handle polling error with backoff.

        Args:
            error: Exception that occurred.
        """
        delay = min(2 ** self._backoff, self._max_backoff_seconds)
        self._backoff = min(self._backoff + 1, self._max_backoff_level)

        logger.error(
            "polling_error",
            error=str(error),
            retry_delay=delay,
            backoff=self._backoff,
        )

        await asyncio.sleep(delay)

    def stop(self) -> None:
        """Signal polling loop to stop."""
        self._running = False
        logger.info("polling_stop_requested")
