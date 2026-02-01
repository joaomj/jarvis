"""Telegram bot implementation with webhook support.

Thin passthrough bridge between Telegram and OpenCode Server.
No command interpretation - just forward messages and return responses.

Key components:
- Webhook server (aiohttp)
- User allowlist (single user)
- Session management (per Telegram user)
- Message routing (/command vs regular text)
- Response formatting and delivery
"""

import json
from pathlib import Path
from typing import Any

from aiohttp import web
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from jarvis.config import Settings
from jarvis.formatter import ResponseFormatter
from jarvis.logging import get_logger
from jarvis.opencode_client import OpenCodeClient, OpenCodeError

logger = get_logger(__name__)


class JarvisBot:
    """Telegram bot with webhook support.

    Responsibilities:
    1. Receive Telegram messages via webhook
    2. Validate user against allowlist
    3. Route messages to OpenCode
    4. Format and return responses
    """

    def __init__(self, settings: Settings):
        """Initialize bot with configuration.

        Args:
            settings: Application settings.
        """
        self.settings = settings
        self.allowed_user_id = settings.telegram_user_id
        self.formatter = ResponseFormatter()
        self.opencode: OpenCodeClient | None = None
        self.sessions: dict[int, str] = {}  # user_id -> session_id
        self.app: Application | None = None
        self.webhook_app: web.Application | None = None

        logger.info(
            "bot_initialized",
            allowed_user=settings.telegram_user_id,
            webhook_url=settings.telegram_webhook_url,
        )

    async def initialize(self) -> None:
        """Initialize bot and OpenCode client."""
        # Initialize OpenCode client
        self.opencode = OpenCodeClient(
            self.settings.opencode_url,
            self.settings.opencode_server_password,
        )

        # Test connection
        healthy = await self.opencode.health_check()
        if not healthy:
            logger.error("opencode_unhealthy")
            raise RuntimeError("OpenCode Server is not healthy")

        logger.info("opencode_connected", healthy=healthy)

        # Load existing sessions
        await self._load_sessions()

        # Initialize Telegram bot application
        self.app = (
            Application.builder()
            .token(self.settings.telegram_bot_id)
            .build()
        )

        # Register handlers
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

        logger.info("bot_application_initialized")

    async def shutdown(self) -> None:
        """Shutdown bot and cleanup resources."""
        # Save sessions
        await self._save_sessions()

        # Close OpenCode client
        if self.opencode:
            await self.opencode.close()

        logger.info("bot_shutdown_complete")

    def _is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized.

        Args:
            user_id: Telegram user ID.

        Returns:
            bool: True if authorized.
        """
        return user_id == self.allowed_user_id

    async def _get_or_create_session(self, user_id: int) -> str:
        """Get existing session or create new one.

        Args:
            user_id: Telegram user ID.

        Returns:
            str: OpenCode session ID.
        """
        if user_id in self.sessions:
            session_id = self.sessions[user_id]
            logger.info("session_found", user_id=user_id, session_id=session_id)
            return session_id

        # Create new session
        if not self.opencode:
            raise RuntimeError("OpenCode client not initialized")

        session_id = await self.opencode.create_session(
            f"jarvis-user-{user_id}"
        )
        self.sessions[user_id] = session_id
        await self._save_sessions()

        logger.info("session_created", user_id=user_id, session_id=session_id)
        return session_id

    async def _load_sessions(self) -> None:
        """Load session mappings from storage."""
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
            logger.info("no_sessions_file")
            self.sessions = {}

    async def _save_sessions(self) -> None:
        """Save session mappings to storage."""
        storage_path = Path(self.settings.session_storage_path)
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            storage_path.write_text(json.dumps(self.sessions, indent=2))
            logger.info("sessions_saved", count=len(self.sessions))
        except IOError as e:
            logger.error("sessions_save_failed", error=str(e))

    async def _send_response(
        self, update: Update, parts: list[dict[str, Any]]
    ) -> None:
        """Send formatted response to user.

        Args:
            update: Telegram update object.
            parts: Response parts from OpenCode.
        """
        if not update.effective_message:
            return

        formatted_chunks = self.formatter.format_response(parts)

        for chunk in formatted_chunks:
            try:
                await update.effective_message.reply_text(
                    chunk, parse_mode="MarkdownV2"
                )
            except Exception as e:
                # If MarkdownV2 fails, try plain text
                logger.warning("markdown_send_failed", error=str(e))
                await update.effective_message.reply_text(chunk)

    async def _handle_error(self, update: Update, error: str) -> None:
        """Send error message to user.

        Args:
            update: Telegram update object.
            error: Error message.
        """
        if not update.effective_message:
            return

        formatted_error = self.formatter.format_error_message(error)
        try:
            await update.effective_message.reply_text(
                formatted_error, parse_mode="MarkdownV2"
            )
        except Exception:
            # Fallback to plain text
            await update.effective_message.reply_text(f"Error: {error}")

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not update.effective_user or not self._is_authorized(update.effective_user.id):
            return

        await update.effective_message.reply_text(
            "👋 Hello! I'm Jarvis, your AI assistant.\n\n"
            "Send me any message and I'll forward it to OpenCode.\n"
            "Use /command syntax (e.g., /undo, /new) for OpenCode commands."
        )

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages from Telegram.

        Args:
            update: Telegram update.
            context: Bot context.
        """
        if not update.effective_user or not update.effective_message:
            return

        user_id = update.effective_user.id
        text = update.effective_message.text or ""

        # Check authorization (silent ignore for unauthorized)
        if not self._is_authorized(user_id):
            logger.warning("unauthorized_access", user_id=user_id, text_preview=text[:50])
            return

        logger.info("message_received", user_id=user_id, text_preview=text[:50])

        try:
            session_id = await self._get_or_create_session(user_id)

            if not self.opencode:
                raise RuntimeError("OpenCode client not initialized")

            # Route based on message type
            if text.startswith("/"):
                # Extract command and arguments
                parts = text[1:].split(maxsplit=1)
                command = parts[0]
                arguments = parts[1] if len(parts) > 1 else ""

                logger.info("command_detected", command=command, user_id=user_id)
                response_parts = await self.opencode.send_command(
                    session_id, command, arguments
                )
            else:
                # Regular message
                response_parts = await self.opencode.send_message(session_id, text)

            # Send response
            await self._send_response(update, response_parts)
            logger.info("response_sent", user_id=user_id, parts=len(response_parts))

        except OpenCodeError as e:
            logger.error("opencode_error", user_id=user_id, error=str(e))
            await self._handle_error(update, f"OpenCode error: {e}")
        except Exception as e:
            logger.error("message_handler_error", user_id=user_id, error=str(e))
            await self._handle_error(update, "An unexpected error occurred")

    async def _webhook_handler(self, request: web.Request) -> web.Response:
        """Handle incoming webhook requests from Telegram.

        Args:
            request: aiohttp request object.

        Returns:
            web.Response: HTTP response.
        """
        try:
            data = await request.json()
            update = Update.de_json(data, self.app.bot)

            # Process update through dispatcher
            await self.app.process_update(update)

            return web.Response(status=200)
        except Exception as e:
            logger.error("webhook_handler_error", error=str(e))
            return web.Response(status=500)

    async def _health_handler(self, request: web.Request) -> web.Response:
        """Health check endpoint.

        Args:
            request: aiohttp request object.

        Returns:
            web.Response: Health status.
        """
        health_data = {
            "healthy": True,
            "service": "jarvis-bot",
            "opencode_connected": self.opencode is not None,
        }
        return web.json_response(health_data)

    def setup_webhook_server(self) -> web.Application:
        """Setup aiohttp webhook server.

        Returns:
            web.Application: Configured aiohttp app.
        """
        self.webhook_app = web.Application()
        self.webhook_app.router.add_post("/webhook", self._webhook_handler)
        self.webhook_app.router.add_get("/health", self._health_handler)

        return self.webhook_app

    async def start(self) -> None:
        """Start the bot and webhook server."""
        await self.initialize()

        # Setup webhook with Telegram
        await self.app.bot.set_webhook(self.settings.telegram_webhook_url)
        logger.info("webhook_set", url=self.settings.telegram_webhook_url)

        # Setup webhook server
        self.setup_webhook_server()

        logger.info("bot_started", port=self.settings.telegram_webhook_port)

    async def stop(self) -> None:
        """Stop the bot and cleanup."""
        # Remove webhook
        if self.app:
            await self.app.bot.delete_webhook()
            logger.info("webhook_deleted")

        await self.shutdown()
