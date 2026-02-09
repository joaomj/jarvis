"""Telegram bot implementation with polling.

Thin passthrough bridge between Telegram and OpenCode Server.
"""

import json
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.ext import Application

from jarvis.config import Settings
from jarvis.database import Database
from jarvis.formatter import ResponseFormatter
from jarvis.logging_config import get_logger
from jarvis.models_manager import ModelsManager
from jarvis.opencode_client import OpenCodeClient, OpenCodeError
from jarvis.polling_engine import PollingEngine

logger = get_logger(__name__)


class JarvisBot:
    """Telegram bot with polling support."""

    def __init__(self, settings: Settings):
        """Initialize bot."""
        self.settings = settings
        self.formatter = ResponseFormatter()
        self.opencode: OpenCodeClient | None = None
        self.sessions: dict[int, str] = {}
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
        # Initialize OpenCode
        self.opencode = OpenCodeClient(
            self.settings.opencode_url,
            self.settings.opencode_server_password,
        )

        healthy = await self.opencode.health_check()
        if not healthy:
            raise RuntimeError("OpenCode Server is not healthy")

        logger.info("opencode_connected", healthy=healthy)

        # Load sessions
        await self._load_sessions()

        # Add user to DB
        self.db.add_user(self.settings.telegram_user_id)

        # Initialize Telegram app
        self.app = (
            Application.builder()
            .token(self.settings.telegram_bot_id)
            .build()
        )

        # Create polling engine
        self.polling = PollingEngine(
            self.app,
            interval=self.settings.telegram_polling_interval,
            timeout=self.settings.telegram_polling_timeout,
        )

        logger.info("bot_application_initialized")

    async def shutdown(self) -> None:
        """Cleanup resources."""
        await self._save_sessions()

        if self.opencode:
            await self.opencode.close()

        logger.info("bot_shutdown_complete")

    def _is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized."""
        return self.db.is_user_allowed(user_id)

    async def _get_or_create_session(self, user_id: int) -> str:
        """Get or create OpenCode session."""
        if user_id in self.sessions:
            session_id = self.sessions[user_id]
            logger.info("session_found", user_id=user_id, session_id=session_id)
            return session_id

        if not self.opencode:
            raise RuntimeError("OpenCode client not initialized")

        session_id = await self.opencode.create_session(f"jarvis-user-{user_id}")
        self.sessions[user_id] = session_id
        await self._save_sessions()

        logger.info("session_created", user_id=user_id, session_id=session_id)
        return session_id

    async def _load_sessions(self) -> None:
        """Load sessions from storage."""
        storage_path = Path(self.settings.session_storage_path)
        if storage_path.exists():
            try:
                data = json.loads(storage_path.read_text())
                self.sessions = {int(k): v for k, v in data.items()}
                logger.info("sessions_loaded", count=len(self.sessions))
            except (json.JSONDecodeError, ValueError) as e:
                logger.error("sessions_load_failed", error=str(e))
                self.sessions = {}
        else:
            self.sessions = {}

    async def _save_sessions(self) -> None:
        """Save sessions to storage."""
        storage_path = Path(self.settings.session_storage_path)
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            storage_path.write_text(json.dumps(self.sessions, indent=2))
            logger.info("sessions_saved", count=len(self.sessions))
        except OSError as e:
            logger.error("sessions_save_failed", error=str(e))

    async def _process_input(
        self,
        update: Update,
        user_id: int,
        session_id: str,
        text: str,
    ) -> list[dict[str, Any]] | None:
        """Process message text and return OpenCode response when applicable."""
        if self.db.get_user_state(user_id) == "awaiting_model_selection":
            await self._handle_model_selection(update, session_id, text)
            return None
        if not self.opencode:
            raise RuntimeError("OpenCode not initialized")
        if text.startswith("!"):
            parts = text[1:].split(maxsplit=1)
            command = parts[0]
            arguments = parts[1] if len(parts) > 1 else ""
            if command == "models":
                await self._start_model_selection(update, user_id)
                return None
            return await self.opencode.send_command(session_id, command, arguments)
        return await self.opencode.send_message(session_id, text)

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

        # Authorization check
        if not self._is_authorized(user_id):
            logger.warning("unauthorized", user_id=user_id, text=text[:50])
            return

        # Audit log
        if self.settings.enable_message_audit:
            self.db.log_message(user_id, "in", text)

        logger.info("message_received", user_id=user_id, text=text[:50])

        try:
            session_id = await self._get_or_create_session(user_id)
            response = await self._process_input(update, user_id, session_id, text)
            if response is None:
                return

            # Send response
            await self._send_response(update, response)
            logger.info("response_sent", parts=len(response))

            # Audit log outgoing
            if self.settings.enable_message_audit:
                for part in response:
                    if part.get("type") == "text":
                        self.db.log_message(user_id, "out", part.get("text", "")[:200])

        except OpenCodeError as e:
            logger.error("opencode_error", error=str(e))
            await self._handle_error(update, f"OpenCode error: {e}")
        except Exception as e:
            logger.error("handler_error", error=str(e))
            await self._handle_error(update, "Unexpected error occurred")

    async def _start_model_selection(self, update: Update, user_id: int) -> None:
        msg = update.effective_message
        if msg is None:
            return
        model_count = self.models.get_count()
        if model_count == 0:
            await msg.reply_text("No favorite models configured in .jarvis/favorite_models.json")
            return
        self.db.set_user_state(user_id, "awaiting_model_selection")
        model_list = self.models.format_telegram_list()
        await msg.reply_text(
            "📋 <b>Available Models</b>\n\n"
            f"{model_list}\n\n"
            f"Reply with number (1-{model_count}) or <code>cancel</code>",
            parse_mode="HTML",
        )

    async def _handle_model_selection(self, update: Update, session_id: str, text: str) -> None:
        msg = update.effective_message
        if msg is None:
            return
        user_id = update.effective_user.id if update.effective_user else 0
        if self.models.is_cancel(text):
            self.db.clear_user_state(user_id)
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
        if not self.opencode:
            raise RuntimeError("OpenCode not initialized")
        self.db.clear_user_state(user_id)
        response = await self.opencode.send_command(
            session_id=session_id,
            command="model",
            arguments=model_id,
        )
        await self._send_response(update, response)

    async def start(self) -> None:
        """Start bot with polling."""
        await self.initialize()

        if not self.app or not self.polling:
            raise RuntimeError("Bot not initialized")

        await self.app.initialize()

        try:
            await self.app.bot.delete_webhook(drop_pending_updates=True)
            logger.info("webhook_deleted")
        except Exception as e:
            logger.warning("webhook_delete_failed", error=str(e))

        self._running = True
        logger.info("bot_started")

        await self.polling.start(self._handle_update)

    def stop(self) -> None:
        """Stop bot."""
        self._running = False
        if self.polling:
            self.polling.stop()
        logger.info("bot_stop_requested")
