"""Feedback operations for Telegram turn ratings."""

import sqlite3

from jarvis.database.core import DatabaseCore
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class FeedbackOperations(DatabaseCore):
    """Mixin for telegram_turn_feedback table operations."""

    def create_turn(  # noqa: PLR0913
        self,
        telegram_user_id: int,
        telegram_chat_id: int,
        source: str,
        prompt_text: str,
        response_text: str,
        telegram_in_message_id: int | None = None,
        opencode_session_id: str | None = None,
        model_full: str | None = None,
        agent: str | None = None,
    ) -> int:
        """Create a new feedback turn record.

        Args:
            telegram_user_id: Telegram user ID.
            telegram_chat_id: Telegram chat ID.
            source: Source of the turn (opencode|bookmarks|model_select|error|system).
            prompt_text: The user's prompt text.
            response_text: The assistant's response text.
            telegram_in_message_id: Optional incoming message ID.
            opencode_session_id: Optional OpenCode session ID.
            model_full: Optional full model name (e.g., openai/gpt-4o).
            agent: Optional agent name.

        Returns:
            The ID of the created turn record.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO telegram_turn_feedback (
                        telegram_user_id, telegram_chat_id, telegram_in_message_id,
                        source, opencode_session_id, model_full, agent,
                        prompt_text, response_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        telegram_user_id,
                        telegram_chat_id,
                        telegram_in_message_id,
                        source,
                        opencode_session_id,
                        model_full,
                        agent,
                        prompt_text,
                        response_text,
                    ),
                )
                lastrowid = cursor.lastrowid
                if lastrowid is None:
                    return 0
                return lastrowid
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.error("create_turn_failed", error=str(e))
            return 0

    def set_out_message_id(self, turn_id: int, telegram_out_message_id: int) -> None:
        """Set the outgoing message ID for a turn.

        Args:
            turn_id: The turn record ID.
            telegram_out_message_id: The Telegram message ID containing feedback buttons.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE telegram_turn_feedback SET telegram_out_message_id = ? WHERE id = ?",
                    (telegram_out_message_id, turn_id),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning("set_out_message_id_failed", turn_id=turn_id, error=str(e))

    def record_vote(self, turn_id: int, telegram_user_id: int, vote: int) -> bool:
        """Record a vote for a turn.

        Args:
            turn_id: The turn record ID.
            telegram_user_id: The Telegram user ID (for authorization check).
            vote: Vote value (1 for up, -1 for down).

        Returns:
            True if vote was recorded, False if not authorized or turn not found.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT telegram_user_id FROM telegram_turn_feedback WHERE id = ?",
                    (turn_id,),
                )
                row = cursor.fetchone()
                if not row or row[0] != telegram_user_id:
                    logger.warning(
                        "unauthorized_vote_attempt",
                        turn_id=turn_id,
                        telegram_user_id=telegram_user_id,
                    )
                    return False

                conn.execute(
                    """
                    UPDATE telegram_turn_feedback
                    SET vote = ?, voted_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (vote, turn_id),
                )
                logger.info("vote_recorded", turn_id=turn_id, vote=vote)
                return True
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.error("record_vote_failed", turn_id=turn_id, error=str(e))
            return False

    def get_turn(self, turn_id: int) -> dict | None:
        """Get a turn record by ID.

        Args:
            turn_id: The turn record ID.

        Returns:
            Turn record as dict, or None if not found.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM telegram_turn_feedback WHERE id = ?",
                    (turn_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row, strict=True))
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning("get_turn_failed", turn_id=turn_id, error=str(e))
            return None
