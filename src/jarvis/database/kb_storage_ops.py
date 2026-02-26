"""Knowledge-base storage and search operations."""

from __future__ import annotations

import sqlite3
from typing import TypedDict

from jarvis.database.core import DatabaseCore
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class KBChunkRow(TypedDict):
    """Chunk payload used for document reindexing."""

    chunk_index: int
    heading: str | None
    line_start: int
    line_end: int
    chunk_text: str


class KBStorageOperations(DatabaseCore):
    """Storage operations for KB documents/chunks/FTS."""

    def upsert_document(  # noqa: PLR0913
        self,
        markdown_path: str,
        url_original: str | None,
        url_canonical: str | None,
        title: str | None,
        domain: str | None,
        captured_at: str | None,
        content_hash: str,
        status: str = "indexed",
        last_error: str | None = None,
    ) -> int:
        """Insert or update a KB document and return document id."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO kb_documents
                       (markdown_path, url_original, url_canonical, title, domain, captured_at,
                        content_hash, status, indexed_at, last_error)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                       ON CONFLICT(markdown_path) DO UPDATE SET
                           url_original=excluded.url_original,
                           url_canonical=excluded.url_canonical,
                           title=excluded.title,
                           domain=excluded.domain,
                           captured_at=excluded.captured_at,
                           content_hash=excluded.content_hash,
                           status=excluded.status,
                           indexed_at=CURRENT_TIMESTAMP,
                           last_error=excluded.last_error""",
                    (
                        markdown_path,
                        url_original,
                        url_canonical,
                        title,
                        domain,
                        captured_at,
                        content_hash,
                        status,
                        last_error,
                    ),
                )
                row = conn.execute(
                    "SELECT id FROM kb_documents WHERE markdown_path = ?",
                    (markdown_path,),
                ).fetchone()
                if row is None:
                    raise sqlite3.IntegrityError("KB document upsert returned no row")
                return int(row[0])
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning(
                "upsert_kb_document_failed",
                markdown_path=markdown_path,
                error=str(error),
            )
            raise

    def replace_document_chunks(self, document_id: int, chunks: list[KBChunkRow]) -> None:
        """Replace all chunks for a document in one transaction."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM kb_chunks_fts WHERE document_id = ?", (document_id,))
                conn.execute("DELETE FROM kb_chunks WHERE document_id = ?", (document_id,))
                conn.executemany(
                    """INSERT INTO kb_chunks
                       (document_id, chunk_index, heading, line_start, line_end, chunk_text)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            document_id,
                            chunk["chunk_index"],
                            chunk["heading"],
                            chunk["line_start"],
                            chunk["line_end"],
                            chunk["chunk_text"],
                        )
                        for chunk in chunks
                    ],
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning(
                "replace_document_chunks_failed",
                document_id=document_id,
                chunk_count=len(chunks),
                error=str(error),
            )
            raise

    def upsert_fts_for_document(self, document_id: int) -> None:
        """Rebuild FTS rows for one document."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM kb_chunks_fts WHERE document_id = ?", (document_id,))
                conn.execute(
                    """INSERT INTO kb_chunks_fts (chunk_text, heading, chunk_id, document_id)
                       SELECT chunk_text, COALESCE(heading, ''), id, document_id
                       FROM kb_chunks
                       WHERE document_id = ?""",
                    (document_id,),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning(
                "upsert_fts_for_document_failed",
                document_id=document_id,
                error=str(error),
            )
            raise

    def get_document_by_path(self, path: str) -> dict[str, object] | None:
        """Return document metadata by markdown path."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM kb_documents WHERE markdown_path = ?",
                    (path,),
                ).fetchone()
                return dict(row) if row else None
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning("get_document_by_path_failed", path=path, error=str(error))
            return None

    def search_chunks_fts(self, query: str, limit: int) -> list[dict[str, object]]:
        """Run lexical FTS search and return joined chunk/document rows."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """SELECT
                           kb_chunks.id AS chunk_id,
                           kb_chunks.document_id,
                           kb_chunks.chunk_index,
                           kb_chunks.heading,
                           kb_chunks.line_start,
                           kb_chunks.line_end,
                           kb_chunks.chunk_text,
                           kb_documents.title,
                           kb_documents.url_original,
                           kb_documents.markdown_path,
                           bm25(kb_chunks_fts) AS score
                       FROM kb_chunks_fts
                       JOIN kb_chunks ON kb_chunks.id = kb_chunks_fts.chunk_id
                       JOIN kb_documents ON kb_documents.id = kb_chunks.document_id
                       WHERE kb_chunks_fts MATCH ?
                       ORDER BY score
                       LIMIT ?""",
                    (query, limit),
                ).fetchall()
                return [dict(row) for row in rows]
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning("search_chunks_fts_failed", query=query, limit=limit, error=str(error))
            return []

    def log_ingest_error(self, path: str, error: str) -> None:
        """Write one ingest error record."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO kb_ingest_log (markdown_path, error) VALUES (?, ?)",
                    (path, error),
                )
        except (
            sqlite3.OperationalError,
            sqlite3.IntegrityError,
            sqlite3.DatabaseError,
        ) as db_error:
            logger.warning(
                "log_ingest_error_failed",
                path=path,
                ingest_error=error[:200],
                db_error=str(db_error),
            )

    def get_recent_kb_documents(self, limit: int) -> list[dict[str, object]]:
        """Get most recently indexed KB documents."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """SELECT * FROM kb_documents
                       ORDER BY indexed_at DESC
                       LIMIT ?""",
                    (limit,),
                ).fetchall()
                return [dict(row) for row in rows]
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning("get_recent_kb_documents_failed", limit=limit, error=str(error))
            return []
