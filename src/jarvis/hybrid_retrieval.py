"""Hybrid retrieval combining lexical (FTS) and semantic (embeddings) search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from jarvis.database import Database
from jarvis.embedding import EmbeddedChunk, EmbeddingGenerator, cosine_similarity
from jarvis.kb_retrieval import RetrievedChunk, _source_priority, build_fts_query, retrieve_chunks
from jarvis.logging_config import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

DEFAULT_LEXICAL_WEIGHT = 0.5
DEFAULT_SEMANTIC_WEIGHT = 0.5
DEFAULT_SEMANTIC_CANDIDATES = 50


@dataclass(frozen=True)
class HybridRetrievedChunk(RetrievedChunk):
    """Chunk with both lexical and semantic scores."""

    lexical_score: float = 0.0
    semantic_score: float = 0.0


def is_conceptual_query(query: str) -> bool:
    """Detect if query benefits from semantic search vs exact match."""
    query_lower = query.lower().strip()

    # Exact match indicators (lexical preferred)
    if '"' in query or "'" in query:
        return False
    if query_lower.startswith("http://") or query_lower.startswith("https://"):
        return False

    # Conceptual indicators
    conceptual_terms = [
        "what is",
        "what are",
        "how to",
        "explain",
        "meaning of",
        "about",
        "similar to",
        "like",
        "related to",
        "concept",
        "idea",
        "topic",
    ]
    return any(term in query_lower for term in conceptual_terms)


def hybrid_retrieve(  # noqa: PLR0913
    db: Database,
    query: str,
    *,
    limit: int = 6,
    lexical_weight: float = DEFAULT_LEXICAL_WEIGHT,
    semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
    semantic_candidates: int = DEFAULT_SEMANTIC_CANDIDATES,
    per_document_cap: int = 2,
    embedding_generator: EmbeddingGenerator | None = None,
) -> list[HybridRetrievedChunk]:
    """Retrieve chunks using hybrid lexical + semantic search."""
    lexical_query = build_fts_query(query)
    lexical_chunks: list[RetrievedChunk] = []

    if lexical_query:
        lexical_chunks = retrieve_chunks(
            db, query, limit=limit * 3, per_document_cap=per_document_cap * 2
        )

    logger.debug("lexical_search_complete", query=query[:50], lexical_results=len(lexical_chunks))

    # Get semantic results if embeddings available
    semantic_results: list[tuple[float, EmbeddedChunk]] = []
    if embedding_generator is not None and semantic_weight > 0:
        try:
            semantic_results = _semantic_search(
                db, query, embedding_generator, top_k=semantic_candidates
            )
            logger.debug(
                "semantic_search_complete", query=query[:50], semantic_results=len(semantic_results)
            )
        except Exception as error:
            logger.warning("semantic_search_failed", error=str(error))
            semantic_weight = 0

    # Merge and rerank
    merged = _merge_results(lexical_chunks, semantic_results, lexical_weight, semantic_weight, db)

    # Apply per-document cap and return top results
    results: list[HybridRetrievedChunk] = []
    per_doc_counts: dict[int, int] = {}

    for chunk in sorted(merged, key=_hybrid_sort_key):
        doc_id = chunk.document_id
        if per_doc_counts.get(doc_id, 0) >= per_document_cap:
            continue
        results.append(chunk)
        per_doc_counts[doc_id] = per_doc_counts.get(doc_id, 0) + 1
        if len(results) >= limit:
            break

    logger.info(
        "hybrid_retrieval_complete",
        query=query[:50],
        lexical_results=len(lexical_chunks),
        semantic_results=len(semantic_results),
        final_results=len(results),
    )
    return results


def _semantic_search(
    db: Database,
    query: str,
    embedding_generator: EmbeddingGenerator,
    top_k: int = 50,
) -> list[tuple[float, EmbeddedChunk]]:
    """Perform semantic search using embeddings.

    Returns:
        List of (similarity_score, chunk) tuples sorted by similarity descending.
    """

    from jarvis.database.embedding_ops import EmbeddingOperations  # noqa: PLC0415

    query_embedding = embedding_generator.embed_query(query)
    embedding_ops = EmbeddingOperations()
    embedding_ops.db_path = db.db_path
    all_chunks = embedding_ops.get_all_embeddings_with_chunks(
        model_name=embedding_generator.model_name
    )

    if not all_chunks:
        logger.debug("no_embeddings_in_database")
        return []

    scored_chunks: list[tuple[float, EmbeddedChunk]] = []
    for chunk in all_chunks:
        similarity = cosine_similarity(query_embedding, chunk.embedding)
        scored_chunks.append((similarity, chunk))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    return scored_chunks[:top_k]


def _get_chunk_details(db: Database, chunk_id: int) -> dict[str, Any] | None:
    """Get full chunk details including document metadata."""
    import sqlite3  # noqa: PLC0415

    try:
        with sqlite3.connect(str(db.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """SELECT
                    c.id as chunk_id,
                    c.document_id,
                    c.chunk_index,
                    c.heading,
                    c.line_start,
                    c.line_end,
                    c.chunk_text,
                    d.title,
                    d.url_original,
                    d.markdown_path
                FROM kb_chunks c
                JOIN kb_documents d ON d.id = c.document_id
                WHERE c.id = ?""",
                (chunk_id,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as error:
        logger.warning("get_chunk_details_failed", chunk_id=chunk_id, error=str(error))
        return None


def _merge_results(
    lexical_chunks: list[RetrievedChunk],
    semantic_results: list[tuple[float, EmbeddedChunk]],
    lexical_weight: float,
    semantic_weight: float,
    db: Database,
) -> list[HybridRetrievedChunk]:
    """Merge lexical and semantic results with weighted scoring."""
    lexical_max = max((c.score for c in lexical_chunks), default=1.0) or 1.0
    by_chunk_id: dict[int, HybridRetrievedChunk] = {}

    # Add lexical results (keyed by chunk_id to avoid collisions across documents)
    for chunk in lexical_chunks:
        normalized_lexical = chunk.score / lexical_max
        by_chunk_id[chunk.chunk_id] = HybridRetrievedChunk(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            heading=chunk.heading,
            line_start=chunk.line_start,
            line_end=chunk.line_end,
            chunk_text=chunk.chunk_text,
            title=chunk.title,
            url_original=chunk.url_original,
            markdown_path=chunk.markdown_path,
            score=normalized_lexical * lexical_weight,
            lexical_score=normalized_lexical,
            semantic_score=0.0,
        )

    # Calculate semantic max for normalization
    semantic_max = max((score for score, _ in semantic_results), default=1.0) or 1.0

    # Add/merge semantic results
    for similarity, chunk in semantic_results:
        normalized_semantic = similarity / semantic_max

        if chunk.chunk_id in by_chunk_id:
            # Merge with existing lexical result
            existing = by_chunk_id[chunk.chunk_id]
            by_chunk_id[chunk.chunk_id] = HybridRetrievedChunk(
                chunk_id=existing.chunk_id,
                document_id=existing.document_id,
                chunk_index=existing.chunk_index,
                heading=existing.heading,
                line_start=existing.line_start,
                line_end=existing.line_end,
                chunk_text=existing.chunk_text,
                title=existing.title,
                url_original=existing.url_original,
                markdown_path=existing.markdown_path,
                score=existing.score + (normalized_semantic * semantic_weight),
                lexical_score=existing.lexical_score,
                semantic_score=normalized_semantic,
            )
        else:
            # Add semantic-only chunk - need to fetch full details from DB
            details = _get_chunk_details(db, chunk.chunk_id)
            if details:
                by_chunk_id[chunk.chunk_id] = HybridRetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=details["document_id"],
                    chunk_index=details["chunk_index"],
                    heading=details.get("heading"),
                    line_start=details["line_start"],
                    line_end=details["line_end"],
                    chunk_text=details["chunk_text"],
                    title=details.get("title"),
                    url_original=details.get("url_original"),
                    markdown_path=details["markdown_path"],
                    score=normalized_semantic * semantic_weight,
                    lexical_score=0.0,
                    semantic_score=normalized_semantic,
                )

    return list(by_chunk_id.values())


def _hybrid_sort_key(chunk: HybridRetrievedChunk) -> tuple:
    """Sort key for hybrid results: source priority, then score descending."""
    return (_source_priority(chunk.markdown_path), -chunk.score)
