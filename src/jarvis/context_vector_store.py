"""Low-level sqlite-vec operations for unified context retrieval."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import cast

from jarvis.logging_config import get_logger

logger = get_logger(__name__)

try:
    import sqlite_vec
    from sqlite_vec import serialize_float32
except Exception:
    sqlite_vec = None
    serialize_float32 = None


def ensure_vector_schema(db_path: str) -> bool:
    """Load sqlite-vec extension and create required vector tables."""
    try:
        with sqlite3.connect(db_path) as conn:
            _load_sqlite_vec(conn)
            conn.execute(
                """CREATE VIRTUAL TABLE IF NOT EXISTS context_vec USING vec0(
                       embedding float[1024]
                   )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS context_embeddings (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       entry_type TEXT NOT NULL,
                       entry_id INTEGER NOT NULL,
                       content_hash TEXT NOT NULL,
                       updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                       UNIQUE(entry_type, entry_id)
                   )"""
            )
        return True
    except Exception as error:
        logger.warning("context_vector_unavailable", error=str(error))
        return False


def upsert_embedding(
    db_path: str,
    entry_type: str,
    entry_id: int,
    embedding: list[float],
    content_hash: str,
) -> None:
    """Upsert metadata row and vec row in one transaction."""
    try:
        with sqlite3.connect(db_path) as conn:
            _load_sqlite_vec(conn)
            conn.execute(
                """INSERT INTO context_embeddings (entry_type, entry_id, content_hash, updated_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(entry_type, entry_id) DO UPDATE SET
                       content_hash=excluded.content_hash,
                       updated_at=CURRENT_TIMESTAMP""",
                (entry_type, entry_id, content_hash),
            )
            row = conn.execute(
                "SELECT id FROM context_embeddings WHERE entry_type = ? AND entry_id = ?",
                (entry_type, entry_id),
            ).fetchone()
            if row is None:
                raise sqlite3.IntegrityError("context embedding row missing after upsert")
            meta_id = _to_int(row[0])

            conn.execute(
                "INSERT OR REPLACE INTO context_vec(rowid, embedding) VALUES (?, ?)",
                (meta_id, _serialize_embedding(embedding)),
            )
    except Exception as error:
        logger.warning(
            "context_embedding_upsert_failed",
            entry_type=entry_type,
            entry_id=entry_id,
            error=str(error),
        )


def semantic_candidates(
    db_path: str, query_embedding: list[float], limit: int
) -> list[tuple[str, int]]:
    """Get ranked semantic candidates as (entry_type, entry_id)."""
    try:
        with sqlite3.connect(db_path) as conn:
            _load_sqlite_vec(conn)
            rows = conn.execute(
                """SELECT ce.entry_type, ce.entry_id, cv.distance
                   FROM context_vec cv
                   JOIN context_embeddings ce ON ce.id = cv.rowid
                   LEFT JOIN kb_chunks kc ON kc.id = ce.entry_id AND ce.entry_type = 'kb_chunk'
                   WHERE cv.embedding MATCH ? AND k = ?
                     AND (ce.entry_type != 'kb_chunk' OR kc.id IS NOT NULL)
                   ORDER BY cv.distance ASC""",
                (_serialize_embedding(query_embedding), limit),
            ).fetchall()
        return [(str(row[0]), _to_int(row[1])) for row in rows]
    except Exception as error:
        logger.warning("semantic_search_failed", error=str(error))
        return []


def _load_sqlite_vec(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec extension for the active SQLite connection."""
    if sqlite_vec is None:
        raise RuntimeError("sqlite-vec is not installed")
    if serialize_float32 is None:
        raise RuntimeError("sqlite-vec serializer unavailable")

    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


def _serialize_embedding(vector: list[float]) -> bytes:
    """Serialize float vector for sqlite-vec MATCH/INSERT operations."""
    if serialize_float32 is None:
        raise RuntimeError("sqlite-vec serializer unavailable")
    serializer = cast(Callable[[list[float]], bytes], serialize_float32)
    return serializer(vector)


def _to_int(value: object) -> int:
    """Convert dynamic DB values to int safely."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value:
        try:
            return int(value)
        except ValueError:
            return 0
    return 0
