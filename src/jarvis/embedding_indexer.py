"""Embedding indexer for semantic search.

Generates and stores embeddings for KB chunks after indexing.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.database import Database
from jarvis.database.embedding_ops import EmbeddingOperations
from jarvis.embedding import EmbeddingGenerator
from jarvis.logging_config import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

DEFAULT_BATCH_SIZE = 32
DEFAULT_MODEL = "all-MiniLM-L6-v2"


@dataclass(frozen=True)
class EmbeddingIndexResult:
    """Result of embedding indexing run."""

    chunks_indexed: int
    embeddings_generated: int
    errors: int


class EmbeddingIndexer:
    """Generates embeddings for chunks and stores them in database."""

    def __init__(
        self,
        db: Database,
        model_name: str = DEFAULT_MODEL,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        """Initialize embedding indexer.

        Args:
            db: Database instance
            model_name: sentence-transformers model name
            batch_size: Batch size for embedding generation
        """
        self.db = db
        self.embedding_ops = EmbeddingOperations()
        self.embedding_ops.db_path = db.db_path
        self.embedding_generator = EmbeddingGenerator(model_name)
        self.batch_size = batch_size
        self.model_name = model_name

    def index_missing_embeddings(self) -> EmbeddingIndexResult:
        """Generate embeddings for chunks that don't have them.

        Returns:
            EmbeddingIndexResult with counts
        """
        chunks = self.embedding_ops.get_chunks_without_embeddings(self.model_name)

        if not chunks:
            logger.info("no_chunks_need_embeddings")
            return EmbeddingIndexResult(chunks_indexed=0, embeddings_generated=0, errors=0)

        logger.info("indexing_embeddings", chunks_to_process=len(chunks))

        generated = 0
        errors = 0

        # Process in batches
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]
            batch_texts = [chunk["chunk_text"] for chunk in batch]

            try:
                embeddings = self.embedding_generator.embed_texts(batch_texts)

                for chunk, embedding in zip(batch, embeddings, strict=True):
                    try:
                        self.embedding_ops.save_embedding(
                            chunk_id=chunk["id"],
                            embedding=embedding,
                            model_name=self.model_name,
                        )
                        generated += 1
                    except Exception as error:
                        logger.error(
                            "save_embedding_failed",
                            chunk_id=chunk["id"],
                            error=str(error),
                        )
                        errors += 1

            except Exception as error:
                logger.error("batch_embedding_failed", batch_index=i, error=str(error))
                errors += len(batch)

        logger.info(
            "embedding_indexing_complete",
            total_chunks=len(chunks),
            generated=generated,
            errors=errors,
        )

        return EmbeddingIndexResult(
            chunks_indexed=len(chunks),
            embeddings_generated=generated,
            errors=errors,
        )

    def index_all_embeddings(self) -> EmbeddingIndexResult:
        """Regenerate all embeddings (useful for model changes).

        Returns:
            EmbeddingIndexResult with counts
        """
        # Delete existing embeddings for this model
        deleted = self.embedding_ops.delete_embeddings_for_model(self.model_name)
        logger.info("deleted_existing_embeddings", model=self.model_name, count=deleted)

        # Index all chunks
        return self.index_missing_embeddings()

    def get_embedding_stats(self) -> dict[str, int]:
        """Get embedding statistics.

        Returns:
            Dict with total_chunks, embedded_chunks, missing_chunks
        """
        from jarvis.database.kb_storage_ops import KBStorageOperations  # noqa: PLC0415

        kb_ops = KBStorageOperations()
        kb_ops.db_path = self.db.db_path

        # Get total chunks count
        try:
            with sqlite3.connect(str(self.db.db_path)) as conn:
                total = conn.execute("SELECT COUNT(*) FROM kb_chunks").fetchone()[0]
        except Exception:
            total = 0

        embedded = self.embedding_ops.count_embeddings(self.model_name)

        return {
            "total_chunks": total,
            "embedded_chunks": embedded,
            "missing_chunks": total - embedded,
        }
