"""Tests for bookmark database operations."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from jarvis.database import Database


class TestDatabaseBookmarks:
    """Test database bookmark operations."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database."""
        db_path = tmp_path / "test.db"
        return Database(str(db_path))

    def test_save_bookmark(self, db):
        """Test saving a bookmark."""
        db.save_bookmark(
            tweet_id="123456789",
            author_username="testuser",
            author_name="Test User",
            author_verified=False,
            text="Test tweet",
            note_text=None,
            created_at=None,
            tweet_url="https://twitter.com/testuser/status/123456789",
            like_count=100,
            retweet_count=50,
            reply_count=10,
            impression_count=1000,
            bookmark_count=5,
            media_urls='["url1", "url2"]',
            urls_expanded='["expanded1", "expanded2"]',
            context_annotations="[]",
            raw_json="{}",
        )

        bookmark = db.get_bookmark_by_id("123456789")
        assert bookmark is not None
        assert bookmark["tweet_id"] == "123456789"
        assert bookmark["author_username"] == "testuser"

    def test_save_bookmark_upsert_preserves_row_identity(self, db):
        """Test upsert updates bookmark without replacing row."""
        bookmark_payload = {
            "tweet_id": "same-id",
            "author_username": "user1",
            "author_name": "User 1",
            "author_verified": False,
            "text": "Original",
            "note_text": None,
            "created_at": None,
            "tweet_url": "https://x.com/user1/status/same-id",
            "like_count": 0,
            "retweet_count": 0,
            "reply_count": 0,
            "impression_count": 0,
            "bookmark_count": 0,
            "media_urls": "[]",
            "urls_expanded": "[]",
            "context_annotations": "[]",
            "raw_json": "{}",
        }
        db.save_bookmark(**bookmark_payload)
        with sqlite3.connect(db.db_path) as conn:
            first_row_id = conn.execute(
                "SELECT id FROM x_bookmarks WHERE tweet_id = ?",
                ("same-id",),
            ).fetchone()[0]

        db.save_bookmark(**(bookmark_payload | {"text": "Updated"}))
        with sqlite3.connect(db.db_path) as conn:
            second_row_id = conn.execute(
                "SELECT id FROM x_bookmarks WHERE tweet_id = ?",
                ("same-id",),
            ).fetchone()[0]

        bookmark = db.get_bookmark_by_id("same-id")
        assert first_row_id == second_row_id
        assert bookmark is not None
        assert bookmark["text"] == "Updated"

    def test_bookmark_sync_mark_and_prune(self, db):
        """Test mark unsynced and prune flow for mirror reconcile."""
        for tweet_id, text in (("keep", "Keep"), ("drop", "Drop")):
            db.save_bookmark(
                tweet_id=tweet_id,
                author_username="user",
                author_name="User",
                author_verified=False,
                text=text,
                note_text=None,
                created_at=None,
                tweet_url=f"https://x.com/user/status/{tweet_id}",
                like_count=0,
                retweet_count=0,
                reply_count=0,
                impression_count=0,
                bookmark_count=0,
                media_urls="[]",
                urls_expanded="[]",
                context_annotations="[]",
                raw_json="{}",
            )

        db.mark_all_bookmarks_unsynced()
        db.save_bookmark(
            tweet_id="keep",
            author_username="user",
            author_name="User",
            author_verified=False,
            text="Keep",
            note_text=None,
            created_at=None,
            tweet_url="https://x.com/user/status/keep",
            like_count=0,
            retweet_count=0,
            reply_count=0,
            impression_count=0,
            bookmark_count=0,
            media_urls="[]",
            urls_expanded="[]",
            context_annotations="[]",
            raw_json="{}",
        )

        deleted = db.delete_unsynced_bookmarks()
        assert deleted == 1
        assert db.get_bookmark_by_id("keep") is not None
        assert db.get_bookmark_by_id("drop") is None
        assert db.get_total_bookmarks_count() == 1

    def test_get_bookmarks_by_time_range(self, db):
        """Test getting bookmarks by time range."""
        for tweet_id in ("1", "2"):
            db.save_bookmark(
                tweet_id=tweet_id,
                author_username=f"user{tweet_id}",
                author_name=f"User {tweet_id}",
                author_verified=False,
                text=f"Tweet {tweet_id}",
                note_text=None,
                created_at=None,
                tweet_url=f"https://twitter.com/user{tweet_id}/status/{tweet_id}",
                like_count=0,
                retweet_count=0,
                reply_count=0,
                impression_count=0,
                bookmark_count=0,
                media_urls="[]",
                urls_expanded="[]",
                context_annotations="[]",
                raw_json="{}",
            )

        bookmarks = db.get_bookmarks_by_time_range(
            (datetime.now(UTC) - timedelta(days=7)).isoformat(),
            (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        )
        assert len(bookmarks) == 2

    def test_sync_status(self, db):
        """Test sync status operations."""
        db.update_sync_status(last_tweet_id="123456", total_bookmarks=100, sync_in_progress=True)

        status = db.get_sync_status()
        assert status is not None
        assert status["last_tweet_id"] == "123456"
        assert status["total_bookmarks"] == 100
        assert status["sync_in_progress"] == 1

        db.update_sync_status(sync_in_progress=False)
        status = db.get_sync_status()
        assert status["sync_in_progress"] == 0

    def test_first_sync_status(self, db):
        """Test first sync complete status."""
        assert db.get_first_sync_status() is False
        db.update_sync_status(first_sync_complete=True)
        assert db.get_first_sync_status() is True
