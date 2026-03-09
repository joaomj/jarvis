"""OpenCode response handling mixin for ``JarvisBot``."""

# mypy: ignore-errors
from __future__ import annotations

from typing import Any

from telegram import Update

from jarvis.logging_config import get_logger
from jarvis.opencode_client import OpenCodeError

logger = get_logger(__name__)


class BotOpenCodeMixin:
    """Methods for handling OpenCode responses and fallbacks."""

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
