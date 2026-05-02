"""Polling engine for Telegram getUpdates via HTTP."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

TELEGRAM_API = "https://api.telegram.org/bot"


class PollingEngine:
    def __init__(
        self,
        bot_token: str,
        interval: float = 1.0,
        timeout: int = 30,
        max_backoff_level: int = 6,
        max_backoff_seconds: int = 60,
    ) -> None:
        self._token = bot_token
        self._interval = interval
        self._timeout = timeout
        self._max_backoff_level = max_backoff_level
        self._max_backoff_seconds = max_backoff_seconds
        self._running = False
        self._offset = 0
        self._backoff = 1
        self._client: httpx.AsyncClient | None = None

    async def start(
        self, handler: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        self._running = True
        self._client = httpx.AsyncClient(timeout=self._timeout)
        while self._running:
            try:
                updates = await self._fetch_updates()
                await self._process_updates(updates, handler)
                self._backoff = 1
            except Exception as exc:
                await self._handle_error(exc)

    async def _fetch_updates(self) -> list[dict[str, Any]]:
        if self._client is None:
            return []
        url = f"{TELEGRAM_API}{self._token}/getUpdates"
        resp = await self._client.post(
            url,
            json={
                "offset": self._offset,
                "limit": 100,
                "timeout": self._timeout,
                "allowed_updates": ["message", "callback_query"],
            },
        )
        resp.raise_for_status()
        data: Any = resp.json()
        result: list[dict[str, Any]] = data.get("result", [])
        return result

    async def _process_updates(
        self,
        updates: list[dict[str, Any]],
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if not updates:
            await asyncio.sleep(self._interval)
            return
        for update in updates:
            try:
                await handler(update)
                self._offset = update["update_id"] + 1
            except Exception:
                self._offset = update["update_id"] + 1

    async def _handle_error(self, _error: Exception) -> None:
        delay = min(2**self._backoff, self._max_backoff_seconds)
        self._backoff = min(self._backoff + 1, self._max_backoff_level)
        await asyncio.sleep(delay)

    def stop(self) -> None:
        self._running = False
