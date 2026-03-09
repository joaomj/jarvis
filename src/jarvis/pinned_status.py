"""Pinned status message manager for Telegram chat."""

from __future__ import annotations

import time
from typing import Any

from jarvis.logging_config import get_logger

logger = get_logger(__name__)

PUBLISH_DEBOUNCE_SECONDS = 1.5


class PinnedStatusManager:
    """Maintains a single pinned status message per chat."""

    def __init__(self) -> None:
        self.chat_id: int | None = None
        self.message_id: int | None = None
        self.session_id: str | None = None
        self.session_title: str = "No active session"
        self.model: str = "unknown"
        self.agent: str = "unknown"
        self.tokens_used: int = 0
        self.changed_files: list[dict[str, Any]] = []
        self._last_publish_ts: float = 0.0

    def set_chat(self, chat_id: int) -> None:
        """Set current chat id for pinned status updates."""
        self.chat_id = chat_id

    def on_session(self, session_id: str, session_title: str) -> None:
        """Initialize status state for a new active session."""
        self.session_id = session_id
        self.session_title = session_title
        self.tokens_used = 0
        self.changed_files = []

    def on_model_agent(self, model: str | None, agent: str | None) -> None:
        """Update model and agent labels."""
        if model:
            self.model = model
        if agent:
            self.agent = agent

    def on_tokens(self, tokens_used: int) -> None:
        """Update approximate context token usage."""
        if tokens_used >= 0:
            self.tokens_used = tokens_used

    def on_diff(self, diff: list[dict[str, Any]]) -> None:
        """Update changed-files list from session.diff event."""
        self.changed_files = diff

    async def publish(self, bot: Any, force: bool = False) -> None:
        """Create or update pinned status message with debounce."""
        if self.chat_id is None:
            return

        now = time.monotonic()
        if not force and now - self._last_publish_ts < PUBLISH_DEBOUNCE_SECONDS:
            return

        text = self._render()
        try:
            if self.message_id is None:
                sent = await bot.send_message(self.chat_id, text)
                self.message_id = sent.message_id
                await bot.pin_chat_message(
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    disable_notification=True,
                )
                logger.info("status_pinned", chat_id=self.chat_id, message_id=self.message_id)
            else:
                await bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    text=text,
                )
        except Exception as error:
            logger.debug("status_publish_skipped", error=str(error))

        self._last_publish_ts = now

    def _render(self) -> str:
        changed_count = len(self.changed_files)
        lines = [
            f"Session: {self.session_title}",
            f"Model: {self.model}",
            f"Agent: {self.agent}",
            f"Context: ~{self.tokens_used} tokens",
            f"Changed files: {changed_count}",
        ]
        if changed_count:
            for item in self.changed_files[:8]:
                file_path = str(item.get("file", ""))
                adds = int(item.get("additions", 0) or 0)
                dels = int(item.get("deletions", 0) or 0)
                lines.append(f"- {file_path} (+{adds}/-{dels})")
            remaining = changed_count - 8
            if remaining > 0:
                lines.append(f"- ... and {remaining} more")
        return "\n".join(lines)
