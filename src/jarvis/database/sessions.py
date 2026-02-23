"""Session management database operations.

Stores OpenCode session mappings with daily rotation for data sovereignty.

The session table tracks:
- telegram_user_id: The Telegram user who owns the session
- opencode_session_id: The OpenCode Server session ID
- session_title: Human-readable title for the session
- date_key: YYYY-MM-DD for daily rotation
- model_used: Last model used (for debugging/auditing)
- created_at: When the session was created

Each day creates a new session automatically.
"""

import sqlite3
from datetime import date, timedelta

from jarvis.database.core import DatabaseCore
from jarvis.exceptions import DatabaseError
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class SessionOperations(DatabaseCore):
    """OpenCode session management with daily rotation."""

    def get_todays_session(self, telegram_user_id: int) -> str | None:
        """Get today's session ID for a user.

        Args:
            telegram_user_id: The Telegram user ID.

        Returns:
            OpenCode session ID if found, None otherwise.
        """
        today = date.today().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT opencode_session_id FROM opencode_sessions
                       WHERE telegram_user_id = ? AND date_key = ?""",
                    (telegram_user_id, today),
                )
                row = cursor.fetchone()
                if row:
                    logger.debug(
                        "session_found_in_db",
                        user_id=telegram_user_id,
                        session_id=row[0],
                        date=today,
                    )
                    return str(row[0])
                return None
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.error(
                "session_lookup_failed",
                user_id=telegram_user_id,
                date=today,
                error=str(e),
            )
            raise DatabaseError(
                f"Failed to lookup session for user {telegram_user_id}",
                operation="get_todays_session",
                details=str(e),
            ) from e

    def create_session_record(
        self,
        telegram_user_id: int,
        opencode_session_id: str,
        session_title: str,
    ) -> None:
        """Create a new session record for today.

        Args:
            telegram_user_id: The Telegram user ID.
            opencode_session_id: The OpenCode session ID.
            session_title: The session title.
        """
        today = date.today().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO opencode_sessions
                       (telegram_user_id, opencode_session_id, session_title, date_key)
                       VALUES (?, ?, ?, ?)""",
                    (telegram_user_id, opencode_session_id, session_title, today),
                )
                logger.info(
                    "session_record_created",
                    user_id=telegram_user_id,
                    session_id=opencode_session_id,
                    title=session_title,
                    date=today,
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.error(
                "session_record_create_failed",
                user_id=telegram_user_id,
                session_id=opencode_session_id,
                error=str(e),
            )
            raise DatabaseError(
                f"Failed to create session record for user {telegram_user_id}",
                operation="create_session_record",
                details=str(e),
            ) from e

    def update_session_model(
        self,
        opencode_session_id: str,
        model: str,
    ) -> None:
        """Update the model used for a session.

        Args:
            opencode_session_id: The OpenCode session ID.
            model: The model ID (e.g., "opencode/glm-5").
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """UPDATE opencode_sessions SET model_used = ?
                       WHERE opencode_session_id = ?""",
                    (model, opencode_session_id),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "session_model_update_failed",
                session_id=opencode_session_id,
                model=model,
                error=str(e),
            )

    def get_session_history(
        self,
        telegram_user_id: int,
        limit: int = 10,
    ) -> list[dict[str, str]]:
        """Get recent session history for a user.

        Args:
            telegram_user_id: The Telegram user ID.
            limit: Maximum number of sessions to return.

        Returns:
            List of session records with date, title, model.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """SELECT date_key, session_title, model_used, created_at
                       FROM opencode_sessions
                       WHERE telegram_user_id = ?
                       ORDER BY date_key DESC
                       LIMIT ?""",
                    (telegram_user_id, limit),
                )
                return [
                    {
                        "date": row["date_key"],
                        "title": row["session_title"],
                        "model": row["model_used"],
                        "created_at": row["created_at"],
                    }
                    for row in cursor.fetchall()
                ]
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.error(
                "session_history_lookup_failed",
                user_id=telegram_user_id,
                error=str(e),
            )
            return []

    def cleanup_old_sessions(self, days_to_keep: int = 30) -> int:
        """Delete session records older than specified days.

        Args:
            days_to_keep: Number of days of history to retain.

        Returns:
            Number of records deleted.
        """
        cutoff_date = (date.today() - timedelta(days=days_to_keep)).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM opencode_sessions WHERE date_key < ?",
                    (cutoff_date,),
                )
                deleted = cursor.rowcount
                if deleted > 0:
                    logger.info(
                        "old_sessions_cleaned",
                        deleted=deleted,
                        cutoff_date=cutoff_date,
                    )
                return deleted
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.error(
                "session_cleanup_failed",
                cutoff_date=cutoff_date,
                error=str(e),
            )
            return 0
