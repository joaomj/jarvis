"""Event-driven OpenCode processing for Jarvis bot."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from telegram import Update

from jarvis.interaction_manager import InteractionManager
from jarvis.logging_config import get_logger
from jarvis.pinned_status import PinnedStatusManager

if TYPE_CHECKING:
    from jarvis.bot import JarvisBot

logger = get_logger(__name__)


@dataclass
class PendingPrompt:
    """Tracks one pending async prompt waiting for completion events."""

    user_id: int
    chat_id: int
    in_message_id: int
    prompt_text: str
    kind: str = "default"
    known_markdown_paths: tuple[str, ...] = ()
    is_private: bool = False


class EventProcessor:
    """Consumes OpenCode events and sends Telegram updates."""

    def __init__(self, bot: JarvisBot) -> None:
        self._bot = bot
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._pending_by_session: dict[str, PendingPrompt] = {}
        self._pinned = PinnedStatusManager()
        self._interactions = InteractionManager(
            bot=self._bot,
            send_chat=self._send_chat,
            current_chat_id=lambda: self._pinned.chat_id,
        )

    def start(self) -> None:
        """Start background event-stream task."""
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="jarvis-opencode-events")

    async def stop(self) -> None:
        """Stop background event-stream task."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def register_pending_prompt(  # noqa: PLR0913
        self,
        *,
        session_id: str,
        user_id: int,
        chat_id: int,
        in_message_id: int,
        prompt_text: str,
        session_title: str,
        kind: str = "default",
        known_markdown_paths: tuple[str, ...] = (),
        is_private: bool = False,
    ) -> None:
        """Register an async prompt waiting for assistant completion."""
        self._pending_by_session[session_id] = PendingPrompt(
            user_id=user_id,
            chat_id=chat_id,
            in_message_id=in_message_id,
            prompt_text=prompt_text,
            kind=kind,
            known_markdown_paths=known_markdown_paths,
            is_private=is_private,
        )
        self._pinned.set_chat(chat_id)
        self._pinned.on_session(session_id=session_id, session_title=session_title)

    def remember_chat(self, chat_id: int) -> None:
        """Remember chat id for proactive event-driven replies."""
        self._pinned.set_chat(chat_id)

    def has_pending_prompt(self, session_id: str) -> bool:
        """Check if a session already has an in-flight async prompt."""
        return session_id in self._pending_by_session

    async def handle_callback(self, update: Update) -> bool:
        """Handle interaction callbacks."""
        return await self._interactions.handle_callback(update)

    async def handle_interaction_input(self, update: Update, user_id: int, text: str) -> bool:
        """Handle or block text input when interaction is active."""
        return await self._interactions.handle_input(update, user_id, text)

    async def _run_loop(self) -> None:
        """Background reconnecting event stream loop."""
        while self._running:
            try:
                if not self._bot.opencode:
                    await asyncio.sleep(1.0)
                    continue

                async for event in self._bot.opencode.stream_events():
                    await self._handle_event(event)
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.warning("event_stream_retry", error=str(error))
                await asyncio.sleep(1.5)

    async def _handle_event(self, event: dict[str, Any]) -> None:
        event_type = str(event.get("type", ""))
        props = event.get("properties", {})

        if event_type == "question.asked":
            await self._interactions.on_question_asked(props)
            return
        if event_type == "permission.asked":
            await self._interactions.on_permission_asked(props)
            return
        if event_type == "session.diff":
            await self._on_session_diff(props)
            return
        if event_type == "message.updated":
            await self._on_message_updated(props)

    async def _on_message_updated(self, props: Any) -> None:
        info = props.get("info", {}) if isinstance(props, dict) else {}
        session_id = str(info.get("sessionID", ""))
        if not session_id:
            return

        model_id = str(info.get("modelID", ""))
        provider_id = str(info.get("providerID", ""))
        agent = str(info.get("agent", ""))
        model_full = f"{provider_id}/{model_id}" if provider_id and model_id else model_id
        self._pinned.on_model_agent(model=model_full, agent=agent)

        tokens = info.get("tokens", {})
        if isinstance(tokens, dict):
            cache = tokens.get("cache", {})
            cache_read = int(cache.get("read", 0)) if isinstance(cache, dict) else 0
            tokens_used = int(tokens.get("input", 0)) + cache_read
            self._pinned.on_tokens(tokens_used=tokens_used)

        await self._publish_pinned()

        pending = self._pending_by_session.get(session_id)
        if pending is None:
            return

        time_info = info.get("time", {})
        completed = isinstance(time_info, dict) and bool(time_info.get("completed"))
        if info.get("role") != "assistant" or not completed:
            return

        self._pending_by_session.pop(session_id, None)
        await self._send_completed_response(session_id, pending)
        if pending.kind == "save":
            await self._bot._on_save_completed(pending)

    async def _send_completed_response(self, session_id: str, pending: PendingPrompt) -> None:
        if not self._bot.opencode or not self._bot.app:
            return

        records = await self._bot.opencode.get_session_messages(session_id=session_id, limit=30)
        parts: list[dict[str, Any]] = []
        info: dict[str, Any] = {}
        for item in reversed(records):
            item_info = item.get("info", {})
            if item_info.get("role") == "assistant":
                parts = item.get("parts", [])
                info = item_info
                break

        response_text = "\n".join(p.get("text", "") for p in parts if p.get("type") == "text")
        model_id = info.get("modelID", "")
        provider_id = info.get("providerID", "")
        used_model = f"{provider_id}/{model_id}" if provider_id and model_id else model_id
        agent = str(info.get("agent", ""))

        turn_id: int | None = None
        if not pending.is_private:
            turn_id = self._bot.db.create_turn(
                telegram_user_id=pending.user_id,
                telegram_chat_id=pending.chat_id,
                source="opencode",
                prompt_text=pending.prompt_text,
                response_text=response_text,
                telegram_in_message_id=pending.in_message_id,
                opencode_session_id=session_id,
                model_full=used_model,
                agent=agent,
            )
        await self._bot._send_response_to_chat(
            chat_id=pending.chat_id,
            reply_to_message_id=pending.in_message_id,
            parts=parts,
            turn_id=turn_id,
        )

    async def _on_session_diff(self, props: Any) -> None:
        if not isinstance(props, dict):
            return
        diff = props.get("diff", [])
        if isinstance(diff, list):
            self._pinned.on_diff(diff)
            await self._publish_pinned()

    async def _publish_pinned(self) -> None:
        if self._bot.app is None:
            return
        await self._pinned.publish(self._bot.app.bot)

    async def _send_chat(self, chat_id: int, text: str, reply_markup: Any | None = None) -> None:
        if self._bot.app is None:
            return
        await self._bot.app.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
