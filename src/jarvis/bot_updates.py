"""Update processing mixin for ``JarvisBot``."""

# mypy: ignore-errors
from __future__ import annotations

import re
from typing import Any

from telegram import Update

from jarvis.auto_retrieval import retrieve_context
from jarvis.command_router import is_command_blocked
from jarvis.logging_config import get_logger
from jarvis.opencode_client import OpenCodeError
from jarvis.session_utils import extract_session_id_from_new_response
from jarvis.utils import is_url_only

logger = get_logger(__name__)

PRIVATE_PREFIX_RE = re.compile(r"^(?:<private>\s*|private:\s*|\/private\s+)", re.IGNORECASE)


class BotUpdateMixin:
    """Methods that process inbound Telegram updates."""

    def _is_private_intent(self, text: str) -> bool:
        """Detect private-turn prefix markers."""
        return bool(PRIVATE_PREFIX_RE.match(text.strip()))

    def _strip_private_marker(self, text: str) -> str:
        """Remove private prefix marker from user text."""
        return PRIVATE_PREFIX_RE.sub("", text.strip(), count=1).strip()

    async def _process_input(
        self,
        update: Update,
        user_id: int,
        session_id: str,
        text: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
        """Process message text and return OpenCode response."""
        is_private = self._is_private_intent(text)
        processed_text = self._strip_private_marker(text) if is_private else text

        if is_url_only(processed_text) and update.effective_message:
            await update.effective_message.reply_text(
                f"💡 To save this URL, use `/save {processed_text}`"
            )
            return None

        if await self.events.handle_interaction_input(update, user_id, processed_text):
            return None

        if not self.opencode:
            raise RuntimeError("OpenCode not initialized")

        if processed_text.startswith("/") or processed_text.startswith("!"):
            return await self._process_command(update, user_id, session_id, processed_text)

        return await self._process_regular_message(
            update, user_id, session_id, processed_text, is_private
        )

    async def _process_command(
        self,
        update: Update,
        user_id: int,
        session_id: str,
        processed_text: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
        """Process command messages."""
        parts = processed_text[1:].split(maxsplit=1)
        command = parts[0]
        arguments = parts[1] if len(parts) > 1 else ""

        block_reason = is_command_blocked(command)
        if block_reason:
            await self._send_feedback_message(
                update,
                user_id,
                block_reason,
                source="command",
                prompt_text=f"[command] {command}",
                parse_mode="HTML",
            )
            return None

        response_parts, info = await self.opencode.send_command(session_id, command, arguments)

        if command == "new" and self.session_manager:
            await self._sync_new_session(user_id, response_parts)

        return self._prepare_command_response(response_parts, info, session_id, user_id)

    async def _sync_new_session(self, user_id: int, response_parts: list[dict[str, Any]]) -> None:
        """Sync session with SessionManager after /new command."""
        new_session_id = extract_session_id_from_new_response(response_parts)
        if new_session_id:
            self.session_manager.set_session(user_id, new_session_id)
            logger.info(
                "session_synced_after_new_command",
                new_session_id=new_session_id,
                user_id=user_id,
            )

    def _prepare_command_response(
        self,
        response_parts: list[dict[str, Any]],
        info: dict[str, Any],
        session_id: str,
        user_id: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Prepare and log command response."""
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

    async def _process_regular_message(
        self,
        update: Update,
        user_id: int,
        session_id: str,
        processed_text: str,
        is_private: bool,
    ) -> None:
        """Process regular (non-command) messages."""
        if self.events.has_pending_prompt(session_id):
            await self._send_feedback_message(
                update,
                user_id,
                "I am still processing your previous request. Please wait for completion.",
                source="status",
                prompt_text=processed_text,
            )
            return None

        system_context: str | None = None
        if not is_private and self.context_store:
            try:
                opencode_db = str(
                    __import__("pathlib").Path(self.settings.vault_root).expanduser()
                    / "raw"
                    / "opencode"
                    / "opencode.db"
                )
                ctx = retrieve_context(
                    self.context_store,
                    opencode_db,
                    processed_text,
                )
                if ctx.sources_used > 0:
                    system_context = ctx.system_prefix
                    logger.debug(
                        "auto_context_retrieved",
                        sources=ctx.sources_used,
                        chars=len(ctx.system_prefix),
                    )
            except Exception as error:
                logger.warning("auto_retrieval_failed", error=str(error))

        await self.opencode.prompt_async(session_id, processed_text, system=system_context)
        self.events.register_pending_prompt(
            session_id=session_id,
            user_id=user_id,
            chat_id=update.effective_message.chat_id,
            in_message_id=update.effective_message.message_id,
            prompt_text=processed_text,
            session_title=f"jarvis-session-{session_id[:8]}",
            is_private=is_private,
        )

        if is_private:
            await update.effective_message.reply_text(
                "Private request received. I will reply without storing this turn."
            )
        else:
            await self._send_feedback_message(
                update,
                user_id,
                "Working on it... I will send the full response when OpenCode finishes.",
                source="status",
                prompt_text=processed_text,
            )
        return None

    async def _handle_update(self, update: Update) -> None:  # noqa: PLR0911, PLR0912
        """Process single update from polling."""
        if update.callback_query:
            if await self.events.handle_callback(update):
                return
            await self._handle_feedback_callback(update)
            return
        if not update.effective_user or not update.effective_message:
            return

        user_id = update.effective_user.id
        text = update.effective_message.text or update.effective_message.caption or ""
        self.events.remember_chat(update.effective_message.chat_id)
        if not self._is_authorized(user_id):
            logger.warning("unauthorized", user_id=user_id, text=text[:50])
            return

        attachment_result = await self._ingest_attachment_if_present(update)
        if await self._handle_attachment_only_message(update, attachment_result, text):
            return

        is_private = self._is_private_intent(text)
        self._log_incoming_message(user_id, text, persist=not is_private)

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

    def _log_incoming_message(self, user_id: int, text: str, *, persist: bool = True) -> None:
        """Log incoming message and optionally audit it."""
        if persist and self.settings.enable_message_audit:
            self.db.log_message(user_id, "in", text)
        logger.info("message_received", user_id=user_id, text=text[:50], persisted=persist)

    async def _handle_attachment_only_message(
        self,
        update: Update,
        attachment_result: Any,
        text: str,
    ) -> bool:
        """Reply immediately when message contains only an attachment."""
        if not attachment_result or text.strip() or not update.effective_message:
            return False

        status = f"Attachment saved at {attachment_result.raw_path}."
        if attachment_result.markdown_path is not None:
            status = (
                "Attachment saved and indexed.\n"
                f"Raw: {attachment_result.raw_path}\n"
                f"Indexed: {attachment_result.markdown_path}"
            )
        await update.effective_message.reply_text(status)
        return True
