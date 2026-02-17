"""Message audit and response logging operations."""

import sqlite3

from jarvis.database.core import DatabaseCore
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class MessageOperations(DatabaseCore):
    """Message audit trail and response logging."""

    def log_message(
        self,
        telegram_id: int,
        direction: str,
        content: str
    ) -> None:
        """Log message to audit trail.

        Args:
            telegram_id: Telegram user ID.
            direction: 'in' or 'out'.
            content: Message content.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO messages (telegram_id, direction, content)
                       VALUES (?, ?, ?)""",
                    (telegram_id, direction, content[:self._message_content_max_length])
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "message_log_failed",
                telegram_id=telegram_id,
                direction=direction,
                error=str(e),
            )

    def get_user_message_count(self, telegram_id: int) -> int:
        """Get message count for user.

        Args:
            telegram_id: Telegram user ID.

        Returns:
            int: Number of messages.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE telegram_id = ?",
                    (telegram_id,)
                )
                return cursor.fetchone()[0]
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "message_count_failed",
                telegram_id=telegram_id,
                error=str(e),
            )
            return 0

    def log_response(
        self,
        session_id: str,
        telegram_id: int,
        model: str | None,
        content: str,
    ) -> None:
        """Log OpenCode response to database.

        Args:
            session_id: OpenCode session ID.
            telegram_id: Telegram user ID.
            model: Model used for this response.
            content: Full response content.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO responses (session_id, telegram_id, model, content)
                       VALUES (?, ?, ?, ?)""",
                    (session_id, telegram_id, model, content),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "response_log_failed",
                session_id=session_id,
                telegram_id=telegram_id,
                model=model,
                error=str(e),
            )

    def cleanup_old_responses(self, days: int | None = None) -> int:
        """Delete responses older than specified days.

        Args:
            days: Number of days to keep (default from config).

        Returns:
            Number of rows deleted.
        """
        days = days if days is not None else self._response_cleanup_days
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """DELETE FROM responses
                       WHERE created_at < datetime('now', '-' || ? || ' days')""",
                    (days,),
                )
                deleted = cursor.rowcount
                if deleted > 0:
                    logger.info("responses_cleaned", deleted=deleted, days=days)
                return deleted
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "response_cleanup_failed",
                days=days,
                error=str(e),
            )
            return 0
