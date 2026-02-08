"""SQLite database for user verification and message audit.

Minimal database layer for single-user bot.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: str):
        """Initialize database.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

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
            """)

    def is_user_allowed(self, telegram_id: int) -> bool:
        """Check if user is in allowlist.

        Args:
            telegram_id: Telegram user ID.

        Returns:
            bool: True if user is allowed.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT allowed FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            result = cursor.fetchone()
            return bool(result and result[0])

    def add_user(self, telegram_id: int) -> None:
        """Add user to allowlist.

        Args:
            telegram_id: Telegram user ID.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (telegram_id) VALUES (?)",
                (telegram_id,)
            )
            logger.info("user_added", telegram_id=telegram_id)

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
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO messages (telegram_id, direction, content)
                   VALUES (?, ?, ?)""",
                (telegram_id, direction, content[:1000])  # Limit content size
            )

    def get_user_message_count(self, telegram_id: int) -> int:
        """Get message count for user.

        Args:
            telegram_id: Telegram user ID.

        Returns:
            int: Number of messages.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE telegram_id = ?",
                (telegram_id,)
            )
            return cursor.fetchone()[0]
