"""Bookmark storage and sync status operations."""

from jarvis.database.bookmark_folder_ops import BookmarkFolderOperations
from jarvis.database.bookmark_storage_ops import BookmarkStorageOperations
from jarvis.database.bookmark_sync_status_ops import BookmarkSyncStatusOperations


class BookmarkOperations(
    BookmarkStorageOperations,
    BookmarkSyncStatusOperations,
    BookmarkFolderOperations,
):
    """Combined bookmark operations mixin."""
