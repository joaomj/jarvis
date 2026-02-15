"""SQLite database for user verification and message audit.

Minimal database layer for single-user bot.
"""

import sqlite3
from pathlib import Path

from jarvis.exceptions import DatabaseError
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: str):
        """Initialize database.

        Args:
            db_path: Path to SQLite database file.

        Raises:
            DatabaseError: If initialization fails.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._init_db()
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            error_msg = f"Failed to initialize database at {db_path}"
            logger.critical("database_init_failed", path=db_path, error=str(e))
            raise DatabaseError(error_msg, operation="init_db", details=str(e)) from e

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    allowed BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER,
                    direction TEXT,  -- 'in' or 'out'
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS user_states (
                    telegram_id INTEGER PRIMARY KEY,
                    state_type TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    telegram_id INTEGER NOT NULL,
                    model TEXT,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_responses_telegram_id ON responses(telegram_id);
                CREATE INDEX IF NOT EXISTS idx_responses_created_at ON responses(created_at);
            """)

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
                    "SELECT allowed FROM users WHERE telegram_id = ?",
                    (telegram_id,)
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
                conn.execute(
                    "INSERT OR IGNORE INTO users (telegram_id) VALUES (?)",
                    (telegram_id,)
                )
                logger.info("user_added", telegram_id=telegram_id)
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            error_msg = f"Failed to add user {telegram_id}"
            logger.error("user_add_failed", telegram_id=telegram_id, error=str(e))
            raise DatabaseError(error_msg, operation="add_user", details=str(e)) from e

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
                    (telegram_id, direction, content[:1000])  # Limit content size
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

    def cleanup_old_responses(self, days: int = 30) -> int:
        """Delete responses older than specified days.

        Args:
            days: Number of days to keep (default 30).

        Returns:
            Number of rows deleted.
        """
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
