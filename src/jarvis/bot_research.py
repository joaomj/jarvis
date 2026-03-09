"""Deep research behaviors for ``JarvisBot``."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

from jarvis.deep_research import DeepResearchDecision, DeepResearchOrchestrator
from jarvis.logging_config import get_logger

logger = get_logger(__name__)
CALLBACK_PARTS = 3


@dataclass
class DeepResearchPendingConfirmation:
    """Pending deep-research confirmation state."""

    session_id: str
    user_id: int
    text: str
    model: str | None


class BotResearchMixin:
    """Methods for deep-research gating and orchestration."""

    def _initialize_research_state(self) -> None:
        """Initialize deep research orchestrator and pending map."""
        self.deep_research = DeepResearchOrchestrator(self.settings.vault_root)
        self._research_pending: dict[str, DeepResearchPendingConfirmation] = {}

    async def _handle_research_callback(self, update: Update) -> bool:  # noqa: PLR0911
        """Handle deep-research confirmation callbacks."""
        callback = update.callback_query
        if callback is None or not callback.data or not callback.data.startswith("dr:"):
            return False
        if callback.from_user is None:
            return True

        user_id = callback.from_user.id
        if not self._is_authorized(user_id):
            await callback.answer()
            return True

        parts = callback.data.split(":")
        if len(parts) != CALLBACK_PARTS:
            await callback.answer("Invalid deep research action")
            return True

        action = parts[1]
        token = parts[2]
        pending = self._research_pending.get(token)
        if pending is None:
            await callback.answer("This request expired")
            return True

        # Authorization check: ensure the user who clicked matches the pending request
        if pending.user_id != user_id:
            await callback.answer("Not authorized for this action")
            return True

        # Remove the pending entry after authorization check passes
        self._research_pending.pop(token, None)

        if action == "cancel":
            await callback.answer("Deep research cancelled")
            await callback.edit_message_reply_markup(reply_markup=None)
            return True

        if action != "confirm":
            await callback.answer("Invalid deep research action")
            return True

        await callback.answer("Starting deep research")
        await callback.edit_message_reply_markup(reply_markup=None)
        await self._run_deep_research_job(
            chat_id=callback.message.chat_id,
            in_message_id=callback.message.message_id,
            pending=pending,
        )
        return True

    async def _maybe_handle_deep_research(
        self,
        update: Update,
        user_id: int,
        session_id: str,
        text: str,
    ) -> bool:
        """Classify request via dr-gate and handle deep-research path."""
        if not self.opencode or not hasattr(self, "deep_research"):
            return False

        selected_model = (
            self.model_selector.get_model_for_user(user_id) if self.model_selector else None
        )
        try:
            decision = await self.deep_research.classify_request(
                opencode=self.opencode,
                session_id=session_id,
                question=text,
                model=selected_model,
            )
        except Exception as error:
            logger.warning("deep_research_gate_failed", error=str(error))
            return False

        if decision.effort != "deep":
            return False

        needs_confirmation = self._needs_confirmation(decision)
        if needs_confirmation:
            token = uuid4().hex[:10]
            self._research_pending[token] = DeepResearchPendingConfirmation(
                session_id=session_id,
                user_id=user_id,
                text=text,
                model=selected_model,
            )
            message = update.effective_message
            if message is None:
                return True
            prompt = (
                decision.suggested_user_confirmation
                or "This looks like a deep research task. Run deep research now?"
            )
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Run deep research", callback_data=f"dr:confirm:{token}"
                        )
                    ],
                    [InlineKeyboardButton("Cancel", callback_data=f"dr:cancel:{token}")],
                ]
            )
            await message.reply_text(prompt, reply_markup=keyboard)
            return True

        await self._run_deep_research_job(
            chat_id=update.effective_message.chat_id,
            in_message_id=update.effective_message.message_id,
            pending=DeepResearchPendingConfirmation(
                session_id=session_id,
                user_id=user_id,
                text=text,
                model=selected_model,
            ),
        )
        return True

    @staticmethod
    def _needs_confirmation(decision: DeepResearchDecision) -> bool:
        """Decide whether deep research requires explicit confirmation."""
        return bool(decision.needs_deep_confirmation)

    async def _run_deep_research_job(
        self,
        *,
        chat_id: int,
        in_message_id: int,
        pending: DeepResearchPendingConfirmation,
    ) -> None:
        """Execute deep research and report result to Telegram."""
        if self.app is None or self.opencode is None:
            return

        await self.app.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=in_message_id,
            text="Deep research started. This can take several minutes.",
        )
        try:
            result = await self.deep_research.run_job(
                opencode=self.opencode,
                session_id=pending.session_id,
                user_id=pending.user_id,
                question=pending.text,
                model=pending.model,
            )
        except Exception as error:
            logger.error("deep_research_failed", error=str(error), exc_info=True)
            await self.app.bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=in_message_id,
                text=f"Deep research failed: {str(error)[:300]}",
            )
            return

        await self.app.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=in_message_id,
            text=(
                "Deep research completed.\n"
                f"Job: {result.job_id}\n"
                f"Report: {result.report_path}\n"
                f"Audit: {result.audit_path or '-'}"
            ),
        )
