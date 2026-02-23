"""User management and state operations."""

import sqlite3

from jarvis.database.core import DatabaseCore
from jarvis.exceptions import DatabaseError
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class UserOperations(DatabaseCore):
    """User authorization and state management."""

    def is_user_allowed(self, telegram_id: int) -> bool:
        """Check if user is in allowlist.

        Args:
            telegram_id: Telegram user ID.

        Returns:
            bool: True if user is allowed.

        Raises:
            DatabaseError: If query fails (CRITICAL - affects security).
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT allowed FROM users WHERE telegram_id = ?", (telegram_id,)
                )
                result = cursor.fetchone()
                return bool(result and result[0])
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            error_msg = f"Failed to check authorization for user {telegram_id}"
            logger.critical("user_auth_check_failed", telegram_id=telegram_id, error=str(e))
            raise DatabaseError(error_msg, operation="is_user_allowed", details=str(e)) from e

    def add_user(self, telegram_id: int) -> None:
        """Add user to allowlist.

        Args:
            telegram_id: Telegram user ID.

        Raises:
            DatabaseError: If adding user fails.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("INSERT OR IGNORE INTO users (telegram_id) VALUES (?)", (telegram_id,))
                logger.info("user_added", telegram_id=telegram_id)
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            error_msg = f"Failed to add user {telegram_id}"
            logger.error("user_add_failed", telegram_id=telegram_id, error=str(e))
            raise DatabaseError(error_msg, operation="add_user", details=str(e)) from e

    def set_user_state(self, telegram_id: int, state_type: str) -> None:
        """Set active state for a user.

        Args:
            telegram_id: Telegram user ID.
            state_type: State type to set.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO user_states (telegram_id, state_type)
                       VALUES (?, ?)
                       ON CONFLICT(telegram_id) DO UPDATE SET
                          state_type = excluded.state_type,
                          created_at = CURRENT_TIMESTAMP""",
                    (telegram_id, state_type),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "user_state_set_failed",
                telegram_id=telegram_id,
                state_type=state_type,
                error=str(e),
            )

    def get_user_state(self, telegram_id: int) -> str | None:
        """Get active state for a user.

        Args:
            telegram_id: Telegram user ID.

        Returns:
            State type or None if not set.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT state_type FROM user_states WHERE telegram_id = ?",
                    (telegram_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return str(row[0])
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "user_state_get_failed",
                telegram_id=telegram_id,
                error=str(e),
            )
            return None

    def clear_user_state(self, telegram_id: int) -> None:
        """Clear active state for a user.

        Args:
            telegram_id: Telegram user ID.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM user_states WHERE telegram_id = ?",
                    (telegram_id,),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "user_state_clear_failed",
                telegram_id=telegram_id,
                error=str(e),
            )
