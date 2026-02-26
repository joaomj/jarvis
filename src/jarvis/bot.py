"""Telegram bot implementation with polling."""

from __future__ import annotations

from telegram.ext import Application

from jarvis.bot_bookmarks import BotBookmarksMixin
from jarvis.bot_feedback import BotFeedbackMixin
from jarvis.bot_kb import BotKBMixin
from jarvis.bot_updates import BotUpdateMixin
from jarvis.config import Settings
from jarvis.database import Database
from jarvis.event_processor import EventProcessor
from jarvis.formatter import ResponseFormatter
from jarvis.logging_config import get_logger
from jarvis.model_selector import ModelSelector
from jarvis.models_manager import ModelsManager
from jarvis.opencode_client import OpenCodeClient
from jarvis.polling_engine import PollingEngine
from jarvis.session_manager import SessionManager

logger = get_logger(__name__)


class JarvisBot(BotUpdateMixin, BotKBMixin, BotBookmarksMixin, BotFeedbackMixin):
    """Telegram bot with polling support."""

    def __init__(self, settings: Settings):
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
        self.kb_indexer = None
        self._initialize_kb_state()
        self.events = EventProcessor(self)
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
            logger.critical("opencode_unhealthy", reason=reason)
            raise RuntimeError(f"OpenCode Server is not healthy: {reason}")

        logger.info("opencode_connected", healthy=healthy, reason=reason)
        self.session_manager = SessionManager(self.opencode, self.db)
        self.model_selector = ModelSelector(self.db, self.models)
        self.db.add_user(self.settings.telegram_user_id)

        deleted = self.db.cleanup_old_responses()
        if deleted > 0:
            logger.info("response_cleanup_complete", deleted=deleted)

        self.app = Application.builder().token(self.settings.telegram_bot_id).build()
        self.polling = PollingEngine(
            self.app,
            interval=self.settings.telegram_polling_interval,
            timeout=self.settings.telegram_polling_timeout,
            max_backoff_level=self.settings.polling_max_backoff_level,
            max_backoff_seconds=self.settings.polling_max_backoff_seconds,
        )
        self._run_kb_startup_scan()
        logger.info("bot_application_initialized")

    async def shutdown(self) -> None:
        """Cleanup resources."""
        await self.events.stop()
        if self.opencode:
            await self.opencode.close()
        logger.info("bot_shutdown_complete")

    def _is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized."""
        return self.db.is_user_allowed(user_id)

    async def start(self) -> None:
        """Start bot with polling."""
        await self.initialize()
        if not self.app or not self.polling:
            raise RuntimeError("Bot not initialized")

        await self.app.initialize()
        self._running = True
        self.events.start()
        logger.info("bot_started")
        await self.polling.start(self._handle_update)

    def stop(self) -> None:
        """Stop bot."""
        self._running = False
        if self.polling:
            self.polling.stop()
        logger.info("bot_stop_requested")
