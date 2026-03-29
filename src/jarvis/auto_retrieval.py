"""Auto-retrieval engine: retrieves relevant context for every user message."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from jarvis.context_store import ContextStore
from jarvis.logging_config import get_logger

logger = get_logger(__name__)

MAX_CONTEXT_CHARS = 2000


@dataclass(frozen=True)
class RetrievedContext:
    """Formatted context for injection into OpenCode prompt."""

    system_prefix: str
    sources_used: int


def retrieve_context(
    context_store: ContextStore,
    opencode_db_path: str,
    query: str,
    *,
    max_chars: int = MAX_CONTEXT_CHARS,
    max_results: int = 6,
) -> RetrievedContext:
    """Retrieve relevant context from KB and OpenCode conversation history.

    Args:
        context_store: The hybrid search context store.
        opencode_db_path: Path to OpenCode's SQLite database (read-only).
        query: User's message text used as search query.
        max_chars: Maximum characters for the formatted context.
        max_results: Maximum number of KB results.

    Returns:
        RetrievedContext with formatted system prefix and source count.
    """
    if not query.strip():
        return RetrievedContext(system_prefix="", sources_used=0)

    snippets: list[tuple[str, str, float]] = []

    try:
        kb_results = context_store.search(query, limit=max_results)
        for result in kb_results:
            source = result.source_url or result.source_path or "unknown"
            snippets.append((result.snippet, source, result.score))
    except Exception as error:
        logger.warning("kb_retrieval_failed", error=str(error))

    try:
        conversation_snippets = _search_opencode_history(opencode_db_path, query)
        for snippet, source in conversation_snippets:
            snippets.append((snippet, source, 0.0))
    except Exception as error:
        logger.warning("opencode_history_search_failed", error=str(error))

    if not snippets:
        return RetrievedContext(system_prefix="", sources_used=0)

    snippets.sort(key=lambda s: s[2], reverse=True)
    unique_snippets = _deduplicate(snippets[:max_results])

    lines: list[str] = []
    total_chars = 0
    for snippet, source, _ in unique_snippets:
        entry = f"- [{source}] {snippet}"
        if total_chars + len(entry) + 1 > max_chars:
            break
        lines.append(entry)
        total_chars += len(entry) + 1

    if not lines:
        return RetrievedContext(system_prefix="", sources_used=0)

    prefix = (
        "The user has relevant saved content. Use these as context when helpful, "
        "but don't force references if they aren't relevant to the question:\n" + "\n".join(lines)
    )
    return RetrievedContext(system_prefix=prefix, sources_used=len(lines))


def _search_opencode_history(db_path: str, query: str, limit: int = 3) -> list[tuple[str, str]]:
    """Search OpenCode session history for relevant past conversations."""
    db_uri = f"file:{db_path}?mode=ro"
    try:
        with sqlite3.connect(db_uri) as conn:
            conn.row_factory = sqlite3.Row
            like = f"%{query.strip()}%"
            rows = conn.execute(
                """SELECT s.title, substr(p.text, 1, 200) as snippet, s.time_updated
                   FROM part p
                   JOIN message m ON m.id = p.message_id
                   JOIN session s ON s.id = m.session_id
                   WHERE s.parent_id IS NULL
                     AND p.data LIKE '%{"type":"text"}%'
                     AND p.data LIKE ?
                   ORDER BY s.time_updated DESC
                   LIMIT ?""",
                (f'%"text":"%{like}%', limit),
            ).fetchall()
            return [
                (
                    str(row["snippet"]).strip(),
                    f"conversation: {row['title'] or 'untitled'}",
                )
                for row in rows
                if row["snippet"]
            ]
    except Exception as error:
        logger.debug("opencode_db_unavailable", error=str(error))
        return []


def _deduplicate(snippets: list[tuple[str, str, float]]) -> list[tuple[str, str, float]]:
    """Remove duplicate snippets based on text similarity."""
    seen: set[str] = set()
    unique: list[tuple[str, str, float]] = []
    for snippet, source, score in snippets:
        normalized = " ".join(snippet.split()).lower()[:60]
        if normalized not in seen:
            seen.add(normalized)
            unique.append((snippet, source, score))
    return unique
