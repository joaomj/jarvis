"""Update processing mixin for ``JarvisBot``."""

# mypy: ignore-errors

from __future__ import annotations

from typing import Any

from telegram import Update

from jarvis.logging_config import get_logger
from jarvis.opencode_client import OpenCodeError

logger = get_logger(__name__)


class BotUpdateMixin:
    """Methods that process inbound Telegram updates."""

    async def _process_input(  # noqa: PLR0911
        self,
        update: Update,
        user_id: int,
        session_id: str,
        text: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
        """Process message text and return OpenCode response."""
        if self.model_selector and self.model_selector.is_awaiting_selection(user_id):
            msg = update.effective_message
            if msg:
                response = await self.model_selector.handle_selection(user_id, text)
                await self._send_feedback_message(
                    update,
                    user_id,
                    response,
                    source="model_select",
                    prompt_text=f"[model selection] {text}",
                    parse_mode="HTML",
                )
            return None

        if self._is_bookmark_query(text) and await self._handle_bookmark_query(update, text):
            return None

        if await self.events.handle_interaction_input(update, user_id, text):
            return None

        if not self.opencode:
            raise RuntimeError("OpenCode not initialized")

        if text.startswith("!"):
            parts = text[1:].split(maxsplit=1)
            command = parts[0]
            arguments = parts[1] if len(parts) > 1 else ""
            if command in {"models", "favmodels"}:
                await self._start_model_selection(update, user_id)
                return None
            response_parts, info = await self.opencode.send_command(session_id, command, arguments)
        else:
            if self.events.has_pending_prompt(session_id):
                await self._send_feedback_message(
                    update,
                    user_id,
                    "I am still processing your previous request. Please wait for completion.",
                    source="status",
                    prompt_text=text,
                )
                return None

            selected_model = None
            if self.model_selector:
                selected_model = self.model_selector.get_model_for_user(user_id)

            await self.opencode.prompt_async(session_id, text, model=selected_model)
            self.events.register_pending_prompt(
                session_id=session_id,
                user_id=user_id,
                chat_id=update.effective_message.chat_id,
                in_message_id=update.effective_message.message_id,
                prompt_text=text,
                session_title=f"jarvis-session-{session_id[:8]}",
            )
            await self._send_feedback_message(
                update,
                user_id,
                "Working on it... I will send the full response when OpenCode finishes.",
                source="status",
                prompt_text=text,
            )
            return None

        content_text = "\n".join(
            p.get("text", "") for p in response_parts if p.get("type") == "text"
        )
        used_model = info.get("modelID", "default")
        try:
            self.db.log_response(session_id, user_id, used_model, content_text)
        except Exception as error:
            logger.warning(
                "response_logging_failed",
                session_id=session_id,
                user_id=user_id,
                model=used_model,
                error=str(error),
            )

        return response_parts, info

    async def _handle_update(self, update: Update) -> None:  # noqa: PLR0911
        """Process single update from polling."""
        if update.callback_query:
            if await self.events.handle_callback(update):
                return
            await self._handle_feedback_callback(update)
            return
        if not update.effective_user or not update.effective_message:
            return

        user_id = update.effective_user.id
        text = update.effective_message.text or ""
        self.events.remember_chat(update.effective_message.chat_id)
        if not self._is_authorized(user_id):
            logger.warning("unauthorized", user_id=user_id, text=text[:50])
            return

        self._log_incoming_message(user_id, text)

        if self.settings.x_client_id and self._should_sync():
            try:
                await self._run_bookmark_sync()
            except Exception as error:
                logger.error("auto_sync_failed", error=str(error))

        if not self.session_manager:
            await self._handle_error(update, "Session manager not initialized", user_id, text)
            return

        session_id, is_new_session = await self.session_manager.get_or_create_session(user_id)
        if not self._health_probe_sent:
            self._health_probe_sent = True
            await self._send_daily_health_probe(update, user_id, session_id, is_new_session)
            return

        try:
            result = await self._process_input(update, user_id, session_id, text)
            if result is None:
                return
            await self._handle_opencode_result(update, user_id, session_id, text, *result)
        except OpenCodeError as error:
            handled = await self._try_model_fallback(update, user_id, session_id, text, error)
            if not handled:
                logger.error("opencode_error", error=str(error), status_code=error.status_code)
                await self._handle_error(update, f"OpenCode error: {error}", user_id, text)
        except Exception as error:
            logger.error("handler_error", error=str(error), exc_info=True)
            await self._handle_error(update, f"Unexpected error: {str(error)[:200]}", user_id, text)

    def _log_incoming_message(self, user_id: int, text: str) -> None:
        """Log incoming message and optionally audit it."""
        if self.settings.enable_message_audit:
            self.db.log_message(user_id, "in", text)
        logger.info("message_received", user_id=user_id, text=text[:50])

    async def _handle_opencode_result(  # noqa: PLR0913
        self,
        update: Update,
        user_id: int,
        session_id: str,
        prompt_text: str,
        parts: list[dict[str, Any]],
        info: dict[str, Any],
    ) -> None:
        """Persist and deliver successful OpenCode response."""
        response_text = "\n".join(
            part.get("text", "") for part in parts if part.get("type") == "text"
        )
        model_id = info.get("modelID", "")
        provider_id = info.get("providerID", "")
        agent = info.get("agent", "")
        used_model = f"{provider_id}/{model_id}" if provider_id else model_id
        if self.session_manager and used_model:
            self.session_manager.update_session_model(session_id, used_model)

        turn_id = self.db.create_turn(
            telegram_user_id=user_id,
            telegram_chat_id=update.effective_message.chat_id,
            source="opencode",
            prompt_text=prompt_text,
            response_text=response_text,
            telegram_in_message_id=update.effective_message.message_id,
            opencode_session_id=session_id,
            model_full=used_model,
            agent=agent,
        )
        await self._send_response(update, parts, turn_id)
        logger.info(
            "response_sent", parts=len(parts), model=used_model, agent=agent, turn_id=turn_id
        )

        if self.settings.enable_message_audit:
            for part in parts:
                if part.get("type") == "text":
                    self.db.log_message(user_id, "out", str(part.get("text", ""))[:200])

    async def _try_model_fallback(
        self,
        update: Update,
        user_id: int,
        session_id: str,
        text: str,
        error: OpenCodeError,
    ) -> bool:
        """Attempt fallback model for model/provider errors."""
        error_str = str(error).lower()
        should_fallback = (
            "model" in error_str or "provider" in error_str or "not found" in error_str
        ) and self.models.get_count() > 0
        if not should_fallback:
            return False

        fallback_model = self.models.get_models()[0]
        logger.warning(
            "model_fallback_activated",
            error=str(error),
            fallback_model=fallback_model,
            user_id=user_id,
        )

        try:
            if not self.opencode:
                raise RuntimeError("OpenCode not initialized")
            parts, info = await self.opencode.send_message(session_id, text, model=fallback_model)
            await self._handle_opencode_result(update, user_id, session_id, text, parts, info)
            logger.info("fallback_response_sent", fallback=True)
            return True
        except Exception as fallback_error:
            logger.error(
                "fallback_failed",
                original_error=str(error),
                fallback_error=str(fallback_error),
                user_id=user_id,
            )
            await self._handle_error(
                update,
                f"OpenCode error (fallback also failed): {error}",
                user_id,
                text,
            )
            return True
