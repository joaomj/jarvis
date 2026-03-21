"""Embedding storage operations for semantic search."""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

from jarvis.database.core import DatabaseCore
from jarvis.logging_config import get_logger

if TYPE_CHECKING:
    from jarvis.embedding import EmbeddedChunk

logger = get_logger(__name__)


class EmbeddingOperations(DatabaseCore):
    """Database operations for chunk embeddings."""

    def save_embedding(
        self,
        chunk_id: int,
        embedding: list[float],
        model_name: str,
    ) -> None:
        """Save or update embedding for a chunk.

        Args:
            chunk_id: ID of the kb_chunks row
            embedding: Embedding vector as list of floats
            model_name: Name of the embedding model used
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute(
                    """INSERT INTO kb_chunk_embeddings (chunk_id, embedding, model_name)
                       VALUES (?, ?, ?)
                       ON CONFLICT(chunk_id) DO UPDATE SET
                           embedding=excluded.embedding,
                           model_name=excluded.model_name,
                           created_at=CURRENT_TIMESTAMP""",
                    (chunk_id, json.dumps(embedding), model_name),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.error("save_embedding_failed", chunk_id=chunk_id, error=str(error))
            raise

    def get_embedding(self, chunk_id: int) -> list[float] | None:
        """Get embedding for a specific chunk.

        Args:
            chunk_id: ID of the chunk

        Returns:
            Embedding vector or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                cursor = conn.execute(
                    "SELECT embedding FROM kb_chunk_embeddings WHERE chunk_id = ?",
                    (chunk_id,),
                )
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as error:
            logger.warning("get_embedding_failed", chunk_id=chunk_id, error=str(error))
            return None

    def get_all_embeddings_with_chunks(
        self,
        model_name: str | None = None,
    ) -> list[EmbeddedChunk]:
        """Get all embeddings with their chunk data for similarity search.

        Args:
            model_name: Optional filter by model name

        Returns:
            List of EmbeddedChunk objects
        """
        from jarvis.embedding import EmbeddedChunk  # noqa: PLC0415

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")

                if model_name:
                    cursor = conn.execute(
                        """SELECT e.chunk_id, e.embedding, c.chunk_text, c.document_id
                           FROM kb_chunk_embeddings e
                           JOIN kb_chunks c ON e.chunk_id = c.id
                           WHERE e.model_name = ?""",
                        (model_name,),
                    )
                else:
                    cursor = conn.execute(
                        """SELECT e.chunk_id, e.embedding, c.chunk_text, c.document_id
                           FROM kb_chunk_embeddings e
                           JOIN kb_chunks c ON e.chunk_id = c.id""",
                    )

                results = []
                for row in cursor.fetchall():
                    chunk_id, embedding_json, chunk_text, document_id = row
                    results.append(
                        EmbeddedChunk(
                            chunk_id=chunk_id,
                            chunk_text=chunk_text,
                            embedding=json.loads(embedding_json),
                            document_id=document_id,
                        )
                    )
                return results

        except (sqlite3.OperationalError, sqlite3.DatabaseError) as error:
            logger.error("get_all_embeddings_failed", error=str(error))
            return []

    def get_chunks_without_embeddings(self, model_name: str) -> list[dict]:
        """Get chunks that don't have embeddings for the specified model.

        Args:
            model_name: Embedding model name

        Returns:
            List of chunk dicts with id, chunk_text, document_id
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                cursor = conn.execute(
                    """SELECT c.id, c.chunk_text, c.document_id
                       FROM kb_chunks c
                       LEFT JOIN kb_chunk_embeddings e
                           ON c.id = e.chunk_id AND e.model_name = ?
                       WHERE e.chunk_id IS NULL""",
                    (model_name,),
                )
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as error:
            logger.error("get_chunks_without_embeddings_failed", error=str(error))
            return []

    def delete_embeddings_for_model(self, model_name: str) -> int:
        """Delete all embeddings for a specific model.

        Args:
            model_name: Model name to delete

        Returns:
            Number of rows deleted
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                cursor = conn.execute(
                    "DELETE FROM kb_chunk_embeddings WHERE model_name = ?",
                    (model_name,),
                )
                return cursor.rowcount
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as error:
            logger.error("delete_embeddings_failed", model_name=model_name, error=str(error))
            return 0

    def count_embeddings(self, model_name: str | None = None) -> int:
        """Count total embeddings, optionally filtered by model.

        Args:
            model_name: Optional model filter

        Returns:
            Count of embeddings
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")

                if model_name:
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM kb_chunk_embeddings WHERE model_name = ?",
                        (model_name,),
                    )
                else:
                    cursor = conn.execute("SELECT COUNT(*) FROM kb_chunk_embeddings")

                row = cursor.fetchone()
                return int(row[0]) if row else 0

        except (sqlite3.OperationalError, sqlite3.DatabaseError) as error:
            logger.error("count_embeddings_failed", error=str(error))
            return 0
