"""Telegram bot implementation with polling.

Thin passthrough bridge between Telegram and OpenCode Server.
"""

from datetime import date
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application

from jarvis.bookmarks.sync import BookmarkSync
from jarvis.config import Settings
from jarvis.database import Database
from jarvis.formatter import ResponseFormatter
from jarvis.handlers.bookmarks import query_bookmarks
from jarvis.logging_config import get_logger
from jarvis.model_selector import ModelSelector
from jarvis.models_manager import ModelsManager
from jarvis.opencode_client import OpenCodeClient, OpenCodeError
from jarvis.polling_engine import PollingEngine
from jarvis.session_manager import SessionManager

logger = get_logger(__name__)

BOOKMARK_KEYWORDS = {
    "saved",
    "bookmarked",
    "my tweets",
    "my bookmarks",
    "saved posts",
    "save",
}

TIME_EXPRESSIONS = {
    "last week",
    "past week",
    "last month",
    "past month",
    "yesterday",
    "today",
    "recent",
}


def build_feedback_keyboard(turn_id: int) -> InlineKeyboardMarkup:
    """Build inline keyboard with thumbs up/down buttons.

    Args:
        turn_id: The turn record ID for callback data.

    Returns:
        InlineKeyboardMarkup with thumbs up/down buttons.
    """
    keyboard = [
        [
            InlineKeyboardButton("👍", callback_data=f"fb:{turn_id}:up"),
            InlineKeyboardButton("👎", callback_data=f"fb:{turn_id}:down"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


class JarvisBot:
    """Telegram bot with polling support."""

    def __init__(self, settings: Settings):
        """Initialize bot."""
        self.settings = settings
        self.formatter = ResponseFormatter()
        self.opencode: OpenCodeClient | None = None
        self.session_manager: SessionManager | None = None
        self.model_selector: ModelSelector | None = None
        self.app: Application | None = None
        self.polling: PollingEngine | None = None
        self.db = Database(
            settings.database_path,
            message_content_max_length=settings.db_message_content_max_length,
            response_cleanup_days=settings.db_response_cleanup_days,
        )
        self.models = ModelsManager(settings.favorite_models_path)
        self._running = False
        self._health_probe_sent = False

        logger.info(
            "bot_initialized",
            user_id=settings.telegram_user_id,
            polling_interval=settings.telegram_polling_interval,
        )

    async def initialize(self) -> None:
        """Initialize bot and OpenCode client."""
        self.opencode = OpenCodeClient(
            self.settings.opencode_url,
            self.settings.opencode_server_password,
            log_level=self.settings.log_level,
        )

        healthy, reason = await self.opencode.health_check()
        if not healthy:
            error_msg = f"OpenCode Server is not healthy: {reason}"
            logger.critical("opencode_unhealthy", reason=reason)
            raise RuntimeError(error_msg)

        logger.info("opencode_connected", healthy=healthy, reason=reason)

        self.session_manager = SessionManager(self.opencode, self.db)
        self.model_selector = ModelSelector(self.db, self.models)

        self.db.add_user(self.settings.telegram_user_id)

        deleted = self.db.cleanup_old_responses()
        if deleted > 0:
            logger.info("response_cleanup_complete", deleted=deleted)

        self.app = (
            Application.builder()
            .token(self.settings.telegram_bot_id)
            .build()
        )

        self.polling = PollingEngine(
            self.app,
            interval=self.settings.telegram_polling_interval,
            timeout=self.settings.telegram_polling_timeout,
            max_backoff_level=self.settings.polling_max_backoff_level,
            max_backoff_seconds=self.settings.polling_max_backoff_seconds,
        )

        logger.info("bot_application_initialized")

    async def shutdown(self) -> None:
        """Cleanup resources."""
        if self.opencode:
            await self.opencode.close()

        logger.info("bot_shutdown_complete")

    def _is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized."""
        return self.db.is_user_allowed(user_id)

    def _is_bookmark_query(self, text: str) -> bool:
        """Check if text is a bookmark query."""
        text_lower = text.lower()
        has_bookmark_keyword = any(keyword in text_lower for keyword in BOOKMARK_KEYWORDS)
        has_time_expression = any(expr in text_lower for expr in TIME_EXPRESSIONS)
        return has_bookmark_keyword and (has_time_expression or "recent" in text_lower)

    async def _handle_bookmark_query(self, update: Update, text: str) -> bool:
        """Handle bookmark query."""
        msg = update.effective_message
        if msg is None:
            return False

        user_id = update.effective_user.id if update.effective_user else 0

        if not self.settings.x_client_id or not self.settings.x_client_secret:
            await self._send_feedback_message(
                update,
                user_id,
                "📚 Bookmarks not configured. Set X_CLIENT_ID and X_CLIENT_SECRET in .env",
                source="system",
                prompt_text=text,
            )
            return False

        response = await query_bookmarks(text, self)
        await self._send_feedback_message(
            update,
            user_id,
            response,
            source="bookmarks",
            prompt_text=text,
            parse_mode="HTML",
        )
        return True

    async def _process_input(
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

        if self._is_bookmark_query(text):
            handled = await self._handle_bookmark_query(update, text)
            if handled:
                return None

        if not self.opencode:
            raise RuntimeError("OpenCode not initialized")

        # Don't send model - let OpenCode use its last-used model
        # This allows OpenCode's session management to work naturally
        model = None

        if text.startswith("!"):
            parts = text[1:].split(maxsplit=1)
            command = parts[0]
            arguments = parts[1] if len(parts) > 1 else ""
            if command in {"models", "favmodels"}:
                await self._start_model_selection(update, user_id)
                return None
            parts, info = await self.opencode.send_command(
                session_id, command, arguments, model=model
            )
        else:
            parts, info = await self.opencode.send_message(
                session_id, text, model=model
            )

        content_text = "\n".join(
            p.get("text", "")
            for p in parts
            if p.get("type") == "text"
        )
        used_model = info.get("modelID", model or "default")
        try:
            self.db.log_response(session_id, user_id, used_model, content_text)
        except Exception as e:
            logger.warning(
                "response_logging_failed",
                session_id=session_id,
                user_id=user_id,
                model=used_model,
                error=str(e),
            )

        return parts, info

    async def _send_response(
        self,
        update: Update,
        parts: list[dict[str, Any]],
        turn_id: int | None = None,
    ) -> None:
        """Send response to user with optional feedback buttons.

        Args:
            update: Telegram update.
            parts: Response parts from OpenCode.
            turn_id: Optional turn ID for feedback buttons.
        """
        msg = update.effective_message
        if msg is None:
            return

        formatted_chunks = self.formatter.format_response(parts)
        total_chunks = len(formatted_chunks)

        for i, chunk in enumerate(formatted_chunks):
            is_last_chunk = i == total_chunks - 1
            reply_markup = None

            if is_last_chunk and turn_id is not None:
                reply_markup = build_feedback_keyboard(turn_id)

            try:
                sent_msg = await msg.reply_text(
                    chunk,
                    parse_mode="MarkdownV2",
                    reply_markup=reply_markup,
                )
                if is_last_chunk and turn_id is not None and sent_msg:
                    self.db.set_out_message_id(turn_id, sent_msg.message_id)
            except Exception as e:
                logger.warning("markdown_send_failed", error=str(e))
                sent_msg = await msg.reply_text(chunk, reply_markup=reply_markup)
                if is_last_chunk and turn_id is not None and sent_msg:
                    self.db.set_out_message_id(turn_id, sent_msg.message_id)

    async def _send_feedback_message(  # noqa: PLR0913
        self,
        update: Update,
        user_id: int,
        response_text: str,
        source: str,
        prompt_text: str,
        parse_mode: str | None = None,
    ) -> None:
        """Send a message with feedback buttons.

        Helper for non-OpenCode responses (bookmarks, model selection, errors).

        Args:
            update: Telegram update.
            user_id: Telegram user ID.
            response_text: Response text to send.
            source: Source type (bookmarks|model_select|error|system).
            prompt_text: Original user prompt.
            parse_mode: Optional parse mode (HTML or MarkdownV2).
        """
        msg = update.effective_message
        if msg is None:
            return

        turn_id = self.db.create_turn(
            telegram_user_id=user_id,
            telegram_chat_id=msg.chat_id,
            source=source,
            prompt_text=prompt_text,
            response_text=response_text,
            telegram_in_message_id=msg.message_id,
        )

        reply_markup = build_feedback_keyboard(turn_id)

        try:
            sent_msg = await msg.reply_text(
                response_text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            if sent_msg:
                self.db.set_out_message_id(turn_id, sent_msg.message_id)
        except Exception as e:
            logger.warning("feedback_message_send_failed", error=str(e))
            sent_msg = await msg.reply_text(response_text, reply_markup=reply_markup)
            if sent_msg:
                self.db.set_out_message_id(turn_id, sent_msg.message_id)

    async def _handle_error(
        self,
        update: Update,
        error: str,
        user_id: int | None = None,
        prompt_text: str | None = None,
    ) -> None:
        """Send error message with feedback buttons."""
        msg = update.effective_message
        if msg is None:
            return

        formatted_error = self.formatter.format_error_message(error)

        if user_id is not None and prompt_text is not None:
            await self._send_feedback_message(
                update,
                user_id,
                formatted_error,
                source="error",
                prompt_text=prompt_text,
                parse_mode="MarkdownV2",
            )
        else:
            try:
                await msg.reply_text(formatted_error, parse_mode="MarkdownV2")
            except Exception:
                await msg.reply_text(f"Error: {error}")

    async def _handle_feedback_callback(self, update: Update) -> None:
        """Handle feedback callback query (thumbs up/down)."""
        callback = update.callback_query
        if callback is None:
            return

        user_id = callback.from_user.id
        if not self._is_authorized(user_id):
            logger.warning("unauthorized_callback", user_id=user_id)
            await callback.answer()
            return

        data = callback.data
        if not data or not data.startswith("fb:"):
            logger.warning("invalid_callback_data", data=data)
            await callback.answer()
            return

        parts = data.split(":")
        if len(parts) != 3:  # noqa: PLR2004
            logger.warning("malformed_callback_data", data=data)
            await callback.answer()
            return

        try:
            turn_id = int(parts[1])
            vote_type = parts[2]
        except ValueError:
            logger.warning("invalid_turn_id", data=data)
            await callback.answer()
            return

        vote = 1 if vote_type == "up" else -1

        success = self.db.record_vote(turn_id, user_id, vote)

        if success:
            logger.info("feedback_recorded", turn_id=turn_id, vote=vote, user_id=user_id)
        else:
            logger.warning("feedback_record_failed", turn_id=turn_id, user_id=user_id)

        await callback.answer()

        try:
            await callback.edit_message_reply_markup(reply_markup=None)
        except Exception as e:
            logger.warning("remove_keyboard_failed", error=str(e))

    async def _handle_update(self, update: Update) -> None:  # noqa: PLR0912
        """Process single update from polling."""
        if update.callback_query:
            await self._handle_feedback_callback(update)
            return

        if not update.effective_user or not update.effective_message:
            return

        user_id = update.effective_user.id
        text = update.effective_message.text or ""

        if not self._is_authorized(user_id):
            logger.warning("unauthorized", user_id=user_id, text=text[:50])
            return

        if self.settings.enable_message_audit:
            self.db.log_message(user_id, "in", text)

        logger.info("message_received", user_id=user_id, text=text[:50])

        if self.settings.x_client_id and self._should_sync():
            try:
                await self._run_bookmark_sync()
            except Exception as e:
                logger.error("auto_sync_failed", error=str(e))

        # Initialize session first (outside main try for fallback access)
        if not self.session_manager:
            await self._handle_error(update, "Session manager not initialized", user_id, text)
            return

        # Get or create session, and check if it's new
        session_id, is_new_session = await self.session_manager.get_or_create_session(user_id)

        # Send health probe on first message after bot restart
        if not self._health_probe_sent:
            self._health_probe_sent = True
            await self._send_daily_health_probe(update, user_id, session_id, is_new_session)
            return

        try:
            result = await self._process_input(update, user_id, session_id, text)
            if result is None:
                return

            parts, info = result

            response_text = "\n".join(
                p.get("text", "")
                for p in parts
                if p.get("type") == "text"
            )

            model_id = info.get("modelID", "")
            provider_id = info.get("providerID", "")
            agent = info.get("agent", "")
            used_model = f"{provider_id}/{model_id}" if provider_id else model_id

            # Track model used for this session (for auditing/debugging)
            if self.session_manager and used_model:
                self.session_manager.update_session_model(session_id, used_model)

            turn_id = self.db.create_turn(
                telegram_user_id=user_id,
                telegram_chat_id=update.effective_message.chat_id,
                source="opencode",
                prompt_text=text,
                response_text=response_text,
                telegram_in_message_id=update.effective_message.message_id,
                opencode_session_id=session_id,
                model_full=used_model,
                agent=agent,
            )

            await self._send_response(update, parts, turn_id)

            logger.info(
                "response_sent",
                parts=len(parts),
                model=used_model,
                agent=agent,
                turn_id=turn_id,
            )

            if self.settings.enable_message_audit:
                for part in parts:
                    if part.get("type") == "text":
                        self.db.log_message(user_id, "out", part.get("text", "")[:200])

        except OpenCodeError as e:
            # Check if this is a model-related error and try fallback
            error_str = str(e).lower()
            if ("model" in error_str or "provider" in error_str or "not found" in error_str) and self.models.get_count() > 0:
                fallback_model = self.models.get_models()[0]
                logger.warning(
                    "model_fallback_activated",
                    error=str(e),
                    fallback_model=fallback_model,
                    user_id=user_id,
                )
                try:
                    if not self.opencode:
                        raise RuntimeError("OpenCode not initialized")
                    parts, info = await self.opencode.send_message(
                        session_id, text, model=fallback_model
                    )
                    # Process the successful fallback response
                    response_text = "\n".join(
                        p.get("text", "")
                        for p in parts
                        if p.get("type") == "text"
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
                        prompt_text=text,
                        response_text=response_text,
                        telegram_in_message_id=update.effective_message.message_id,
                        opencode_session_id=session_id,
                        model_full=used_model,
                        agent=agent,
                    )
                    await self._send_response(update, parts, turn_id)
                    logger.info(
                        "fallback_response_sent",
                        parts=len(parts),
                        model=used_model,
                        agent=agent,
                        turn_id=turn_id,
                        fallback=True,
                    )
                    return  # Successfully handled with fallback
                except Exception as fallback_error:
                    logger.error(
                        "fallback_failed",
                        original_error=str(e),
                        fallback_error=str(fallback_error),
                        user_id=user_id,
                    )
                    await self._handle_error(
                        update,
                        f"OpenCode error (fallback also failed): {e}",
                        user_id,
                        text,
                    )
            else:
                logger.error("opencode_error", error=str(e), status_code=e.status_code)
                await self._handle_error(update, f"OpenCode error: {e}", user_id, text)
        except Exception as e:
            logger.error("handler_error", error=str(e), exc_info=True)
            await self._handle_error(update, f"Unexpected error: {str(e)[:200]}", user_id, text)

    def _should_sync(self) -> bool:
        """Check if we should sync bookmarks today."""
        today = date.today().isoformat()
        sync_status = self.db.get_sync_status()
        return not (sync_status and sync_status.get("last_sync_date") == today)

    async def _run_bookmark_sync(self) -> None:
        """Run bookmark sync."""
        if not self.settings.x_client_id or not self.settings.x_client_secret:
            logger.warning("x_oauth_not_configured")
            return

        if not self.db.has_oauth_tokens():
            logger.warning("x_oauth_tokens_not_found_run_setup")
            return

        logger.info("starting_auto_sync")
        sync = BookmarkSync(
            self.db,
            self.settings.x_client_id,
            self.settings.x_client_secret,
            base_url=self.settings.x_api_base_url,
            oauth_token_url=self.settings.x_oauth_token_url,
            api_timeout=self.settings.x_api_timeout,
            token_refresh_buffer_seconds=self.settings.x_token_refresh_buffer_seconds,
        )

        sync_status = self.db.get_sync_status()
        is_first = not sync_status or not sync_status.get("first_sync_complete")

        result = await sync.sync_bookmarks(full_sync=is_first)

        if result.get("status") == "success":
            self.db.update_sync_status(last_sync_date=date.today().isoformat())
            logger.info("auto_sync_complete", new=result.get("new_bookmarks"))

    async def _send_daily_health_probe(
        self,
        update: Update,
        user_id: int,
        session_id: str,
        is_new_session: bool = False,
    ) -> None:
        """Send health probe on first message after bot restart.

        Tests system by asking "What day is today?" and reports status.
        If this is a new session, uses the first favorite model as default.

        Args:
            update: Telegram update.
            user_id: Telegram user ID.
            session_id: OpenCode session ID.
            is_new_session: True if this session was just created.
        """
        if not self.opencode:
            await self._handle_error(update, "OpenCode not initialized", user_id, "health_probe")
            return

        # Use default model for new sessions
        model = None
        if is_new_session and self.models.get_count() > 0:
            model = self.models.get_models()[0]
            logger.info("using_default_model_for_new_session", model=model)

        # Test message to validate system
        test_prompt = "What day is today?"

        try:
            parts, info = await self.opencode.send_message(
                session_id, test_prompt, model=model
            )

            # Extract response text
            response_text = "\n".join(
                p.get("text", "")
                for p in parts
                if p.get("type") == "text"
            )

            # Get model and agent info
            model_id = info.get("modelID", "unknown")
            provider_id = info.get("providerID", "")
            agent = info.get("agent", "unknown")
            used_model = f"{provider_id}/{model_id}" if provider_id else model_id

            # Track model used
            if self.session_manager:
                self.session_manager.update_session_model(session_id, used_model)

            # Build health report
            # Extract session title from info if available
            session_title = f"jarvis-user-{user_id}"

            health_report = (
                f"🤖 <b>Jarvis is online!</b>\n\n"
                f"📊 <b>Session Info:</b>\n"
                f"• Model: <code>{used_model}</code>\n"
                f"• Agent: <code>{agent}</code>\n"
                f"• Session: <code>{session_id[:20]}...</code>\n\n"
                f"💬 <b>Test response:</b>\n"
                f"{response_text[:200]}\n\n"
                f"<i>Ready for your commands!</i>"
            )

            # Send as system message
            await self._send_feedback_message(
                update,
                user_id,
                health_report,
                source="system",
                prompt_text="[startup health probe]",
                parse_mode="HTML",
            )

            logger.info(
                "startup_health_probe_sent",
                user_id=user_id,
                session_id=session_id,
                model=used_model,
                agent=agent,
            )

        except Exception as e:
            logger.error(
                "health_probe_failed",
                user_id=user_id,
                session_id=session_id,
                error=str(e),
            )
            await self._handle_error(
                update,
                f"Health probe failed: {str(e)[:100]}",
                user_id,
                "health_probe",
            )

    async def _start_model_selection(self, update: Update, user_id: int) -> None:
        """Start model selection flow."""
        msg = update.effective_message
        if msg is None or self.model_selector is None:
            return

        response = await self.model_selector.start_selection(user_id)
        if response:
            prompt_text = msg.text or "[model selection]"
            await self._send_feedback_message(
                update,
                user_id,
                response,
                source="model_select",
                prompt_text=prompt_text,
                parse_mode="HTML",
            )

    async def start(self) -> None:
        """Start bot with polling."""
        await self.initialize()

        if not self.app or not self.polling:
            raise RuntimeError("Bot not initialized")

        await self.app.initialize()

        self._running = True
        logger.info("bot_started")

        await self.polling.start(self._handle_update)

    def stop(self) -> None:
        """Stop bot."""
        self._running = False
        if self.polling:
            self.polling.stop()
        logger.info("bot_stop_requested")
