"""Telegram gateway: polling, message routing, streaming responses."""
from __future__ import annotations

import uuid
from typing import Any

from src.agent import AlfredAgent
from src.config import Settings
from src.conversation import ConversationStore
from src.logging_config import correlation_id, get_logger
from src.models import AVAILABLE_MODELS, get_display_name
from src.polling_engine import PollingEngine
from src.skill_loader import SkillLoader

logger = get_logger(__name__)

PRIVATE_TRUNCATE_LEN = 80


def generate_correlation_id() -> str:
    return str(uuid.uuid4())


def _build_model_keyboard() -> dict[str, Any]:
    """Build Telegram InlineKeyboardMarkup for model selection."""
    cols = 2
    buttons: list[list[dict[str, str]]] = []
    row: list[dict[str, str]] = []
    for m in AVAILABLE_MODELS:
        row.append({"text": m.display, "callback_data": f"model:{m.id}"})
        if len(row) == cols:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return {"inline_keyboard": buttons}


class TelegramGateway:
    def __init__(
        self,
        agent: AlfredAgent,
        skill_loader: SkillLoader,
        conversation: ConversationStore,
        polling: PollingEngine,
        settings: Settings,
    ) -> None:
        self.agent = agent
        self.skill_loader = skill_loader
        self.conversation = conversation
        self.polling = polling
        self.settings = settings
        self._sessions: dict[int, str] = {}

    def _get_or_create_session(self, user_id: int) -> str:
        if user_id not in self._sessions:
            self._sessions[user_id] = self.conversation.new_session()
        return self._sessions[user_id]

    async def handle_update(self, update: dict[str, Any]) -> None:
        """Route an incoming Telegram update (message or callback query)."""
        if "callback_query" in update:
            await self._handle_callback(update["callback_query"])
            return

        message = update.get("message") or {}
        text: str | None = message.get("text")
        user_id: int | None = (message.get("from") or {}).get("id")
        chat_id: int | None = (message.get("chat") or {}).get("id")

        if not text or not user_id or not chat_id:
            return
        if user_id != self.settings.telegram_user_id:
            return

        await self._handle_message(text, user_id, chat_id)

    async def _handle_message(
        self, text: str, user_id: int, chat_id: int
    ) -> None:
        cid = generate_correlation_id()
        correlation_id.set(cid)
        session_id = self._get_or_create_session(user_id)

        is_private = text.startswith("/private")
        log_text = (
            text[:PRIVATE_TRUNCATE_LEN] + "..." if is_private and len(text) > PRIVATE_TRUNCATE_LEN
            else text
        )
        logger.info(
            "incoming_message",
            extra={"cid": cid, "user_id": user_id, "text": log_text},
        )

        self.conversation.add_message(session_id, "user", text, cid)

        # /model — show inline keyboard
        if text.startswith("/model"):
            await self.polling.send_message(
                chat_id, "Select model:", reply_markup=_build_model_keyboard()
            )
            return

        # /command — skill dispatch
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            command = parts[0][1:]
            args = parts[1] if len(parts) > 1 else ""
            try:
                skill = self.skill_loader.load_skill(command)
            except FileNotFoundError:
                await self.polling.send_message(
                    chat_id, f"Unknown command: /{command}"
                )
                return
            full_response = ""
            async for chunk in self.agent.run_stream(args or text, skill=skill):
                full_response += chunk
            if full_response:
                self.conversation.add_message(
                    session_id, "assistant", full_response, cid
                )
                await self.polling.send_message(chat_id, full_response)
            return

        # Skill suggestion
        suggestion = self.agent.find_matching_skill(text)
        if suggestion:
            await self.polling.send_message(
                chat_id,
                f"Try /{suggestion} for that. Send it and I'll help.",
            )
            return

        # Normal chat
        full_response = ""
        async for chunk in self.agent.run_stream(text):
            full_response += chunk
        if full_response:
            self.conversation.add_message(
                session_id, "assistant", full_response, cid
            )
            await self.polling.send_message(chat_id, full_response)

        logger.info(
            "outgoing_response",
            extra={"cid": cid, "response_len": len(full_response)},
        )

    async def _handle_callback(self, callback_query: dict[str, Any]) -> None:
        """Handle inline keyboard callback (model selection)."""
        cid = generate_correlation_id()
        correlation_id.set(cid)

        data: str = callback_query.get("data", "")
        cb_id: str = callback_query["id"]
        message = callback_query.get("message") or {}
        chat_id: int | None = (message.get("chat") or {}).get("id")
        msg_id: int | None = message.get("message_id")

        if not data.startswith("model:"):
            await self.polling.answer_callback_query(cb_id)
            return

        model_id = data[len("model:"):]
        display = get_display_name(model_id)

        logger.info("model_change", extra={"cid": cid, "model": model_id})

        self.agent.update_model(model_id, self.settings.opencode_go_api_key)

        if chat_id and msg_id:
            await self.polling.edit_message_text(
                chat_id, msg_id, f"Model switched to {display}"
            )
        await self.polling.answer_callback_query(cb_id, f"Switched to {display}")
