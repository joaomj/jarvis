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

                CREATE TABLE IF NOT EXISTS x_bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id TEXT UNIQUE NOT NULL,
                    author_username TEXT NOT NULL,
                    author_name TEXT,
                    author_verified BOOLEAN DEFAULT 0,
                    text TEXT NOT NULL,
                    note_text TEXT,
                    created_at TIMESTAMP,
                    bookmarked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tweet_url TEXT NOT NULL,
                    like_count INTEGER DEFAULT 0,
                    retweet_count INTEGER DEFAULT 0,
                    reply_count INTEGER DEFAULT 0,
                    impression_count INTEGER DEFAULT 0,
                    bookmark_count INTEGER DEFAULT 0,
                    media_urls TEXT,
                    urls_expanded TEXT,
                    context_annotations TEXT,
                    raw_json TEXT,
                    last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS x_sync_status (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    last_sync_date TEXT,
                    last_sync_at TIMESTAMP,
                    last_tweet_id TEXT,
                    total_bookmarks INTEGER DEFAULT 0,
                    sync_in_progress BOOLEAN DEFAULT 0,
                    first_sync_complete BOOLEAN DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_bookmarks_bookmarked_at ON x_bookmarks(bookmarked_at);
                CREATE INDEX IF NOT EXISTS idx_bookmarks_created_at ON x_bookmarks(created_at);

                INSERT OR IGNORE INTO x_sync_status (id) VALUES (1);
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

    def save_bookmark(  # noqa: PLR0913
        self,
        tweet_id: str,
        author_username: str,
        author_name: str,
        author_verified: bool,
        text: str,
        note_text: str | None,
        created_at: str | None,
        tweet_url: str,
        like_count: int,
        retweet_count: int,
        reply_count: int,
        impression_count: int,
        bookmark_count: int,
        media_urls: str,
        urls_expanded: str,
        context_annotations: str,
        raw_json: str,
    ) -> None:
        """Save a bookmark to database.

        Args:
            tweet_id: Tweet ID.
            author_username: Author username.
            author_name: Author display name.
            author_verified: Author verified status.
            text: Tweet text.
            note_text: User's private note.
            created_at: Tweet creation timestamp.
            tweet_url: Tweet URL.
            like_count: Number of likes.
            retweet_count: Number of retweets.
            reply_count: Number of replies.
            impression_count: Number of impressions.
            bookmark_count: Number of bookmarks.
            media_urls: JSON string of media URLs.
            urls_expanded: JSON string of expanded URLs.
            context_annotations: JSON string of context annotations.
            raw_json: Raw API response JSON.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO x_bookmarks
                       (tweet_id, author_username, author_name, author_verified, text,
                        note_text, created_at, tweet_url, like_count, retweet_count,
                        reply_count, impression_count, bookmark_count, media_urls,
                        urls_expanded, context_annotations, raw_json, last_synced_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (
                        tweet_id, author_username, author_name, author_verified, text,
                        note_text, created_at, tweet_url, like_count, retweet_count,
                        reply_count, impression_count, bookmark_count, media_urls,
                        urls_expanded, context_annotations, raw_json,
                    ),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "save_bookmark_failed",
                tweet_id=tweet_id,
                error=str(e),
            )

    def get_bookmarks_by_time_range(self, start_date: str, end_date: str) -> list[dict]:
        """Get bookmarks within time range.

        Args:
            start_date: Start date (ISO format or SQLite date function).
            end_date: End date (ISO format or SQLite date function).

        Returns:
            List of bookmark dictionaries.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT tweet_id, author_username, author_name, author_verified,
                              text, note_text, created_at, bookmarked_at, tweet_url,
                              like_count, retweet_count, reply_count, impression_count,
                              bookmark_count, media_urls, urls_expanded
                       FROM x_bookmarks
                       WHERE bookmarked_at >= ? AND bookmarked_at <= ?
                       ORDER BY bookmarked_at DESC""",
                    (start_date, end_date),
                )
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "get_bookmarks_by_time_range_failed",
                start_date=start_date,
                end_date=end_date,
                error=str(e),
            )
            return []

    def get_bookmark_by_id(self, tweet_id: str) -> dict | None:
        """Get a specific bookmark by tweet ID.

        Args:
            tweet_id: Tweet ID.

        Returns:
            Bookmark dictionary or None.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT tweet_id, author_username, author_name, author_verified,
                              text, note_text, created_at, bookmarked_at, tweet_url,
                              like_count, retweet_count, reply_count, impression_count,
                              bookmark_count, media_urls, urls_expanded, raw_json
                       FROM x_bookmarks
                       WHERE tweet_id = ?""",
                    (tweet_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row, strict=True))
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "get_bookmark_by_id_failed",
                tweet_id=tweet_id,
                error=str(e),
            )
            return None

    def get_sync_status(self) -> dict | None:
        """Get current sync status.

        Returns:
            Sync status dictionary or None.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT last_sync_date, last_sync_at, last_tweet_id, total_bookmarks,
                              sync_in_progress, first_sync_complete
                       FROM x_sync_status
                       WHERE id = 1""",
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row, strict=True))
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning("get_sync_status_failed", error=str(e))
            return None

    def update_sync_status(  # noqa: PLR0913
        self,
        last_sync_date: str | None = None,
        last_sync_at: str | None = None,
        last_tweet_id: str | None = None,
        total_bookmarks: int | None = None,
        sync_in_progress: bool | None = None,
        first_sync_complete: bool | None = None,
    ) -> None:
        """Update sync status.

        Args:
            last_sync_date: Last sync date string (YYYY-MM-DD).
            last_sync_at: Last sync timestamp.
            last_tweet_id: Last synced tweet ID.
            total_bookmarks: Total bookmark count.
            sync_in_progress: Whether sync is in progress.
            first_sync_complete: Whether first full sync is complete.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                updates = []
                params = []
                if last_sync_date is not None:
                    updates.append("last_sync_date = ?")
                    params.append(last_sync_date)
                if last_sync_at is not None:
                    updates.append("last_sync_at = ?")
                    params.append(last_sync_at)
                if last_tweet_id is not None:
                    updates.append("last_tweet_id = ?")
                    params.append(last_tweet_id)
                if total_bookmarks is not None:
                    updates.append("total_bookmarks = ?")
                    params.append(total_bookmarks)
                if sync_in_progress is not None:
                    updates.append("sync_in_progress = ?")
                    params.append(1 if sync_in_progress else 0)
                if first_sync_complete is not None:
                    updates.append("first_sync_complete = ?")
                    params.append(1 if first_sync_complete else 0)

                if updates:
                    query = f"UPDATE x_sync_status SET {', '.join(updates)} WHERE id = 1"  # noqa: S608
                    conn.execute(query, params)
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning("update_sync_status_failed", error=str(e))

    def get_first_sync_status(self) -> bool:
        """Check if first full sync has been completed.

        Returns:
            bool: True if first sync complete.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT first_sync_complete FROM x_sync_status WHERE id = 1"
                )
                row = cursor.fetchone()
                return bool(row and row[0]) if row else False
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning("get_first_sync_status_failed", error=str(e))
            return False
