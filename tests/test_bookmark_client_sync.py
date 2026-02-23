"""Tests for X API client and bookmark sync."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.bookmarks.client import XAPIClient
from jarvis.bookmarks.models import Author, Bookmark, TweetMetrics
from jarvis.bookmarks.parser import parse_bookmark
from jarvis.bookmarks.sync import BookmarkSync
from jarvis.database import Database


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
                    "public_metrics": {"like_count": 100, "retweet_count": 50},
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
            "entities": {"urls": [{"expanded_url": "https://example.com"}]},
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
        mock_client_instance.get_all_bookmarks = AsyncMock(
            return_value=(
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
            )
        )
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
