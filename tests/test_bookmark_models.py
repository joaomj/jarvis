"""Tests for bookmark Pydantic models."""

from jarvis.bookmarks.models import Author, Bookmark, TweetMetrics


class TestBookmarkModels:
    """Test bookmark Pydantic models."""

    def test_author_model(self) -> None:
        """Test Author model."""
        author = Author(username="testuser", name="Test User", verified=True)
        assert author.username == "testuser"
        assert author.name == "Test User"
        assert author.verified is True

    def test_tweet_metrics_model(self) -> None:
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

    def test_bookmark_model(self) -> None:
        """Test Bookmark model."""
        bookmark = Bookmark(
            tweet_id="123456789",
            author=Author(username="testuser", name="Test User", verified=False),
            text="Test tweet content",
            tweet_url="https://twitter.com/testuser/status/123456789",
            metrics=TweetMetrics(like_count=100),
            note_text=None,
            created_at=None,
            raw_json=None,
        )
        assert bookmark.tweet_id == "123456789"
        assert bookmark.author.username == "testuser"
        assert bookmark.text == "Test tweet content"
        assert bookmark.metrics.like_count == 100
