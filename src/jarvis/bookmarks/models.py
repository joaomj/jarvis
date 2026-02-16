"""Pydantic models for X bookmarks.

Defines data models for tweets and sync status.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Author(BaseModel):
    """Tweet author information."""

    username: str = Field(..., description="Twitter username without @")
    name: str = Field(..., description="Display name")
    verified: bool = Field(default=False, description="Verified status")


class TweetMetrics(BaseModel):
    """Tweet engagement metrics."""

    like_count: int = Field(default=0, ge=0)
    retweet_count: int = Field(default=0, ge=0)
    reply_count: int = Field(default=0, ge=0)
    impression_count: int = Field(default=0, ge=0)
    bookmark_count: int = Field(default=0, ge=0)


class Bookmark(BaseModel):
    """X/Twitter bookmark data."""

    tweet_id: str = Field(..., description="Tweet ID")
    author: Author
    text: str = Field(..., description="Full tweet text")
    note_text: str | None = Field(None, description="User's private note on bookmark")
    created_at: datetime | None = Field(None, description="Tweet creation timestamp")
    bookmarked_at: datetime = Field(default_factory=datetime.utcnow, description="Bookmark timestamp")
    tweet_url: str = Field(..., description="Tweet URL")
    metrics: TweetMetrics = Field(default_factory=TweetMetrics)
    media_urls: list[str] = Field(default_factory=list, description="Media URLs")
    urls_expanded: list[str] = Field(default_factory=list, description="Expanded URLs from tweet")
    context_annotations: list[dict[str, Any]] = Field(default_factory=list, description="Context annotations from X API")
    raw_json: dict[str, Any] | None = Field(None, description="Raw API response")


class SyncStatus(BaseModel):
    """Sync status tracking."""

    last_sync_date: str | None = None
    last_sync_at: datetime | None = None
    last_tweet_id: str | None = None
    total_bookmarks: int = Field(default=0, ge=0)
    sync_in_progress: bool = Field(default=False)
    first_sync_complete: bool = Field(default=False)
