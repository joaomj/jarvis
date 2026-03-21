"""X API response parsing utilities.

Pure functions for converting X API JSON responses to Pydantic models.
"""

import contextlib
from datetime import datetime
from typing import Any, Literal

from jarvis.bookmarks.models import Author, Bookmark, TweetMetrics


def parse_tweet_metrics(metrics: dict[str, Any]) -> TweetMetrics:
    """Parse tweet metrics from API response.

    Args:
        metrics: Public metrics from API.

    Returns:
        TweetMetrics model.
    """
    return TweetMetrics(
        like_count=metrics.get("like_count", 0),
        retweet_count=metrics.get("retweet_count", 0),
        reply_count=metrics.get("reply_count", 0),
        impression_count=metrics.get("impression_count", 0),
        bookmark_count=metrics.get("bookmark_count", 0),
    )


def parse_author(user_data: dict[str, Any]) -> Author:
    """Parse author data from API response.

    Args:
        user_data: User data from API.

    Returns:
        Author model.
    """
    return Author(
        username=user_data.get("username", ""),
        name=user_data.get("name", ""),
        verified=user_data.get("verified", False),
    )


def _extract_canonical_content(
    tweet_data: dict[str, Any],
) -> tuple[
    Literal["article", "note_tweet", "post", "link_only", "media_only", "unknown"],
    str | None,
    str | None,
    str,
    str | None,
]:
    """Extract canonical content following precedence rules.

    Precedence:
    1. article.plain_text
    2. note_tweet.text
    3. text

    Returns:
        Tuple of (content_kind, content_title, content_preview, content_text, source_unwound_url)
    """
    # Check for article content first
    article = tweet_data.get("article")
    if article and isinstance(article, dict):
        plain_text = article.get("plain_text", "").strip()
        if plain_text:
            title = article.get("title", "").strip() or None
            preview = article.get("preview_text", "").strip() or None
            # Get unwound URL from article or entities
            unwound_url = article.get("unwound_url", "").strip()
            if not unwound_url:
                unwound_url = _extract_unwound_url(tweet_data)
            return ("article", title, preview, plain_text, unwound_url or None)

    # Check for note_tweet content
    note_tweet = tweet_data.get("note_tweet")
    if note_tweet and isinstance(note_tweet, dict):
        note_text = note_tweet.get("text", "").strip()
        if note_text:
            unwound_url = _extract_unwound_url(tweet_data)
            return ("note_tweet", None, None, note_text, unwound_url)

    # Fall back to regular text
    text = tweet_data.get("text", "").strip()
    unwound_url = _extract_unwound_url(tweet_data)

    # Determine content kind based on content
    if not text:
        if tweet_data.get("attachments"):
            return ("media_only", None, None, "", unwound_url)
        return ("unknown", None, None, "", unwound_url)

    # Check if it's primarily a link post
    if text and (text.startswith("https://") or text.startswith("http://")):
        return ("link_only", None, None, text, unwound_url)

    return ("post", None, None, text, unwound_url)


def _extract_unwound_url(tweet_data: dict[str, Any]) -> str | None:
    """Extract the best resolved external URL from tweet entities."""
    entities = tweet_data.get("entities", {})
    urls = entities.get("urls", [])

    for url_obj in urls:
        if isinstance(url_obj, dict):
            # Prefer unwound_url, then expanded_url, then url
            unwound = url_obj.get("unwound_url", "").strip()
            if unwound:
                return unwound
            expanded = url_obj.get("expanded_url", "").strip()
            if expanded:
                return expanded

    return None


def parse_bookmark(tweet_data: dict[str, Any], users: dict[str, dict]) -> Bookmark:
    """Parse bookmark data from API response.

    Args:
        tweet_data: Tweet data from API.
        users: Dictionary mapping user IDs to user data.

    Returns:
        Bookmark model.
    """
    tweet_id = tweet_data.get("id", "")
    author_id = tweet_data.get("author_id", "")
    author_data = users.get(author_id, {})
    author = parse_author(author_data)

    metrics = TweetMetrics()
    if "public_metrics" in tweet_data:
        metrics = parse_tweet_metrics(tweet_data["public_metrics"])

    media_urls = []
    urls_expanded = []

    if "entities" in tweet_data:
        entities = tweet_data["entities"]
        if "media" in entities:
            media_urls = [m.get("media_url", "") for m in entities["media"] if isinstance(m, dict)]
        if "urls" in entities:
            urls_expanded = [
                u.get("expanded_url", "") for u in entities["urls"] if isinstance(u, dict)
            ]

    created_at = None
    if "created_at" in tweet_data:
        with contextlib.suppress(ValueError):
            created_at = datetime.fromisoformat(tweet_data["created_at"].replace("Z", "+00:00"))

    # Get original text (for backward compatibility)
    text = tweet_data.get("text", "")

    # Build tweet URL
    if author.username:
        tweet_url = f"https://x.com/{author.username}/status/{tweet_id}"
    else:
        tweet_url = f"https://x.com/i/web/status/{tweet_id}"

    # Extract canonical content following precedence rules
    content_kind, content_title, content_preview, content_text, source_unwound_url = (
        _extract_canonical_content(tweet_data)
    )

    return Bookmark(
        tweet_id=tweet_id,
        author=author,
        text=text,
        note_text=None,
        created_at=created_at,
        tweet_url=tweet_url,
        metrics=metrics,
        media_urls=media_urls,
        urls_expanded=urls_expanded,
        context_annotations=tweet_data.get("context_annotations", []),
        raw_json=tweet_data,
        # Normalized content fields
        content_kind=content_kind,
        content_title=content_title,
        content_preview=content_preview,
        content_text=content_text,
        source_unwound_url=source_unwound_url,
    )
