"""Tests for bookmark parser with article and note_tweet support."""

from __future__ import annotations

from jarvis.bookmarks.parser import _extract_canonical_content, _extract_unwound_url, parse_bookmark


class TestExtractCanonicalContent:
    """Test canonical content extraction with precedence rules."""

    def test_article_plain_text_priority(self):
        """article.plain_text should be highest priority."""
        tweet_data = {
            "text": "Short tweet text",
            "note_tweet": {"text": "Longer note tweet content here"},
            "article": {
                "plain_text": "This is the full article content that should be used",
                "title": "Article Title",
                "preview_text": "Preview of the article",
            },
        }

        kind, title, preview, content, _url = _extract_canonical_content(tweet_data)

        assert kind == "article"
        assert title == "Article Title"
        assert preview == "Preview of the article"
        assert content == "This is the full article content that should be used"

    def test_note_tweet_second_priority(self):
        """note_tweet.text should be used when article not available."""
        tweet_data = {
            "text": "Short tweet text",
            "note_tweet": {"text": "This is the note tweet content"},
        }

        kind, _title, _preview, content, _url = _extract_canonical_content(tweet_data)

        assert kind == "note_tweet"
        assert content == "This is the note tweet content"

    def test_regular_text_fallback(self):
        """Regular text should be fallback."""
        tweet_data = {"text": "Regular tweet content"}

        kind, _title, _preview, content, _url = _extract_canonical_content(tweet_data)

        assert kind == "post"
        assert content == "Regular tweet content"


class TestExtractUnwoundUrl:
    """Test URL extraction from entities."""

    def test_unwound_url_priority(self):
        """unwound_url should be preferred over expanded_url."""
        tweet_data = {
            "entities": {
                "urls": [
                    {
                        "url": "https://t.co/short",
                        "expanded_url": "https://example.com/page",
                        "unwound_url": "https://example.com/full/article",
                    }
                ]
            }
        }

        url = _extract_unwound_url(tweet_data)
        assert url == "https://example.com/full/article"

    def test_no_urls(self):
        """Return None when no URLs present."""
        tweet_data = {"text": "Just text without URLs"}
        url = _extract_unwound_url(tweet_data)
        assert url is None


class TestParseBookmark:
    """Test full bookmark parsing."""

    def test_parse_article_bookmark(self):
        """Parse a bookmark with article content."""
        tweet_data = {
            "id": "123456789",
            "author_id": "987654321",
            "text": "Check out this article!",
            "created_at": "2024-01-15T10:00:00Z",
            "public_metrics": {
                "like_count": 42,
                "retweet_count": 5,
                "reply_count": 3,
            },
            "article": {
                "plain_text": "This is the full article content. It is very informative.",
                "title": "Informative Article",
                "preview_text": "A preview of the informative content",
                "unwound_url": "https://example.com/full-article",
            },
        }

        users = {
            "987654321": {
                "username": "testuser",
                "name": "Test User",
                "verified": True,
            }
        }

        bookmark = parse_bookmark(tweet_data, users)

        assert bookmark.tweet_id == "123456789"
        assert bookmark.author.username == "testuser"
        assert bookmark.author.name == "Test User"
        assert bookmark.author.verified is True
        assert bookmark.content_kind == "article"
        assert bookmark.content_title == "Informative Article"
        assert bookmark.content_text == "This is the full article content. It is very informative."
        assert bookmark.source_unwound_url == "https://example.com/full-article"
        assert bookmark.metrics.like_count == 42

    def test_parse_note_tweet_bookmark(self):
        """Parse a bookmark with note_tweet content."""
        tweet_data = {
            "id": "987654321",
            "author_id": "123456789",
            "text": "Short",
            "note_tweet": {"text": "This is a much longer note tweet with detailed content"},
            "created_at": "2024-01-15T11:00:00Z",
        }

        users = {
            "123456789": {
                "username": "anotheruser",
                "name": "Another User",
                "verified": False,
            }
        }

        bookmark = parse_bookmark(tweet_data, users)

        assert bookmark.tweet_id == "987654321"
        assert bookmark.content_kind == "note_tweet"
        assert bookmark.content_text == "This is a much longer note tweet with detailed content"
        assert bookmark.author.verified is False

    def test_parse_preserves_original_text(self):
        """Original text field should be preserved for backwards compatibility."""
        tweet_data = {
            "id": "999888777",
            "author_id": "111222333",
            "text": "Original short text",
            "article": {
                "plain_text": "Full article content",
                "title": "Title",
            },
        }

        users = {"111222333": {"username": "user", "name": "User"}}
        bookmark = parse_bookmark(tweet_data, users)

        assert bookmark.text == "Original short text"
        assert bookmark.content_text == "Full article content"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_missing_author(self):
        """Handle missing author in users dict."""
        tweet_data = {
            "id": "123",
            "author_id": "999",
            "text": "Test",
        }

        users = {}
        bookmark = parse_bookmark(tweet_data, users)

        assert bookmark.author.username == ""
        assert bookmark.author.name == ""

    def test_invalid_created_at(self):
        """Handle invalid created_at timestamp."""
        tweet_data = {
            "id": "123",
            "author_id": "456",
            "text": "Test",
            "created_at": "invalid-timestamp",
        }

        users = {"456": {"username": "test", "name": "Test"}}
        bookmark = parse_bookmark(tweet_data, users)

        assert bookmark.created_at is None
