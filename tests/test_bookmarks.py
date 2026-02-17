"""Tests for X bookmarks functionality."""

from datetime import UTC, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.bookmarks.client import XAPIClient
from jarvis.bookmarks.models import Author, Bookmark, TweetMetrics
from jarvis.bookmarks.parser import parse_bookmark
from jarvis.bookmarks.sync import BookmarkSync
from jarvis.database import Database


class TestBookmarkModels:
    """Test bookmark Pydantic models."""

    def test_author_model(self):
        """Test Author model."""
        author = Author(
            username="testuser",
            name="Test User",
            verified=True,
        )

        assert author.username == "testuser"
        assert author.name == "Test User"
        assert author.verified is True

    def test_tweet_metrics_model(self):
        """Test TweetMetrics model."""
        metrics = TweetMetrics(
            like_count=100,
            retweet_count=50,
            reply_count=10,
            impression_count=1000,
            bookmark_count=5,
        )

        assert metrics.like_count == 100
        assert metrics.retweet_count == 50
        assert metrics.reply_count == 10
        assert metrics.impression_count == 1000
        assert metrics.bookmark_count == 5

    def test_bookmark_model(self):
        """Test Bookmark model."""
        author = Author(username="testuser", name="Test User", verified=False)
        metrics = TweetMetrics(like_count=100)

        bookmark = Bookmark(
            tweet_id="123456789",
            author=author,
            text="Test tweet content",
            tweet_url="https://twitter.com/testuser/status/123456789",
            metrics=metrics,
            note_text=None,
            created_at=None,
            raw_json=None,
        )

        assert bookmark.tweet_id == "123456789"
        assert bookmark.author.username == "testuser"
        assert bookmark.text == "Test tweet content"
        assert bookmark.metrics.like_count == 100


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
            context_annotations='[]',
            raw_json='{}',
        )

        bookmark = db.get_bookmark_by_id("123456789")
        assert bookmark is not None
        assert bookmark["tweet_id"] == "123456789"
        assert bookmark["author_username"] == "testuser"

    def test_get_bookmarks_by_time_range(self, db):
        """Test getting bookmarks by time range."""
        from datetime import datetime

        db.save_bookmark(
            tweet_id="1",
            author_username="user1",
            author_name="User 1",
            author_verified=False,
            text="Old tweet",
            note_text=None,
            created_at=None,
            tweet_url="https://twitter.com/user1/status/1",
            like_count=0,
            retweet_count=0,
            reply_count=0,
            impression_count=0,
            bookmark_count=0,
            media_urls='[]',
            urls_expanded='[]',
            context_annotations='[]',
            raw_json='{}',
        )

        db.save_bookmark(
            tweet_id="2",
            author_username="user2",
            author_name="User 2",
            author_verified=False,
            text="Recent tweet",
            note_text=None,
            created_at=None,
            tweet_url="https://twitter.com/user2/status/2",
            like_count=0,
            retweet_count=0,
            reply_count=0,
            impression_count=0,
            bookmark_count=0,
            media_urls='[]',
            urls_expanded='[]',
            context_annotations='[]',
            raw_json='{}',
        )

        bookmarks = db.get_bookmarks_by_time_range(
            (datetime.now(UTC) - timedelta(days=7)).isoformat(),
            (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        )

        assert len(bookmarks) == 2

    def test_sync_status(self, db):
        """Test sync status operations."""
        db.update_sync_status(
            last_tweet_id="123456",
            total_bookmarks=100,
            sync_in_progress=True,
        )

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


class TestXAPIClient:
    """Test X API client."""

    @pytest.fixture
    def mock_client(self, tmp_path):
        """Create mock X API client."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.save_oauth_tokens(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_at="2099-01-01T00:00:00+00:00",
            scope="bookmark.read tweet.read users.read offline.access",
        )
        return XAPIClient(db, "test_client_id", "test_client_secret")

    @pytest.mark.asyncio
    async def test_get_bookmarks(self, mock_client):
        """Test fetching bookmarks."""
        mock_client._user_id = "test_user_id"

        mock_response = {
            "data": [
                {
                    "id": "123456789",
                    "text": "Test tweet",
                    "author_id": "author1",
                    "created_at": "2024-01-01T00:00:00.000Z",
                    "public_metrics": {
                        "like_count": 100,
                        "retweet_count": 50,
                    },
                }
            ],
            "includes": {
                "users": [
                    {
                        "id": "author1",
                        "username": "testuser",
                        "name": "Test User",
                        "verified": False,
                    }
                ]
            },
            "meta": {"result_count": 1},
        }

        with patch.object(mock_client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = MagicMock()
            mock_get.return_value = mock_response_obj

            bookmarks_data = await mock_client.get_bookmarks()

            assert "data" in bookmarks_data
            assert len(bookmarks_data["data"]) == 1
            assert bookmarks_data["data"][0]["id"] == "123456789"

    @pytest.mark.asyncio
    async def test_parse_bookmark(self, mock_client):
        """Test parsing bookmark from API data."""
        tweet_data = {
            "id": "123456789",
            "text": "Test tweet",
            "author_id": "author1",
            "created_at": "2024-01-01T00:00:00.000Z",
            "public_metrics": {
                "like_count": 100,
                "retweet_count": 50,
                "reply_count": 10,
                "impression_count": 1000,
                "bookmark_count": 5,
            },
            "entities": {
                "urls": [{"expanded_url": "https://example.com"}],
            },
        }

        users = {
            "author1": {
                "id": "author1",
                "username": "testuser",
                "name": "Test User",
                "verified": True,
            }
        }

        bookmark = parse_bookmark(tweet_data, users)

        assert bookmark.tweet_id == "123456789"
        assert bookmark.author.username == "testuser"
        assert bookmark.author.verified is True
        assert bookmark.metrics.like_count == 100
        assert bookmark.urls_expanded == ["https://example.com"]


class TestBookmarkSync:
    """Test bookmark synchronization."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database."""
        db_path = tmp_path / "test.db"
        return Database(str(db_path))

    @pytest.mark.asyncio
    async def test_sync_bookmarks(self, db):
        """Test syncing bookmarks."""
        mock_client_instance = MagicMock()
        mock_client_instance.get_all_bookmarks = AsyncMock(return_value=(
            [
                Bookmark(
                    tweet_id="123456",
                    author=Author(username="testuser", name="Test User", verified=False),
                    text="Test tweet",
                    tweet_url="https://twitter.com/testuser/status/123456",
                    metrics=TweetMetrics(like_count=100),
                    note_text=None,
                    created_at=None,
                    raw_json=None,
                )
            ],
            "123456",
        ))
        mock_client_instance.close = AsyncMock()

        with patch("jarvis.bookmarks.sync.XAPIClient", return_value=mock_client_instance):
            sync = BookmarkSync(db, "test_client_id", "test_client_secret")
            result = await sync.sync_bookmarks()

            assert result["status"] == "success"
            assert result["new_bookmarks"] == 1

    @pytest.mark.asyncio
    async def test_sync_in_progress(self, db):
        """Test that sync is skipped when already in progress."""
        db.update_sync_status(sync_in_progress=True)

        sync = BookmarkSync(db, "test_client_id", "test_client_secret")
        result = await sync.sync_bookmarks()

        assert result["status"] == "skipped"
        assert result["reason"] == "Sync already in progress"
