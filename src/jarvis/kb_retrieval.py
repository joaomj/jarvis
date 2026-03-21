"""Lexical retrieval pipeline for Jarvis knowledge-base answers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from jarvis.database import Database

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
MIN_TOKEN_LENGTH = 2
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "for",
    "from",
    "with",
    "my",
    "what",
    "is",
    "are",
    "in",
    "on",
    "of",
    "about",
    "please",
}


@dataclass(frozen=True)
class RetrievedChunk:
    """One retrieved KB chunk with document metadata."""

    chunk_id: int
    document_id: int
    chunk_index: int
    heading: str | None
    line_start: int
    line_end: int
    chunk_text: str
    title: str | None
    url_original: str | None
    markdown_path: str
    score: float


def build_fts_query(question: str) -> str:
    """Build a safe FTS5 query from user question."""
    tokens = [token.lower() for token in TOKEN_RE.findall(question)]
    filtered: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in STOPWORDS or len(token) < MIN_TOKEN_LENGTH or token in seen:
            continue
        filtered.append(token)
        seen.add(token)
    if not filtered:
        return ""
    return " OR ".join(f'"{token}"' for token in filtered[:16])


def retrieve_chunks(
    db: Database,
    question: str,
    *,
    limit: int,
    per_document_cap: int = 2,
) -> list[RetrievedChunk]:
    """Retrieve top chunks with diversity cap across documents."""
    query = build_fts_query(question)
    if not query:
        return []

    rows = db.search_chunks_fts(query, max(limit * 6, limit))
    if not rows:
        return []

    ranked_rows = sorted(
        rows,
        key=lambda row: (
            _source_priority(str(row.get("markdown_path", ""))),
            _as_float(row.get("score")),
        ),
    )

    selected: list[RetrievedChunk] = []
    per_doc_counts: dict[int, int] = {}
    for row in ranked_rows:
        doc_id = _as_int(row.get("document_id"))
        if per_doc_counts.get(doc_id, 0) >= per_document_cap:
            continue

        selected.append(
            RetrievedChunk(
                chunk_id=_as_int(row.get("chunk_id")),
                document_id=doc_id,
                chunk_index=_as_int(row.get("chunk_index")),
                heading=_as_optional_str(row.get("heading")),
                line_start=_as_int(row.get("line_start")),
                line_end=_as_int(row.get("line_end")),
                chunk_text=str(row.get("chunk_text", "")),
                title=_as_optional_str(row.get("title")),
                url_original=_as_optional_str(row.get("url_original")),
                markdown_path=str(row.get("markdown_path", "")),
                score=_as_float(row.get("score")),
            )
        )
        per_doc_counts[doc_id] = per_doc_counts.get(doc_id, 0) + 1
        if len(selected) >= limit:
            break

    return selected


def _source_priority(markdown_path: str) -> int:
    normalized = markdown_path.replace("\\", "/").lower()
    if "/attachments/" in normalized:
        return 0
    if "/memories/" in normalized:
        return 1
    if "/sources/web/" in normalized:
        return 2
    return 1


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value:
        return int(value)
    return 0


def _as_float(value: object) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str) and value:
        return float(value)
    return 0.0


def _as_optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
