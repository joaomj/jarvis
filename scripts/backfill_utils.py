#!/usr/bin/env python3
"""Utility functions for backfill operations."""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

from jarvis.bookmarks.models import Bookmark
from jarvis.bookmarks.parser import parse_bookmark
from jarvis.logging_config import get_logger

if TYPE_CHECKING:
    from jarvis.database import Database

logger = get_logger(__name__)


def parse_existing_bookmark(row: dict) -> Bookmark | None:
    """Parse a database row back into a Bookmark model."""
    try:
        raw_json = json.loads(row.get("raw_json", "{}"))
        if not raw_json:
            return None

        author_id = raw_json.get("author_id", "")
        users = {}
        if author_id:
            users[author_id] = {
                "username": row.get("author_username", ""),
                "name": row.get("author_name", ""),
                "verified": bool(row.get("author_verified", 0)),
            }

        bookmark = parse_bookmark(raw_json, users)
        bookmark.tweet_id = row.get("tweet_id", bookmark.tweet_id)
        bookmark.bookmarked_at = row.get("bookmarked_at")

        return bookmark

    except Exception as error:
        logger.warning(
            "parse_existing_bookmark_failed", tweet_id=row.get("tweet_id"), error=str(error)
        )
        return None


def fetch_all_bookmarks(db: Database) -> list[dict]:
    """Fetch all bookmarks from database."""
    try:
        with sqlite3.connect(str(db.db_path)) as conn:
            cursor = conn.execute(
                """SELECT tweet_id, author_username, author_name, author_verified,
                          text, created_at, tweet_url, raw_json, content_kind, artifact_path
                   FROM x_bookmarks"""
            )
            return [
                dict(zip([desc[0] for desc in cursor.description], row, strict=True))
                for row in cursor.fetchall()
            ]
    except Exception as error:
        logger.error("fetch_bookmarks_failed", error=str(error))
        return []


def generate_validation_report(db_path: str, db: Database) -> dict[str, object]:
    """Generate validation report on bookmark content."""
    logger.info("generating_validation_report")

    try:
        with sqlite3.connect(str(db.db_path)) as conn:
            cursor = conn.execute(
                """SELECT content_kind, COUNT(*) as count
                   FROM x_bookmarks
                   GROUP BY content_kind"""
            )
            content_kinds = {row[0]: row[1] for row in cursor.fetchall()}

            cursor = conn.execute(
                """SELECT COUNT(*) FROM x_bookmarks
                   WHERE content_text IS NULL OR content_text = ''"""
            )
            empty_content = cursor.fetchone()[0]

            cursor = conn.execute(
                """SELECT COUNT(*) FROM x_bookmarks
                   WHERE content_title IS NOT NULL"""
            )
            with_titles = cursor.fetchone()[0]

            cursor = conn.execute(
                """SELECT COUNT(*) FROM x_bookmarks
                   WHERE artifact_path IS NOT NULL"""
            )
            with_artifacts = cursor.fetchone()[0]

        report = {
            "total_bookmarks": sum(content_kinds.values()),
            "by_content_kind": content_kinds,
            "empty_content_count": empty_content,
            "with_titles": with_titles,
            "with_artifacts": with_artifacts,
        }

        logger.info("validation_report", **report)
        return report

    except Exception as error:
        logger.error("validation_report_failed", error=str(error))
        return {"error": str(error)}
