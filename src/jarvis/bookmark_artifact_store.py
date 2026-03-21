"""Bookmark artifact generation for vault storage.

Creates human-inspectable markdown artifacts for bookmarks under vault/sources/x-bookmarks/.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from jarvis.bookmarks.models import Bookmark
from jarvis.database import Database
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class BookmarkArtifactStore:
    """Handles writing bookmark artifacts to vault and updating DB references."""

    def __init__(self, db: Database, vault_root: str) -> None:
        self._db = db
        self._vault_root = Path(vault_root).expanduser()
        self._bookmark_dir = self._vault_root / "sources" / "x-bookmarks"
        self._bookmark_dir.mkdir(parents=True, exist_ok=True)

    @property
    def bookmark_dir(self) -> Path:
        """Return bookmark artifact directory path."""
        return self._bookmark_dir

    def create_or_update_artifact(self, bookmark: Bookmark) -> Path | None:
        """Create or update a bookmark markdown artifact.

        Args:
            bookmark: Bookmark model with normalized content.

        Returns:
            Path to the artifact file, or None if creation failed.
        """
        try:
            # Generate content hash for change detection
            content_to_hash = (
                f"{bookmark.content_text}:{bookmark.content_title}:{bookmark.content_preview}"
            )
            content_hash = hashlib.sha256(content_to_hash.encode("utf-8")).hexdigest()[:16]

            # Check if we need to update
            existing = self._db.get_bookmark_by_id(bookmark.tweet_id)
            if existing and existing.get("content_hash") == content_hash:
                # Content unchanged, skip
                artifact_path = existing.get("artifact_path")
                if artifact_path:
                    return Path(artifact_path)

            # Create artifact
            artifact_path = self._bookmark_dir / f"{bookmark.tweet_id}.md"
            markdown_content = self._render_markdown(bookmark)
            artifact_path.write_text(markdown_content, encoding="utf-8")

            # Update DB with artifact path and content hash
            self._db.update_bookmark_artifact(
                tweet_id=bookmark.tweet_id,
                artifact_path=str(artifact_path),
                content_hash=content_hash,
            )

            logger.info(
                "bookmark_artifact_created",
                tweet_id=bookmark.tweet_id,
                path=str(artifact_path),
                content_kind=bookmark.content_kind,
            )

            return artifact_path

        except Exception as error:
            logger.error(
                "bookmark_artifact_failed",
                tweet_id=bookmark.tweet_id,
                error=str(error),
            )
            return None

    def _render_markdown(self, bookmark: Bookmark) -> str:
        """Render bookmark as markdown with frontmatter."""
        frontmatter_lines = [
            "---",
            "source_type: bookmark",
            f"tweet_id: {bookmark.tweet_id}",
            f"content_kind: {bookmark.content_kind}",
            f"author_username: {bookmark.author.username}",
            f"author_name: {bookmark.author.name}",
            f"tweet_url: {bookmark.tweet_url}",
        ]

        if bookmark.source_unwound_url:
            frontmatter_lines.append(f"source_unwound_url: {bookmark.source_unwound_url}")

        if bookmark.created_at:
            frontmatter_lines.append(f"created_at: {bookmark.created_at.isoformat()}")

        frontmatter_lines.append(f"bookmarked_at: {datetime.now(UTC).isoformat()}")

        # Add engagement metrics
        frontmatter_lines.extend(
            [
                f"like_count: {bookmark.metrics.like_count}",
                f"retweet_count: {bookmark.metrics.retweet_count}",
                f"reply_count: {bookmark.metrics.reply_count}",
                f"impression_count: {bookmark.metrics.impression_count}",
                f"bookmark_count: {bookmark.metrics.bookmark_count}",
            ]
        )

        frontmatter_lines.append("---")

        # Content section
        content_lines = [""]

        if bookmark.content_title:
            content_lines.append(f"# {bookmark.content_title}")
            content_lines.append("")

        if bookmark.content_preview:
            content_lines.append(f"> {bookmark.content_preview}")
            content_lines.append("")

        # Main content
        if bookmark.content_text:
            content_lines.append(bookmark.content_text)
            content_lines.append("")
        elif bookmark.text:
            # Fallback to original text
            content_lines.append(bookmark.text)
            content_lines.append("")

        # Media and URLs
        if bookmark.urls_expanded:
            content_lines.append("## Links")
            for url in bookmark.urls_expanded:
                content_lines.append(f"- {url}")
            content_lines.append("")

        if bookmark.media_urls:
            content_lines.append("## Media")
            for url in bookmark.media_urls:
                content_lines.append(f"- {url}")
            content_lines.append("")

        return "\n".join(frontmatter_lines + content_lines)
