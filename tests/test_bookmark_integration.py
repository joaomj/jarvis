"""Tests for X API client and bookmark sync using fake harness."""

from __future__ import annotations

import pytest

from jarvis.bookmarks.models import Bookmark
from jarvis.bookmarks.parser import parse_bookmark
from jarvis.bookmarks.sync import BookmarkSync
from jarvis.database import Database
from tests.harness.fake_x_client import FakeBookmarkData, FakeXAPIClient


@pytest.fixture
def tmp_db_path(tmp_path):
    """Provide temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def db(tmp_db_path):
    """Create test database with OAuth tokens."""
    database = Database(str(tmp_db_path))
    database.save_oauth_tokens(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        expires_at="2099-01-01T00:00:00+00:00",
        scope="bookmark.read tweet.read users.read offline.access",
    )
    return database


@pytest.fixture
def fake_client():
    """Create fake X API client with sample data."""
    client = FakeXAPIClient(user_id="test_user_123")
    client.add_bookmark(
        FakeBookmarkData(
            tweet_id="123456789",
            text="Test tweet content",
            author_id="author1",
            username="testuser",
            name="Test User",
            verified=True,
            like_count=100,
            retweet_count=50,
            urls=["https://example.com"],
        )
    )
    return client


class TestFakeXAPIClientOperations:
    """Tests for fake X API client behavior."""

    @pytest.mark.asyncio
    async def test_get_bookmarks_returns_paginated_results(self, fake_client):
        """Test that bookmarks are returned in X API format."""
        data = await fake_client.get_bookmarks()

        assert "data" in data
        assert len(data["data"]) == 1
        assert data["data"][0]["id"] == "123456789"
        assert data["data"][0]["text"] == "Test tweet content"
        assert data["meta"]["result_count"] == 1

    @pytest.mark.asyncio
    async def test_get_bookmarks_includes_user_data(self, fake_client):
        """Test that user data is included in includes.users."""
        data = await fake_client.get_bookmarks()

        assert "includes" in data
        assert "users" in data["includes"]
        users = data["includes"]["users"]
        assert len(users) == 1
        assert users[0]["id"] == "author1"
        assert users[0]["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_get_all_bookmarks_returns_bookmark_objects(self, fake_client):
        """Test that get_all_bookmarks returns parsed Bookmark objects."""
        bookmarks, last_id = await fake_client.get_all_bookmarks()

        assert len(bookmarks) == 1
        assert isinstance(bookmarks[0], Bookmark)
        assert bookmarks[0].tweet_id == "123456789"
        assert bookmarks[0].author.username == "testuser"
        assert bookmarks[0].author.verified is True
        assert bookmarks[0].metrics.like_count == 100
        assert last_id == "123456789"

    @pytest.mark.asyncio
    async def test_get_bookmarks_respects_since_id(self, fake_client):
        """Test that since_id filters older bookmarks."""
        # Add another bookmark with higher ID
        fake_client.add_bookmark(
            FakeBookmarkData(
                tweet_id="999999999",
                text="Newer tweet",
                author_id="author2",
                username="newuser",
                name="New User",
            )
        )

        data = await fake_client.get_bookmarks(since_id="123456789")

        assert len(data["data"]) == 1
        assert data["data"][0]["id"] == "999999999"

    @pytest.mark.asyncio
    async def test_get_all_bookmarks_handles_pagination(self, fake_client):
        """Test that pagination works correctly."""
        # Add many bookmarks to trigger pagination
        for i in range(150):
            fake_client.add_bookmark(
                FakeBookmarkData(
                    tweet_id=str(1000 + i),
                    text=f"Tweet {i}",
                    author_id=f"author_{i}",
                    username=f"user{i}",
                    name=f"User {i}",
                )
            )

        bookmarks, _last_id = await fake_client.get_all_bookmarks()

        assert len(bookmarks) == 151  # 150 new + 1 original
        # Verify pagination happened
        calls = fake_client.call_log
        get_bookmarks_calls = [c for c in calls if c["method"] == "get_bookmarks"]
        assert len(get_bookmarks_calls) > 1

    @pytest.mark.asyncio
    async def test_client_tracks_calls(self, fake_client):
        """Test that client tracks all API calls."""
        await fake_client.get_bookmarks()
        await fake_client.get_bookmark_folders()

        assert len(fake_client.call_log) == 2
        assert fake_client.call_log[0]["method"] == "get_bookmarks"
        assert fake_client.call_log[1]["method"] == "get_bookmark_folders"

    @pytest.mark.asyncio
    async def test_client_can_be_closed(self, fake_client):
        """Test that client can be closed."""
        assert not fake_client.is_closed
        await fake_client.close()
        assert fake_client.is_closed


class TestBookmarkParsing:
    """Tests for bookmark parsing from API data."""

    def test_parse_bookmark_extracts_all_fields(self):
        """Test parsing bookmark from API response."""
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
        assert bookmark.text == "Test tweet"
        assert bookmark.author.username == "testuser"
        assert bookmark.author.verified is True
        assert bookmark.metrics.like_count == 100
        assert bookmark.metrics.retweet_count == 50
        assert bookmark.urls_expanded == ["https://example.com"]


@pytest.mark.integration
class TestBookmarkSyncIntegration:
    """Integration tests for bookmark synchronization."""

    @pytest.mark.asyncio
    async def test_sync_bookmarks_saves_to_database(self, db):
        """Test that sync saves bookmarks to database."""
        fake_client = FakeXAPIClient()
        fake_client.add_bookmark(
            FakeBookmarkData(
                tweet_id="sync_test_1",
                text="Sync test tweet",
                author_id="sync_author",
                username="syncuser",
                name="Sync User",
            )
        )

        # Create sync and inject fake client
        sync = BookmarkSync(db, "test_client_id", "test_client_secret")
        sync.client = fake_client  # type: ignore[assignment]  # Monkey-patch with fake client

        result = await sync.sync_bookmarks()

        assert result["status"] == "success"
        assert result["new_bookmarks"] == 1

        # Verify saved to database
        total = db.get_total_bookmarks_count()
        assert total == 1
        # Verify we can retrieve the bookmark by ID
        bookmark = db.get_bookmark_by_id("sync_test_1")
        assert bookmark is not None
        assert bookmark["tweet_id"] == "sync_test_1"

    @pytest.mark.asyncio
    async def test_sync_respects_existing_bookmarks(self, db):
        """Test that sync doesn't duplicate existing bookmarks."""
        fake_client = FakeXAPIClient()
        fake_client.add_bookmark(
            FakeBookmarkData(
                tweet_id="123456",
                text="Duplicate test",
                author_id="dup_author",
                username="dupuser",
                name="Dup User",
            )
        )

        sync = BookmarkSync(db, "test_client_id", "test_client_secret")
        sync.client = fake_client  # type: ignore[assignment]  # Monkey-patch with fake client

        # First sync
        result1 = await sync.sync_bookmarks()
        assert result1["new_bookmarks"] == 1

        # Second sync with same data
        result2 = await sync.sync_bookmarks()
        assert result2["new_bookmarks"] == 0  # No new bookmarks

    @pytest.mark.asyncio
    async def test_sync_in_progress_prevents_concurrent_sync(self, db):
        """Test that sync is skipped when already in progress."""
        db.update_sync_status(sync_in_progress=True)

        sync = BookmarkSync(db, "test_client_id", "test_client_secret")
        # No need to inject client, sync is skipped before API calls

        result = await sync.sync_bookmarks()

        assert result["status"] == "skipped"
        assert result["reason"] == "Sync already in progress"

    @pytest.mark.asyncio
    async def test_sync_handles_multiple_pages(self, db):
        """Test sync handles paginated bookmark results."""
        fake_client = FakeXAPIClient()

        # Add enough bookmarks to trigger pagination
        for i in range(150):
            fake_client.add_bookmark(
                FakeBookmarkData(
                    tweet_id=str(10000 + i),
                    text=f"Multi-page tweet {i}",
                    author_id=f"author_{i}",
                    username=f"user{i}",
                    name=f"User {i}",
                )
            )

        sync = BookmarkSync(db, "test_client_id", "test_client_secret")
        sync.client = fake_client  # type: ignore[assignment]  # Monkey-patch with fake client

        result = await sync.sync_bookmarks()

        assert result["status"] == "success"
        assert result["new_bookmarks"] == 150
