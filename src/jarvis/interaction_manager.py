"""Interaction guard/state management for OpenCode questions and permissions."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from jarvis.bot import JarvisBot

ALLOWED_DURING_INTERACTION = ("/help", "/status", "/stop")


@dataclass
class QuestionInteraction:
    """Active question request awaiting user response."""

    request_id: str
    session_id: str
    questions: list[dict[str, Any]]


@dataclass
class PermissionInteraction:
    """Active permission request awaiting user response."""

    request_id: str
    session_id: str
    permission: str
    patterns: list[str]


class InteractionManager:
    """Owns interactive state and blocks unrelated inputs while active."""

    def __init__(
        self,
        bot: JarvisBot,
        send_chat: Callable[[int, str, Any | None], Awaitable[None]],
        current_chat_id: Callable[[], int | None],
    ) -> None:
        self._bot = bot
        self._send_chat = send_chat
        self._current_chat_id = current_chat_id
        self._question_by_user: dict[int, QuestionInteraction] = {}
        self._permission_by_user: dict[int, PermissionInteraction] = {}

    async def handle_callback(self, update: Update) -> bool:  # noqa: PLR0911
        """Handle permission callbacks. Returns True when consumed."""
        callback = update.callback_query
        if callback is None or not callback.data:
            return False
        if not callback.data.startswith("perm:"):
            return False

        user_id = callback.from_user.id
        if not self._bot._is_authorized(user_id):
            await callback.answer()
            return True

        parts = callback.data.split(":")
        if len(parts) != 3:  # noqa: PLR2004
            await callback.answer("Invalid permission action")
            return True

        request_id = parts[1]
        reply = parts[2]
        if reply not in {"once", "always", "reject"}:
            await callback.answer("Invalid permission action")
            return True

        if not self._bot.opencode:
            await callback.answer("OpenCode not initialized")
            return True

        await self._bot.opencode.permission_reply(request_id=request_id, reply=reply)
        self._permission_by_user.pop(user_id, None)
        await callback.answer(f"Permission {reply}")
        with suppress(Exception):
            await callback.edit_message_reply_markup(reply_markup=None)
        return True

    async def handle_input(  # noqa: PLR0911
        self, update: Update, user_id: int, text: str
    ) -> bool:
        """Handle or block text input when interaction is active."""
        msg = update.effective_message
        if msg is None:
            return False
        chat_id = msg.chat_id

        if any(text.startswith(prefix) for prefix in ALLOWED_DURING_INTERACTION):
            return False

        if user_id in self._permission_by_user:
            await self._send_chat(
                chat_id,
                "A permission request is pending. Use the buttons to allow or reject.",
                None,
            )
            return True

        question = self._question_by_user.get(user_id)
        if question is None:
            return False

        if text.startswith("/cancel"):
            if self._bot.opencode:
                await self._bot.opencode.question_reject(question.request_id)
            self._question_by_user.pop(user_id, None)
            await self._send_chat(chat_id, "Question rejected.", None)
            return True

        if text.startswith("/answer "):
            answers = self._parse_answer_payload(text[len("/answer ") :])
            if not answers:
                await self._send_chat(
                    chat_id,
                    "Invalid answer format. Use /answer label[,label][;label].",
                    None,
                )
                return True

            if self._bot.opencode:
                await self._bot.opencode.question_reply(question.request_id, answers)
            self._question_by_user.pop(user_id, None)
            await self._send_chat(chat_id, "Question answered.", None)
            return True

        await self._send_chat(chat_id, "Question pending. Use /answer ... or /cancel.", None)
        return True

    async def on_question_asked(self, props: Any) -> None:
        """Store question interaction and notify user."""
        if not isinstance(props, dict):
            return

        request_id = str(props.get("id", ""))
        session_id = str(props.get("sessionID", ""))
        questions = props.get("questions", [])
        if not request_id or not isinstance(questions, list):
            return

        user_id = self._bot.settings.telegram_user_id
        self._question_by_user[user_id] = QuestionInteraction(request_id, session_id, questions)
        chat_id = self._current_chat_id()
        if chat_id is not None:
            await self._send_chat(chat_id, self._format_question_prompt(questions), None)

    async def on_permission_asked(self, props: Any) -> None:
        """Store permission interaction and send inline buttons."""
        if not isinstance(props, dict):
            return

        request_id = str(props.get("id", ""))
        session_id = str(props.get("sessionID", ""))
        permission = str(props.get("permission", ""))
        patterns = props.get("patterns", [])
        if not request_id:
            return

        user_id = self._bot.settings.telegram_user_id
        self._permission_by_user[user_id] = PermissionInteraction(
            request_id=request_id,
            session_id=session_id,
            permission=permission,
            patterns=patterns if isinstance(patterns, list) else [],
        )

        chat_id = self._current_chat_id()
        if chat_id is None:
            return

        prompt = (
            f"Permission requested: {permission}\n"
            f"Patterns: {', '.join(self._permission_by_user[user_id].patterns) or '-'}"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Allow once", callback_data=f"perm:{request_id}:once")],
                [InlineKeyboardButton("Always allow", callback_data=f"perm:{request_id}:always")],
                [InlineKeyboardButton("Reject", callback_data=f"perm:{request_id}:reject")],
            ]
        )
        await self._send_chat(chat_id, prompt, keyboard)

    @staticmethod
    def _parse_answer_payload(raw: str) -> list[list[str]]:
        segments = [segment.strip() for segment in raw.split(";") if segment.strip()]
        answers = [
            [label.strip() for label in segment.split(",") if label.strip()] for segment in segments
        ]
        return [labels for labels in answers if labels]

    @staticmethod
    def _format_question_prompt(questions: list[dict[str, Any]]) -> str:
        lines = [
            "Agent asked for input.",
            "Reply with: /answer label[,label][;label] or /cancel",
            "",
        ]
        for idx, question in enumerate(questions, start=1):
            text = str(question.get("question", "Question"))
            options = question.get("options", [])
            lines.append(f"Q{idx}: {text}")
            if isinstance(options, list):
                labels = [
                    str(option.get("label", "")) for option in options if isinstance(option, dict)
                ]
                if labels:
                    lines.append("Options: " + ", ".join(labels))
            lines.append("")
        return "\n".join(lines).strip()
