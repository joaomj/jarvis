"""Unified context search/index built on SQLite + sqlite-vec."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.context_vector_store import (
    auto_link,
    ensure_vector_schema,
    select_missing_embedding_targets,
    semantic_candidates,
    upsert_embedding,
)
from jarvis.embeddings import embed_batch, embed_text
from jarvis.kb_retrieval import build_fts_query
from jarvis.logging_config import get_logger

if TYPE_CHECKING:
    from jarvis.database import Database

logger = get_logger(__name__)

RRF_K = 60
SEMANTIC_MULTIPLIER = 4
GRAPH_ONE_HOP_LIMIT = 2


@dataclass(frozen=True)
class ContextResult:
    """One result across memories and KB chunks."""

    entry_type: str
    entry_id: int
    title: str
    snippet: str
    score: float
    source_path: str | None = None
    source_url: str | None = None
    memory_key: str | None = None


class ContextStore:
    """Semantic + lexical context storage and retrieval."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._db_path = str(db.db_path)
        self._vector_ready = ensure_vector_schema(self._db_path)

    @property
    def vector_ready(self) -> bool:
        """Whether sqlite-vec index is available for semantic search."""
        return self._vector_ready

    def index_memory(self, memory_id: int, title: str, content: str) -> None:
        """Compute and persist memory embedding."""
        if not self._vector_ready:
            return
        text = f"{title}\n{content}".strip()
        embedding = embed_text(text)
        content_hash = _hash_text(text)
        upsert_embedding(self._db_path, "memory", memory_id, embedding, content_hash)
        auto_link(self._db_path, "memory", memory_id, embedding)

    def index_kb_document_chunks(self, document_id: int) -> None:
        """Compute and persist embeddings for all chunks in a document."""
        if not self._vector_ready:
            return
        rows = self._db.get_chunks_for_document(document_id)
        if not rows:
            return

        texts = [
            _normalize_chunk_text(
                title=str(row.get("title", "") or ""),
                heading=str(row.get("heading", "") or ""),
                chunk=str(row.get("chunk_text", "") or ""),
            )
            for row in rows
        ]
        vectors = embed_batch(texts)
        if len(vectors) != len(rows):
            logger.warning(
                "kb_chunk_embedding_count_mismatch",
                document_id=document_id,
                chunks=len(rows),
                vectors=len(vectors),
            )
            return

        for row, vector, text in zip(rows, vectors, texts, strict=True):
            chunk_id = _to_int(row.get("chunk_id"))
            upsert_embedding(self._db_path, "kb_chunk", chunk_id, vector, _hash_text(text))
            auto_link(self._db_path, "kb_chunk", chunk_id, vector)

    def search(self, query: str, limit: int = 6) -> list[ContextResult]:
        """Run hybrid retrieval with RRF fusion and one-hop graph expansion."""
        normalized = query.strip()
        if not normalized:
            return []

        lexical_ranked = self._lexical_candidates(normalized, limit=max(limit * 3, 12))
        semantic_ranked = (
            semantic_candidates(
                self._db_path,
                embed_text(normalized),
                limit=max(limit * SEMANTIC_MULTIPLIER, 12),
            )
            if self._vector_ready
            else []
        )

        scores: dict[tuple[str, int], float] = {}
        for rank, key in enumerate(lexical_ranked, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)
        for rank, key in enumerate(semantic_ranked, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)

        expanded = self._expand_one_hop(scores)
        merged = sorted(expanded.items(), key=lambda item: item[1], reverse=True)

        results: list[ContextResult] = []
        for (entry_type, entry_id), score in merged:
            record = self._hydrate(entry_type, entry_id)
            if record is None:
                continue
            results.append(record_with_score(record, score))
            if len(results) >= limit:
                break

        return results

    def backfill_missing_embeddings(self, limit_per_type: int = 300) -> None:
        """Backfill embeddings for existing rows not yet indexed."""
        if not self._vector_ready:
            return
        memory_rows, document_ids = select_missing_embedding_targets(
            self._db_path,
            limit_per_type,
        )
        for memory_id, title, content in memory_rows:
            self.index_memory(memory_id, title, content)
        for document_id in document_ids:
            self.index_kb_document_chunks(document_id)

    def _lexical_candidates(self, query: str, limit: int) -> list[tuple[str, int]]:
        """Get ranked lexical candidates across memory and KB."""
        ranked: list[tuple[str, int]] = []

        memory_rows = self._db.search_active_memories(query=query, limit=limit)
        ranked.extend(("memory", _to_int(row.get("id"))) for row in memory_rows if row.get("id"))

        fts_query = build_fts_query(query)
        if fts_query:
            kb_rows = self._db.search_chunks_fts(fts_query, limit)
            ranked.extend(
                ("kb_chunk", _to_int(row.get("chunk_id"))) for row in kb_rows if row.get("chunk_id")
            )

        deduped: list[tuple[str, int]] = []
        seen: set[tuple[str, int]] = set()
        for key in ranked:
            if key in seen:
                continue
            seen.add(key)
            deduped.append(key)
        return deduped

    def _expand_one_hop(self, scores: dict[tuple[str, int], float]) -> dict[tuple[str, int], float]:
        """Add one-hop related items with discounted score."""
        if not scores:
            return scores

        expanded = dict(scores)
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                top_keys = sorted(scores.items(), key=lambda item: item[1], reverse=True)[
                    :GRAPH_ONE_HOP_LIMIT
                ]
                for (entry_type, entry_id), base_score in top_keys:
                    rows = conn.execute(
                        """SELECT target_type, target_id, strength
                           FROM context_links
                           WHERE source_type = ? AND source_id = ?
                           UNION ALL
                           SELECT source_type AS target_type, source_id AS target_id, strength
                           FROM context_links
                           WHERE target_type = ? AND target_id = ?""",
                        (entry_type, entry_id, entry_type, entry_id),
                    ).fetchall()
                    for row in rows:
                        key = (str(row["target_type"]), _to_int(row["target_id"]))
                        link_strength = float(row["strength"])
                        expanded[key] = max(
                            expanded.get(key, 0.0), base_score * 0.4 * link_strength
                        )
            return expanded
        except Exception as error:
            logger.warning("graph_expansion_failed", error=str(error))
            return expanded

    def _hydrate(self, entry_type: str, entry_id: int) -> ContextResult | None:
        """Hydrate entry to display result."""
        if entry_type == "memory":
            row = self._db.get_memory_by_id(entry_id)
            if not row:
                return None
            if _to_int(row.get("active")) != 1:
                return None
            content = str(row.get("content", "")).strip()
            return ContextResult(
                entry_type="memory",
                entry_id=entry_id,
                title=str(row.get("title", row.get("memory_key", "memory"))),
                snippet=_snippet(content),
                score=0.0,
                source_path=str(row.get("markdown_path", "") or "") or None,
                memory_key=str(row.get("memory_key", "") or "") or None,
            )

        if entry_type == "kb_chunk":
            row = self._db.get_chunk_by_id(entry_id)
            if not row:
                return None
            return ContextResult(
                entry_type="kb_chunk",
                entry_id=entry_id,
                title=str(row.get("title", "Knowledge Chunk") or "Knowledge Chunk"),
                snippet=_snippet(str(row.get("chunk_text", ""))),
                score=0.0,
                source_path=str(row.get("markdown_path", "") or "") or None,
                source_url=str(row.get("url_original", "") or "") or None,
            )

        return None


def _normalize_chunk_text(title: str, heading: str, chunk: str) -> str:
    """Normalize chunk text used for embedding and hash identity."""
    combined = "\n".join(part for part in [title.strip(), heading.strip(), chunk.strip()] if part)
    return combined[:2000]


def _hash_text(value: str) -> str:
    """Compute stable SHA256 hash of normalized text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _snippet(text: str, max_chars: int = 180) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[: max_chars - 3]}..."


def record_with_score(record: ContextResult, score: float) -> ContextResult:
    """Return new immutable record with computed score."""
    return ContextResult(
        entry_type=record.entry_type,
        entry_id=record.entry_id,
        title=record.title,
        snippet=record.snippet,
        score=score,
        source_path=record.source_path,
        source_url=record.source_url,
        memory_key=record.memory_key,
    )


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
