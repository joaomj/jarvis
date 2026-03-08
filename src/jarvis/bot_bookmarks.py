"""Bookmark-specific behaviors for ``JarvisBot``."""

# mypy: ignore-errors

from __future__ import annotations

from datetime import date

from telegram import Update

from jarvis.bookmarks.sync import BookmarkSync
from jarvis.bot_constants import WEEKLY_RECONCILE_DAYS
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class BotBookmarksMixin:
    """Methods for bookmark sync orchestration."""

    def _should_sync(self) -> bool:
        """Check if bookmark sync should run today."""
        today = date.today().isoformat()
        sync_status = self.db.get_sync_status()
        return not (sync_status and sync_status.get("last_sync_date") == today)

    def _should_run_weekly_reconcile(self) -> bool:
        """Check if weekly full mirror reconciliation is due."""
        sync_status = self.db.get_sync_status()
        if not sync_status:
            return True

        last_full_sync = sync_status.get("last_full_sync_date")
        if not last_full_sync:
            return True

        try:
            days_since_full = (date.today() - date.fromisoformat(last_full_sync)).days
        except ValueError:
            return True
        return days_since_full >= WEEKLY_RECONCILE_DAYS

    async def _run_bookmark_sync(self) -> None:
        """Run bookmark sync against X API."""
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

        run_full_reconcile = self._should_run_weekly_reconcile()
        result = await sync.sync_bookmarks(
            full_sync=run_full_reconcile,
            sync_folders=run_full_reconcile,
        )

        if result.get("status") == "success":
            self.db.update_sync_status(last_sync_date=date.today().isoformat())
            logger.info(
                "auto_sync_complete",
                new=result.get("new_bookmarks"),
                deleted=result.get("deleted_bookmarks"),
                full_sync=run_full_reconcile,
            )

    async def _send_daily_health_probe(
        self,
        update: Update,
        user_id: int,
        session_id: str,
        is_new_session: bool = False,
    ) -> None:
        """Send startup health probe on first user message."""
        if not self.opencode:
            await self._handle_error(update, "OpenCode not initialized", user_id, "health_probe")
            return

        model = (
            self.models.get_models()[0] if is_new_session and self.models.get_count() > 0 else None
        )
        if model:
            logger.info("using_default_model_for_new_session", model=model)

        try:
            parts, info = await self.opencode.send_message(
                session_id, "What day is today?", model=model
            )
            response_text = "\n".join(
                part.get("text", "") for part in parts if part.get("type") == "text"
            )
            model_id = info.get("modelID", "unknown")
            provider_id = info.get("providerID", "")
            agent = info.get("agent", "unknown")
            used_model = f"{provider_id}/{model_id}" if provider_id else model_id

            if self.session_manager:
                self.session_manager.update_session_model(session_id, used_model)

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
        except Exception as error:
            logger.error(
                "health_probe_failed",
                user_id=user_id,
                session_id=session_id,
                error=str(error),
            )
            await self._handle_error(
                update,
                f"Health probe failed: {str(error)[:100]}",
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
