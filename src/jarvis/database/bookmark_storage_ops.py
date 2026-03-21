"""Bookmark storage and query operations."""

from __future__ import annotations

import sqlite3

from jarvis.database.core import DatabaseCore
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class BookmarkStorageOperations(DatabaseCore):
    """Storage operations for bookmark rows."""

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
        content_kind: str = "unknown",
        content_title: str | None = None,
        content_preview: str | None = None,
        content_text: str = "",
        source_unwound_url: str | None = None,
        artifact_path: str | None = None,
        content_hash: str | None = None,
    ) -> None:
        """Save a bookmark row with upsert semantics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute(
                    """INSERT INTO x_bookmarks
                       (tweet_id, author_username, author_name, author_verified, text,
                        note_text, created_at, tweet_url, like_count, retweet_count,
                        reply_count, impression_count, bookmark_count, media_urls,
                        urls_expanded, context_annotations, raw_json, last_synced_at,
                        content_kind, content_title, content_preview, content_text,
                        source_unwound_url, artifact_path, content_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP,
                               ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(tweet_id) DO UPDATE SET
                           author_username=excluded.author_username,
                           author_name=excluded.author_name,
                           author_verified=excluded.author_verified,
                           text=excluded.text,
                           note_text=excluded.note_text,
                           created_at=excluded.created_at,
                           tweet_url=excluded.tweet_url,
                           like_count=excluded.like_count,
                           retweet_count=excluded.retweet_count,
                           reply_count=excluded.reply_count,
                           impression_count=excluded.impression_count,
                           bookmark_count=excluded.bookmark_count,
                           media_urls=excluded.media_urls,
                           urls_expanded=excluded.urls_expanded,
                           context_annotations=excluded.context_annotations,
                           raw_json=excluded.raw_json,
                           last_synced_at=CURRENT_TIMESTAMP,
                           content_kind=excluded.content_kind,
                           content_title=excluded.content_title,
                           content_preview=excluded.content_preview,
                           content_text=excluded.content_text,
                           source_unwound_url=excluded.source_unwound_url,
                           artifact_path=excluded.artifact_path,
                           content_hash=excluded.content_hash""",
                    (
                        tweet_id,
                        author_username,
                        author_name,
                        author_verified,
                        text,
                        note_text,
                        created_at,
                        tweet_url,
                        like_count,
                        retweet_count,
                        reply_count,
                        impression_count,
                        bookmark_count,
                        media_urls,
                        urls_expanded,
                        context_annotations,
                        raw_json,
                        content_kind,
                        content_title,
                        content_preview,
                        content_text,
                        source_unwound_url,
                        artifact_path,
                        content_hash,
                    ),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.error("save_bookmark_failed", tweet_id=tweet_id, error=str(error))
            raise

    def get_all_bookmark_ids(self) -> set[str]:
        """Get all bookmark tweet IDs."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                cursor = conn.execute("SELECT tweet_id FROM x_bookmarks")
                return {row[0] for row in cursor.fetchall()}
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning("get_all_bookmark_ids_failed", error=str(error))
            return set()

    def get_total_bookmarks_count(self) -> int:
        """Get total distinct bookmark count in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                cursor = conn.execute("SELECT COUNT(DISTINCT tweet_id) FROM x_bookmarks")
                row = cursor.fetchone()
                return int(row[0]) if row else 0
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning("get_total_bookmarks_count_failed", error=str(error))
            return 0

    def mark_all_bookmarks_unsynced(self) -> None:
        """Mark all bookmarks as unsynced for full mirror reconciliation."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("UPDATE x_bookmarks SET last_synced_at = NULL")
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning("mark_all_bookmarks_unsynced_failed", error=str(error))

    def delete_unsynced_bookmarks(self) -> int:
        """Delete bookmarks not seen during current full reconciliation."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                cursor = conn.execute("DELETE FROM x_bookmarks WHERE last_synced_at IS NULL")
                return cursor.rowcount
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning("delete_unsynced_bookmarks_failed", error=str(error))
            return 0

    def get_bookmarks_by_time_range(self, start_date: str, end_date: str) -> list[dict]:
        """Get bookmarks within time range."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                cursor = conn.execute(
                    """SELECT tweet_id, author_username, author_name, author_verified,
                              text, note_text, created_at, bookmarked_at, tweet_url,
                              like_count, retweet_count, reply_count, impression_count,
                              bookmark_count, media_urls, urls_expanded, content_kind,
                              content_title, content_preview, content_text, source_unwound_url
                       FROM x_bookmarks
                       WHERE bookmarked_at >= ? AND bookmarked_at <= ?
                       ORDER BY bookmarked_at DESC""",
                    (start_date, end_date),
                )
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning(
                "get_bookmarks_by_time_range_failed",
                start_date=start_date,
                end_date=end_date,
                error=str(error),
            )
            return []

    def get_bookmark_by_id(self, tweet_id: str) -> dict | None:
        """Get a specific bookmark by tweet ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                cursor = conn.execute(
                    """SELECT tweet_id, author_username, author_name, author_verified,
                              text, note_text, created_at, bookmarked_at, tweet_url,
                              like_count, retweet_count, reply_count, impression_count,
                              bookmark_count, media_urls, urls_expanded, raw_json,
                              content_kind, content_title, content_preview, content_text,
                              source_unwound_url, artifact_path, content_hash
                       FROM x_bookmarks
                       WHERE tweet_id = ?""",
                    (tweet_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row, strict=True))
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning("get_bookmark_by_id_failed", tweet_id=tweet_id, error=str(error))
            return None

    def update_bookmark_artifact(
        self,
        tweet_id: str,
        artifact_path: str,
        content_hash: str,
    ) -> None:
        """Update bookmark with artifact path and content hash."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute(
                    """UPDATE x_bookmarks
                       SET artifact_path = ?, content_hash = ?
                       WHERE tweet_id = ?""",
                    (artifact_path, content_hash, tweet_id),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.error("update_bookmark_artifact_failed", tweet_id=tweet_id, error=str(error))
            raise
