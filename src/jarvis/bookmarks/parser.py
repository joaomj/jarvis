"""X API response parsing utilities.

Pure functions for converting X API JSON responses to Pydantic models.
"""

import contextlib
from datetime import datetime
from typing import Any

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
            media_urls = [m.get("media_url", "") for m in entities["media"]]
        if "urls" in entities:
            urls_expanded = [u.get("expanded_url", "") for u in entities["urls"]]

    created_at = None
    if "created_at" in tweet_data:
        with contextlib.suppress(ValueError):
            created_at = datetime.fromisoformat(
                tweet_data["created_at"].replace("Z", "+00:00")
            )

    text = tweet_data.get("text", "")

    if author.username:
        tweet_url = f"https://x.com/{author.username}/status/{tweet_id}"
    else:
        tweet_url = f"https://x.com/i/web/status/{tweet_id}"

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
    )
