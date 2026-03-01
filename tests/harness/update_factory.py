"""Typed update builders for message/callback/document scenarios."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from tests.harness.fake_telegram import FakeTelegramBot


@dataclass(frozen=True)
class FakeTelegramUser:
    """Minimal Telegram user representation."""

    id: int


@dataclass
class FakeTelegramMessage:
    """Minimal Telegram message representation."""

    chat_id: int
    message_id: int
    text: str | None = None
    caption: str | None = None
    document: Any | None = None
    bot: FakeTelegramBot | None = None

    async def reply_text(
        self,
        text: str,
        parse_mode: str | None = None,
        reply_markup: Any | None = None,
    ) -> SimpleNamespace:
        """Mirror message.reply_text behavior via fake bot."""
        if self.bot is None:
            return SimpleNamespace(message_id=self.message_id + 1, text=text)
        return await self.bot.send_message(
            chat_id=self.chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            reply_to_message_id=self.message_id,
        )


@dataclass
class FakeCallbackQuery:
    """Minimal callback query representation."""

    data: str
    from_user: FakeTelegramUser
    message: FakeTelegramMessage
    bot: FakeTelegramBot | None = None
    answers: list[str] = field(default_factory=list)

    async def answer(self, text: str | None = None) -> None:
        """Capture callback answers."""
        self.answers.append(text or "")

    async def edit_message_reply_markup(self, reply_markup: Any | None = None) -> None:
        """Capture callback keyboard updates."""
        if self.bot is None:
            return
        await self.bot.edit_message_reply_markup(
            chat_id=self.message.chat_id,
            message_id=self.message.message_id,
            reply_markup=reply_markup,
        )


@dataclass
class FakeUpdate:
    """Telegram update with effective_* accessors."""

    update_id: int
    effective_user: FakeTelegramUser | None
    effective_message: FakeTelegramMessage | None
    callback_query: FakeCallbackQuery | None = None


def build_message_update(
    *,
    user_id: int,
    chat_id: int,
    text: str,
    message_id: int = 1,
    update_id: int = 1,
    bot: FakeTelegramBot | None = None,
) -> FakeUpdate:
    """Build deterministic update for inbound text messages."""
    user = FakeTelegramUser(id=user_id)
    message = FakeTelegramMessage(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        bot=bot,
    )
    return FakeUpdate(
        update_id=update_id,
        effective_user=user,
        effective_message=message,
    )


def build_document_update(
    *,
    user_id: int,
    chat_id: int,
    file_id: str,
    file_unique_id: str,
    file_name: str,
    mime_type: str,
    caption: str | None = None,
    message_id: int = 1,
    update_id: int = 1,
    bot: FakeTelegramBot | None = None,
) -> FakeUpdate:
    """Build deterministic update with an attached document."""
    user = FakeTelegramUser(id=user_id)
    document = SimpleNamespace(
        file_id=file_id,
        file_unique_id=file_unique_id,
        file_name=file_name,
        mime_type=mime_type,
    )
    message = FakeTelegramMessage(
        chat_id=chat_id,
        message_id=message_id,
        text=None,
        caption=caption,
        document=document,
        bot=bot,
    )
    return FakeUpdate(
        update_id=update_id,
        effective_user=user,
        effective_message=message,
    )


def build_callback_update(
    *,
    user_id: int,
    chat_id: int,
    data: str,
    message_id: int = 1,
    update_id: int = 1,
    bot: FakeTelegramBot | None = None,
) -> FakeUpdate:
    """Build deterministic callback update."""
    user = FakeTelegramUser(id=user_id)
    message = FakeTelegramMessage(
        chat_id=chat_id,
        message_id=message_id,
        text="callback",
        bot=bot,
    )
    callback = FakeCallbackQuery(data=data, from_user=user, message=message, bot=bot)
    return FakeUpdate(
        update_id=update_id,
        effective_user=user,
        effective_message=message,
        callback_query=callback,
    )
