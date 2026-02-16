"""Telegram bot implementation with polling.

Thin passthrough bridge between Telegram and OpenCode Server.
"""

import html
from datetime import date
from typing import Any

from telegram import Update
from telegram.ext import Application

from jarvis.bookmarks.sync import BookmarkSync
from jarvis.config import Settings
from jarvis.database import Database
from jarvis.formatter import ResponseFormatter
from jarvis.handlers.commands import query_bookmarks
from jarvis.logging_config import get_logger
from jarvis.models_manager import ModelsManager
from jarvis.opencode_client import OpenCodeClient, OpenCodeError
from jarvis.polling_engine import PollingEngine

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


class JarvisBot:
    """Telegram bot with polling support."""

    def __init__(self, settings: Settings):
        """Initialize bot."""
        self.settings = settings
        self.formatter = ResponseFormatter()
        self.opencode: OpenCodeClient | None = None
        self.sessions: dict[int, str] = {}
        self._model_preferences: dict[int, str] = {}
        self.app: Application | None = None
        self.polling: PollingEngine | None = None
        self.db = Database(settings.database_path)
        self.models = ModelsManager(settings.favorite_models_path)
        self._running = False

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

        self.db.add_user(self.settings.telegram_user_id)

        deleted = self.db.cleanup_old_responses(30)
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
        """Check if text is a bookmark query.

        Args:
            text: Message text to check.

        Returns:
            True if text contains bookmark keywords and time expressions.
        """
        text_lower = text.lower()
        has_bookmark_keyword = any(keyword in text_lower for keyword in BOOKMARK_KEYWORDS)
        has_time_expression = any(expr in text_lower for expr in TIME_EXPRESSIONS)
        return has_bookmark_keyword and (has_time_expression or "recent" in text_lower)

    async def _handle_bookmark_query(self, update: Update, text: str) -> bool:
        """Handle bookmark query.

        Args:
            update: Telegram update.
            text: Query text.

        Returns:
            True if handled, False otherwise.
        """
        msg = update.effective_message
        if msg is None:
            return False

        if not self.settings.x_bearer_token:
            await msg.reply_text("📚 Bookmarks not configured. Set X_BEARER_TOKEN in .env")
            return False

        response = await query_bookmarks(text, self)
        await msg.reply_text(response, parse_mode="HTML")
        return True

    async def _get_or_create_session(self, user_id: int) -> str:
        """Find existing session by title or create new one."""
        if user_id in self.sessions:
            session_id = self.sessions[user_id]
            logger.info("session_found_in_memory", user_id=user_id, session_id=session_id)
            return session_id

        if not self.opencode:
            raise RuntimeError("OpenCode client not initialized")

        session_title = f"jarvis-user-{user_id}"
        sessions = await self.opencode.list_sessions()
        user_session = next(
            (s for s in sessions if s.get("title") == session_title),
            None
        )

        if user_session:
            session_id = user_session["id"]
            self.sessions[user_id] = session_id
            logger.info("session_found_in_opencode", user_id=user_id, session_id=session_id)
            return session_id

        session_id = await self.opencode.create_session(session_title)
        self.sessions[user_id] = session_id
        logger.info("session_created", user_id=user_id, session_id=session_id)
        return session_id

    def _get_model_for_user(self, user_id: int) -> str | None:
        """Get model preference for user.

        Args:
            user_id: Telegram user ID.

        Returns:
            Model ID or None (use OpenCode default).
        """
        return self._model_preferences.get(user_id)

    async def _process_input(
        self,
        update: Update,
        user_id: int,
        session_id: str,
        text: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
        """Process message text and return OpenCode response.

        Returns:
            tuple of (parts, info) or None if no response needed.
        """
        if self.db.get_user_state(user_id) == "awaiting_model_selection":
            await self._handle_model_selection(update, text)
            return None

        if self._is_bookmark_query(text):
            handled = await self._handle_bookmark_query(update, text)
            if handled:
                return None

        if not self.opencode:
            raise RuntimeError("OpenCode not initialized")

        model = self._get_model_for_user(user_id)

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
        self, update: Update, parts: list[dict[str, Any]]
    ) -> None:
        """Send response to user."""
        msg = update.effective_message
        if msg is None:
            return

        formatted_chunks = self.formatter.format_response(parts)

        for chunk in formatted_chunks:
            try:
                await msg.reply_text(chunk, parse_mode="MarkdownV2")
            except Exception as e:
                logger.warning("markdown_send_failed", error=str(e))
                await msg.reply_text(chunk)

    async def _handle_error(self, update: Update, error: str) -> None:
        """Send error message."""
        msg = update.effective_message
        if msg is None:
            return

        formatted_error = self.formatter.format_error_message(error)
        try:
            await msg.reply_text(formatted_error, parse_mode="MarkdownV2")
        except Exception:
            await msg.reply_text(f"Error: {error}")

    async def _handle_update(self, update: Update) -> None:
        """Process single update from polling."""
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

        # Trigger bookmark sync on first message of the day
        if self.settings.x_client_id and self._should_sync():
            try:
                await self._run_bookmark_sync()
            except Exception as e:
                logger.error("auto_sync_failed", error=str(e))

        try:
            session_id = await self._get_or_create_session(user_id)
            result = await self._process_input(update, user_id, session_id, text)
            if result is None:
                return

            parts, info = result

            await self._send_response(update, parts)

            model_id = info.get("modelID", "")
            provider_id = info.get("providerID", "")
            agent = info.get("agent", "")
            used_model = f"{provider_id}/{model_id}" if provider_id else model_id

            logger.info(
                "response_sent",
                parts=len(parts),
                model=used_model,
                agent=agent,
            )

            if self.settings.enable_message_audit:
                for part in parts:
                    if part.get("type") == "text":
                        self.db.log_message(user_id, "out", part.get("text", "")[:200])

        except OpenCodeError as e:
            logger.error("opencode_error", error=str(e), status_code=e.status_code)
            await self._handle_error(update, f"OpenCode error: {e}")
        except Exception as e:
            logger.error("handler_error", error=str(e), exc_info=True)
            await self._handle_error(update, f"Unexpected error: {str(e)[:200]}")

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
        )

        # Check if first sync ever
        sync_status = self.db.get_sync_status()
        is_first = not sync_status or not sync_status.get("first_sync_complete")

        result = await sync.sync_bookmarks(full_sync=is_first)

        if result.get("status") == "success":
            self.db.update_sync_status(last_sync_date=date.today().isoformat())
            logger.info("auto_sync_complete", new=result.get("new_bookmarks"))

    async def _start_model_selection(self, update: Update, user_id: int) -> None:
        """Start model selection flow.

        Args:
            update: Telegram update.
            user_id: Telegram user ID.
        """
        msg = update.effective_message
        if msg is None:
            return
        model_count = self.models.get_count()
        if model_count == 0:
            await msg.reply_text("No favorite models configured in .jarvis/favorite_models.json")
            return
        try:
            self.db.set_user_state(user_id, "awaiting_model_selection")
        except Exception as e:
            logger.error("set_user_state_failed", user_id=user_id, error=str(e))
            await msg.reply_text("❌ Failed to start model selection. Please try again.")
            return
        model_list = self.models.format_telegram_list()
        await msg.reply_text(
            "📋 <b>Available Models</b>\n\n"
            f"{model_list}\n\n"
            f"Reply with number (1-{model_count}) or <code>cancel</code>",
            parse_mode="HTML",
        )

    async def _handle_model_selection(self, update: Update, text: str) -> None:
        """Handle model selection response.

        Args:
            update: Telegram update.
            text: User's response text.
        """
        msg = update.effective_message
        if msg is None:
            return
        user_id = update.effective_user.id if update.effective_user else 0
        if self.models.is_cancel(text):
            try:
                self.db.clear_user_state(user_id)
            except Exception as e:
                logger.warning("clear_user_state_failed", user_id=user_id, error=str(e))
            await msg.reply_text("Model selection cancelled.")
            return
        if not text.strip().isdigit():
            await msg.reply_text("Please reply with a model number or cancel.")
            return
        selected = int(text.strip())
        model_id = self.models.get_model_by_number(selected)
        if model_id is None:
            await msg.reply_text(f"Invalid selection. Choose 1-{self.models.get_count()} or cancel.")
            return

        try:
            self.db.clear_user_state(user_id)
        except Exception as e:
            logger.warning("clear_user_state_failed", user_id=user_id, error=str(e))

        self._model_preferences[user_id] = model_id
        logger.info("model_preference_set", model=model_id, user_id=user_id)

        await msg.reply_text(
            f"✅ Model set to: <code>{html.escape(model_id)}</code>\n\n"
            "This will be used for your next message.",
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
