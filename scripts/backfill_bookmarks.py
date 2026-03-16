#!/usr/bin/env python3
"""Backfill and reindex existing bookmark data.

Usage:
    python scripts/backfill_bookmarks.py [--dry-run] [--batch-size 100]

This script:
1. Migrates schema (adds new columns if missing)
2. Reparses existing raw_json rows to extract normalized content
3. Creates markdown artifacts for bookmarks
4. Rebuilds KB indexes
5. Generates embeddings for semantic search
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from jarvis.bookmark_artifact_store import BookmarkArtifactStore
from jarvis.bookmarks.models import Bookmark
from jarvis.bookmarks.parser import parse_bookmark
from jarvis.database import Database
from jarvis.embedding_indexer import EmbeddingIndexer
from jarvis.kb_indexer import KBIndexer
from jarvis.logging_config import get_logger
from jarvis.sync_health import SyncHealthChecker

logger = get_logger(__name__)


def parse_existing_bookmark(row: dict) -> Bookmark | None:
    """Parse a database row back into a Bookmark model."""
    try:
        # Parse raw_json
        raw_json = json.loads(row.get("raw_json", "{}"))
        if not raw_json:
            return None

        # Reconstruct users dict from author fields
        author_id = raw_json.get("author_id", "")
        users = {}
        if author_id:
            users[author_id] = {
                "username": row.get("author_username", ""),
                "name": row.get("author_name", ""),
                "verified": bool(row.get("author_verified", 0)),
            }

        # Parse using the parser
        bookmark = parse_bookmark(raw_json, users)

        # Override with DB fields if they exist
        bookmark.tweet_id = row.get("tweet_id", bookmark.tweet_id)
        bookmark.bookmarked_at = row.get("bookmarked_at")

        return bookmark

    except Exception as error:
        logger.warning(
            "parse_existing_bookmark_failed", tweet_id=row.get("tweet_id"), error=str(error)
        )
        return None


async def backfill_bookmarks(
    db_path: str,
    vault_root: str,
    batch_size: int = 100,
    dry_run: bool = False,
) -> dict[str, object]:
    """Backfill existing bookmarks with normalized content and artifacts.

    Args:
        db_path: Path to SQLite database
        vault_root: Root directory for vault artifacts
        batch_size: Number of bookmarks to process per batch
        dry_run: If True, don't write changes

    Returns:
        Dict with backfill statistics
    """
    stats = {
        "total_bookmarks": 0,
        "reparsed": 0,
        "artifacts_created": 0,
        "artifacts_skipped": 0,
        "errors": 0,
    }

    logger.info("starting_backfill", dry_run=dry_run, db_path=db_path)

    # Initialize components
    db = Database(db_path)
    artifact_store = BookmarkArtifactStore(db, vault_root)

    # Get all bookmarks
    try:
        with db.db_path.connect() as conn:  # type: ignore
            cursor = conn.execute(
                """SELECT tweet_id, author_username, author_name, author_verified,
                          text, created_at, tweet_url, raw_json, content_kind, artifact_path
                   FROM x_bookmarks"""
            )
            rows = [
                dict(zip([desc[0] for desc in cursor.description], row, strict=True))
                for row in cursor.fetchall()
            ]
    except Exception as error:
        logger.error("fetch_bookmarks_failed", error=str(error))
        return {**stats, "error": str(error)}

    stats["total_bookmarks"] = len(rows)
    logger.info("found_bookmarks", count=len(rows))

    # Process in batches
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        logger.info("processing_batch", batch_num=i // batch_size + 1, batch_size=len(batch))

        for row in batch:
            try:
                # Skip if already has normalized content and artifact
                if row.get("content_kind") and row.get("artifact_path"):
                    stats["artifacts_skipped"] += 1
                    continue

                # Parse bookmark from raw_json
                bookmark = parse_existing_bookmark(row)
                if not bookmark:
                    stats["errors"] += 1
                    continue

                stats["reparsed"] += 1

                if dry_run:
                    logger.debug(
                        "would_update_bookmark",
                        tweet_id=bookmark.tweet_id,
                        content_kind=bookmark.content_kind,
                    )
                    continue

                # Update database with normalized fields
                db.save_bookmark(
                    tweet_id=bookmark.tweet_id,
                    author_username=bookmark.author.username,
                    author_name=bookmark.author.name,
                    author_verified=bookmark.author.verified,
                    text=bookmark.text,
                    note_text=None,
                    created_at=bookmark.created_at.isoformat() if bookmark.created_at else None,
                    tweet_url=bookmark.tweet_url,
                    like_count=bookmark.metrics.like_count,
                    retweet_count=bookmark.metrics.retweet_count,
                    reply_count=bookmark.metrics.reply_count,
                    impression_count=bookmark.metrics.impression_count,
                    bookmark_count=bookmark.metrics.bookmark_count,
                    media_urls=json.dumps(bookmark.media_urls),
                    urls_expanded=json.dumps(bookmark.urls_expanded),
                    context_annotations=json.dumps(bookmark.context_annotations),
                    raw_json=json.dumps(bookmark.raw_json) if bookmark.raw_json else "{}",
                    content_kind=bookmark.content_kind,
                    content_title=bookmark.content_title,
                    content_preview=bookmark.content_preview,
                    content_text=bookmark.content_text,
                    source_unwound_url=bookmark.source_unwound_url,
                )

                # Create artifact
                artifact_path = artifact_store.create_or_update_artifact(bookmark)
                if artifact_path:
                    stats["artifacts_created"] += 1

            except Exception as error:
                logger.error(
                    "backfill_bookmark_failed", tweet_id=row.get("tweet_id"), error=str(error)
                )
                stats["errors"] += 1

    logger.info("backfill_complete", **stats)
    return stats


def rebuild_indexes(
    db_path: str,
    vault_root: str,
    kb_content_dir: str,
    dry_run: bool = False,
) -> dict[str, object]:
    """Rebuild KB indexes and generate embeddings.

    Args:
        db_path: Path to SQLite database
        vault_root: Root directory for vault artifacts
        kb_content_dir: Directory for KB content
        dry_run: If True, don't write changes

    Returns:
        Dict with indexing statistics
    """
    stats = {
        "kb_files_scanned": 0,
        "kb_files_indexed": 0,
        "chunks_embedded": 0,
        "embedding_errors": 0,
    }

    logger.info("starting_index_rebuild", dry_run=dry_run)

    if dry_run:
        logger.info("dry_run_mode_skipping_index_rebuild")
        return stats

    try:
        db = Database(db_path)

        # Rebuild KB index
        logger.info("rebuilding_kb_index")
        kb_indexer = KBIndexer(
            db=db,
            content_dir=kb_content_dir,
            chunk_size_chars=1800,
            vault_root=vault_root,
        )
        result = kb_indexer.index_all()
        stats["kb_files_scanned"] = result.scanned_files
        stats["kb_files_indexed"] = result.indexed_files

        logger.info(
            "kb_index_complete",
            scanned=result.scanned_files,
            indexed=result.indexed_files,
            skipped=result.skipped_files,
        )

        # Generate embeddings
        logger.info("generating_embeddings")
        embedding_indexer = EmbeddingIndexer(db)
        emb_result = embedding_indexer.index_missing_embeddings()
        stats["chunks_embedded"] = emb_result.embeddings_generated
        stats["embedding_errors"] = emb_result.errors

        logger.info(
            "embeddings_complete",
            generated=emb_result.embeddings_generated,
            errors=emb_result.errors,
        )

    except Exception as error:
        logger.error("rebuild_indexes_failed", error=str(error))
        stats["error"] = str(error)

    return stats


def generate_validation_report(db_path: str) -> dict[str, object]:
    """Generate validation report on bookmark content.

    Args:
        db_path: Path to SQLite database

    Returns:
        Dict with validation statistics
    """
    logger.info("generating_validation_report")

    try:
        db = Database(db_path)

        # Get counts by content kind
        with db.db_path.connect() as conn:  # type: ignore
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


async def main():
    parser = argparse.ArgumentParser(description="Backfill and reindex bookmarks")
    parser.add_argument("--db-path", default=".jarvis/jarvis.db", help="Path to SQLite database")
    parser.add_argument("--vault-root", default="vault", help="Vault root directory")
    parser.add_argument(
        "--kb-content-dir", default=".jarvis/url-saves", help="KB content directory"
    )
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for processing")
    parser.add_argument("--dry-run", action="store_true", help="Don't write changes")
    parser.add_argument("--skip-backfill", action="store_true", help="Skip bookmark backfill")
    parser.add_argument("--skip-index", action="store_true", help="Skip index rebuild")
    parser.add_argument("--skip-embeddings", action="store_true", help="Skip embedding generation")

    args = parser.parse_args()

    # Expand paths
    db_path = str(Path(args.db_path).expanduser())
    vault_root = str(Path(args.vault_root).expanduser())
    kb_content_dir = str(Path(args.kb_content_dir).expanduser())

    print("Backfill Configuration:")
    print(f"  Database: {db_path}")
    print(f"  Vault Root: {vault_root}")
    print(f"  KB Content: {kb_content_dir}")
    print(f"  Dry Run: {args.dry_run}")
    print()

    # Check sync health first
    print("Checking sync health...")
    health_checker = SyncHealthChecker()
    health_checker.db_path = db_path
    health = health_checker.check_sync_health()
    print(f"  Status: {health.status}")
    print(f"  Actual Bookmarks: {health.actual_count}")
    print(f"  Reported Bookmarks: {health.reported_count}")
    print(f"  Drift: {health.drift}")
    if health.issues:
        print(f"  Issues: {', '.join(health.issues)}")
    print()

    results = {}

    # Backfill bookmarks
    if not args.skip_backfill:
        print("Backfilling bookmarks...")
        results["backfill"] = await backfill_bookmarks(
            db_path, vault_root, args.batch_size, args.dry_run
        )
        print(f"  Reparsed: {results['backfill'].get('reparsed', 0)}")
        print(f"  Artifacts Created: {results['backfill'].get('artifacts_created', 0)}")
        print(f"  Errors: {results['backfill'].get('errors', 0)}")
        print()

    # Rebuild indexes
    if not args.skip_index:
        print("Rebuilding indexes...")
        results["indexing"] = rebuild_indexes(db_path, vault_root, kb_content_dir, args.dry_run)
        print(f"  KB Files Indexed: {results['indexing'].get('kb_files_indexed', 0)}")
        if not args.skip_embeddings:
            print(f"  Chunks Embedded: {results['indexing'].get('chunks_embedded', 0)}")
        print()

    # Generate validation report
    print("Generating validation report...")
    results["validation"] = generate_validation_report(db_path)
    print(f"  Total Bookmarks: {results['validation'].get('total_bookmarks', 0)}")
    print(f"  By Content Kind: {results['validation'].get('by_content_kind', {})}")
    print(f"  With Artifacts: {results['validation'].get('with_artifacts', 0)}")
    print()

    # Repair sync status
    if not args.dry_run and health.status != "healthy":
        print("Repairing sync status...")
        repair = health_checker.repair_sync_status()
        print(f"  Actions: {repair.get('actions', [])}")
        print()

    print("Backfill complete!")
    return results


if __name__ == "__main__":
    results = asyncio.run(main())
    sys.exit(0)
