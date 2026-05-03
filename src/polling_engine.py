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

    @property
    def _api_base(self) -> str:
        return f"{TELEGRAM_API}{self._token}"

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

    async def send_message(
        self, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a message to a Telegram chat."""
        if self._client is None:
            raise RuntimeError("PollingEngine not started")
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        resp = await self._client.post(
            f"{self._api_base}/sendMessage", json=payload
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    async def answer_callback_query(
        self, callback_query_id: str, text: str = ""
    ) -> dict[str, Any]:
        """Answer a Telegram callback query (dismiss the loading indicator)."""
        if self._client is None:
            raise RuntimeError("PollingEngine not started")
        resp = await self._client.post(
            f"{self._api_base}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text},
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    async def edit_message_text(
        self, chat_id: int, message_id: int, text: str
    ) -> dict[str, Any]:
        """Edit an existing message (e.g. to remove keyboard after selection)."""
        if self._client is None:
            raise RuntimeError("PollingEngine not started")
        resp = await self._client.post(
            f"{self._api_base}/editMessageText",
            json={"chat_id": chat_id, "message_id": message_id, "text": text},
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    async def _fetch_updates(self) -> list[dict[str, Any]]:
        if self._client is None:
            return []
        url = f"{self._api_base}/getUpdates"
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
