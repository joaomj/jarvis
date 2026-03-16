"""Sync correctness verification and repair utilities."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from jarvis.database.core import DatabaseCore
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class SyncHealthReport:
    """Health report for sync status."""

    status: str  # "healthy", "drifted", "error"
    actual_count: int
    reported_count: int
    drift: int
    last_sync_at: str | None
    sync_age_hours: float | None
    issues: list[str]


class SyncHealthChecker(DatabaseCore):
    """Verify and repair sync status correctness."""

    def check_sync_health(self) -> SyncHealthReport:
        """Check if sync status matches actual database state.

        Returns:
            SyncHealthReport with findings
        """
        issues: list[str] = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get actual count
                cursor = conn.execute("SELECT COUNT(*) FROM x_bookmarks")
                actual_count = cursor.fetchone()[0]

                # Get sync status
                cursor = conn.execute(
                    """SELECT total_bookmarks, last_sync_at, last_sync_date,
                              sync_in_progress, first_sync_complete
                       FROM x_sync_status WHERE id = 1"""
                )
                row = cursor.fetchone()

                if not row:
                    return SyncHealthReport(
                        status="error",
                        actual_count=actual_count,
                        reported_count=0,
                        drift=actual_count,
                        last_sync_at=None,
                        sync_age_hours=None,
                        issues=["No sync status row found"],
                    )

                (
                    reported_count,
                    last_sync_at,
                    _last_sync_date,
                    sync_in_progress,
                    first_sync_complete,
                ) = row

                # Calculate drift
                drift = abs(actual_count - reported_count)

                # Calculate sync age
                sync_age_hours = None
                if last_sync_at:
                    try:
                        sync_time = datetime.fromisoformat(last_sync_at)
                        now = datetime.now(UTC)
                        sync_age_hours = (now - sync_time).total_seconds() / 3600
                    except (ValueError, TypeError):
                        issues.append(f"Invalid last_sync_at timestamp: {last_sync_at}")

                # Check for issues
                if drift > 0:
                    issues.append(f"Count drift: actual={actual_count}, reported={reported_count}")

                if sync_in_progress and sync_age_hours is not None and sync_age_hours > 1:
                    issues.append(
                        f"Sync appears stuck (in_progress for {sync_age_hours:.1f} hours)"
                    )

                if not first_sync_complete and actual_count > 0:
                    issues.append("Bookmarks exist but first_sync_complete is False")

                status = "healthy" if not issues else "drifted"

                return SyncHealthReport(
                    status=status,
                    actual_count=actual_count,
                    reported_count=reported_count,
                    drift=drift,
                    last_sync_at=last_sync_at,
                    sync_age_hours=sync_age_hours,
                    issues=issues,
                )

        except Exception as error:
            logger.error("check_sync_health_failed", error=str(error))
            return SyncHealthReport(
                status="error",
                actual_count=0,
                reported_count=0,
                drift=0,
                last_sync_at=None,
                sync_age_hours=None,
                issues=[f"Error checking health: {error}"],
            )

    def repair_sync_status(self) -> dict[str, object]:
        """Repair sync status to match actual database state.

        Fixes:
        - Updates total_bookmarks to actual count
        - Clears stuck sync_in_progress flag
        - Sets first_sync_complete if bookmarks exist

        Returns:
            Dict with repair actions taken
        """
        actions: list[str] = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")

                # Get actual count
                cursor = conn.execute("SELECT COUNT(*) FROM x_bookmarks")
                actual_count = cursor.fetchone()[0]

                # Get current status
                cursor = conn.execute(
                    "SELECT total_bookmarks, sync_in_progress FROM x_sync_status WHERE id = 1"
                )
                row = cursor.fetchone()

                if row:
                    reported_count, sync_in_progress = row

                    # Fix count drift
                    if actual_count != reported_count:
                        conn.execute(
                            "UPDATE x_sync_status SET total_bookmarks = ? WHERE id = 1",
                            (actual_count,),
                        )
                        actions.append(f"Fixed total_bookmarks: {reported_count} -> {actual_count}")

                    # Fix stuck sync
                    if sync_in_progress:
                        conn.execute(
                            """UPDATE x_sync_status
                               SET sync_in_progress = 0, last_sync_at = ?
                               WHERE id = 1""",
                            (datetime.now(UTC).isoformat(),),
                        )
                        actions.append("Cleared stuck sync_in_progress flag")

                    # Fix first_sync_complete
                    if actual_count > 0:
                        conn.execute(
                            "UPDATE x_sync_status SET first_sync_complete = 1 WHERE id = 1"
                        )
                        actions.append("Set first_sync_complete = True")

                logger.info("sync_status_repaired", actions=actions)

                return {
                    "status": "success",
                    "actions": actions,
                    "actual_bookmarks": actual_count,
                }

        except Exception as error:
            logger.error("repair_sync_status_failed", error=str(error))
            return {
                "status": "error",
                "error": str(error),
                "actions": actions,
            }

    def get_sync_summary(self) -> dict[str, object]:
        """Get comprehensive sync summary.

        Returns:
            Dict with sync statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Bookmark counts
                cursor = conn.execute("SELECT COUNT(*) FROM x_bookmarks")
                total_bookmarks = cursor.fetchone()[0]

                cursor = conn.execute(
                    """SELECT COUNT(*) FROM x_bookmarks
                       WHERE content_kind = 'article'"""
                )
                article_count = cursor.fetchone()[0]

                cursor = conn.execute(
                    """SELECT COUNT(*) FROM x_bookmarks
                       WHERE artifact_path IS NOT NULL"""
                )
                with_artifacts = cursor.fetchone()[0]

                # Sync status
                cursor = conn.execute(
                    """SELECT last_sync_date, last_sync_at, last_full_sync_date,
                              total_bookmarks, sync_in_progress, first_sync_complete
                       FROM x_sync_status WHERE id = 1"""
                )
                row = cursor.fetchone()

                status = {
                    "total_bookmarks": total_bookmarks,
                    "article_bookmarks": article_count,
                    "with_artifacts": with_artifacts,
                    "sync_status": dict(
                        zip(
                            [
                                "last_sync_date",
                                "last_sync_at",
                                "last_full_sync_date",
                                "total_bookmarks",
                                "sync_in_progress",
                                "first_sync_complete",
                            ],
                            row if row else [None] * 6,
                            strict=True,
                        )
                    )
                    if row
                    else None,
                }

                return status

        except Exception as error:
            logger.error("get_sync_summary_failed", error=str(error))
            return {"error": str(error)}
