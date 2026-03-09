"""Deterministic fake Telegram API primitives for tests."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any


@dataclass(frozen=True)
class SentMessage:
    """Captured send_message call."""

    message_id: int
    chat_id: int
    text: str
    reply_to_message_id: int | None
    parse_mode: str | None
    reply_markup: Any | None


@dataclass(frozen=True)
class EditedReplyMarkup:
    """Captured edit_message_reply_markup call."""

    chat_id: int
    message_id: int
    reply_markup: Any | None


@dataclass(frozen=True)
class EditedMessageText:
    """Captured edit_message_text call."""

    chat_id: int
    message_id: int
    text: str


@dataclass(frozen=True)
class PinnedMessage:
    """Captured pin_chat_message call."""

    chat_id: int
    message_id: int
    disable_notification: bool


class FakeTelegramFile:
    """Fake Telegram file payload."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    async def download_as_bytearray(self) -> bytearray:
        """Return deterministic file bytes."""
        return bytearray(self._data)


class FakeTelegramBot:
    """In-memory fake Telegram bot API."""

    def __init__(self) -> None:
        self.sent_messages: list[SentMessage] = []
        self.edited_reply_markups: list[EditedReplyMarkup] = []
        self.edited_texts: list[EditedMessageText] = []
        self.pinned_messages: list[PinnedMessage] = []
        self._files: dict[str, bytes] = {}
        self._next_message_id = 100

    def add_file(self, file_id: str, data: bytes) -> None:
        """Register fake file bytes by file id."""
        self._files[file_id] = data

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
        parse_mode: str | None = None,
        reply_markup: Any | None = None,
    ) -> SimpleNamespace:
        """Record sent message and return Telegram-like response."""
        message = SentMessage(
            message_id=self._next_message_id,
            chat_id=chat_id,
            text=text,
            reply_to_message_id=reply_to_message_id,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        self.sent_messages.append(message)
        self._next_message_id += 1
        return SimpleNamespace(message_id=message.message_id, chat_id=chat_id, text=text)

    async def edit_message_reply_markup(
        self,
        *,
        chat_id: int,
        message_id: int,
        reply_markup: Any | None,
    ) -> None:
        """Record reply-markup edits."""
        self.edited_reply_markups.append(
            EditedReplyMarkup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup,
            )
        )

    async def edit_message_text(self, *, chat_id: int, message_id: int, text: str) -> None:
        """Record message text edits."""
        self.edited_texts.append(
            EditedMessageText(chat_id=chat_id, message_id=message_id, text=text)
        )

    async def pin_chat_message(
        self,
        *,
        chat_id: int,
        message_id: int,
        disable_notification: bool,
    ) -> None:
        """Record pinned status message calls."""
        self.pinned_messages.append(
            PinnedMessage(
                chat_id=chat_id,
                message_id=message_id,
                disable_notification=disable_notification,
            )
        )

    async def get_file(self, file_id: str) -> FakeTelegramFile:
        """Return fake file object."""
        return FakeTelegramFile(self._files[file_id])


class FakeTelegramApp:
    """Fake telegram.ext.Application subset used by bot code."""

    def __init__(self, bot: FakeTelegramBot | None = None) -> None:
        self.bot = bot or FakeTelegramBot()
