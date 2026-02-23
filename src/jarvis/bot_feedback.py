"""Feedback and response delivery mixin for ``JarvisBot``."""

# mypy: ignore-errors

from __future__ import annotations

from telegram import Update

from jarvis.bot_constants import build_feedback_keyboard
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class BotFeedbackMixin:
    """Methods for response sending and feedback callbacks."""

    async def _send_response(
        self,
        update: Update,
        parts: list[dict[str, object]],
        turn_id: int | None = None,
    ) -> None:
        """Send response to user with optional feedback buttons."""
        msg = update.effective_message
        if msg is None:
            return

        formatted_chunks = self.formatter.format_response(parts)
        total_chunks = len(formatted_chunks)
        for index, chunk in enumerate(formatted_chunks):
            is_last_chunk = index == total_chunks - 1
            reply_markup = build_feedback_keyboard(turn_id) if is_last_chunk and turn_id else None
            try:
                sent_msg = await msg.reply_text(
                    chunk,
                    parse_mode="MarkdownV2",
                    reply_markup=reply_markup,
                )
            except Exception as error:
                logger.warning("markdown_send_failed", error=str(error))
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
        """Send a non-OpenCode response with feedback buttons."""
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

        try:
            sent_msg = await msg.reply_text(
                response_text,
                parse_mode=parse_mode,
                reply_markup=build_feedback_keyboard(turn_id),
            )
        except Exception as error:
            logger.warning("feedback_message_send_failed", error=str(error))
            sent_msg = await msg.reply_text(
                response_text,
                reply_markup=build_feedback_keyboard(turn_id),
            )

        if sent_msg:
            self.db.set_out_message_id(turn_id, sent_msg.message_id)

    async def _handle_error(
        self,
        update: Update,
        error: str,
        user_id: int | None = None,
        prompt_text: str | None = None,
    ) -> None:
        """Send user-facing error response."""
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
            return

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
            vote = 1 if parts[2] == "up" else -1
        except ValueError:
            logger.warning("invalid_turn_id", data=data)
            await callback.answer()
            return

        success = self.db.record_vote(turn_id, user_id, vote)
        if success:
            logger.info("feedback_recorded", turn_id=turn_id, vote=vote, user_id=user_id)
        else:
            logger.warning("feedback_record_failed", turn_id=turn_id, user_id=user_id)

        await callback.answer()
        try:
            await callback.edit_message_reply_markup(reply_markup=None)
        except Exception as error:
            logger.warning("remove_keyboard_failed", error=str(error))
