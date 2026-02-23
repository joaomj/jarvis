"""SQLite database for user verification and message audit.

Minimal database layer for single-user bot.

The Database class is composed of mixins for each domain:
- UserOperations: Authorization and state management
- MessageOperations: Audit trail and response logging
- BookmarkOperations: X bookmark storage
- OAuthOperations: OAuth token storage
"""

import sqlite3
from pathlib import Path

from jarvis.database.bookmarks import BookmarkOperations
from jarvis.database.feedback import FeedbackOperations
from jarvis.database.messages import MessageOperations
from jarvis.database.oauth import OAuthOperations
from jarvis.database.sessions import SessionOperations
from jarvis.database.users import UserOperations
from jarvis.exceptions import DatabaseError
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class Database(
    UserOperations,
    MessageOperations,
    BookmarkOperations,
    OAuthOperations,
    FeedbackOperations,
    SessionOperations,
):
    """SQLite database manager combining all domain operations."""

    def __init__(
        self,
        db_path: str,
        message_content_max_length: int = 1000,
        response_cleanup_days: int = 30,
    ):
        """Initialize database.

        Args:
            db_path: Path to SQLite database file.
            message_content_max_length: Max characters to store per message.
            response_cleanup_days: Days to keep responses before cleanup.

        Raises:
            DatabaseError: If initialization fails.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._message_content_max_length = message_content_max_length
        self._response_cleanup_days = response_cleanup_days
        try:
            self._init_db()
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            error_msg = f"Failed to initialize database at {db_path}"
            logger.critical("database_init_failed", path=db_path, error=str(e))
            raise DatabaseError(error_msg, operation="init_db", details=str(e)) from e
