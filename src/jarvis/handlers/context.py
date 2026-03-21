"""Native context handlers for hybrid /recall search."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from jarvis.logging_config import get_logger

if TYPE_CHECKING:
    from jarvis.bot import JarvisBot

logger = get_logger("context_handlers")


async def handle_recall(args: str, bot: JarvisBot) -> str:
    """Search across memories and KB using hybrid retrieval."""
    query = args.strip()
    if not query:
        return (
            "🔎 <b>Context Search</b>\n\n"
            "Usage: <code>/recall &lt;query&gt;</code>\n\n"
            "Searches your unified context:\n"
            "• Memories\n"
            "• Saved URLs and attachments"
        )

    try:
        limit = max(1, bot.settings.kb_max_chunks_per_query)
        results = bot.context_store.search(query=query, limit=limit)
    except Exception as error:
        logger.error("context_recall_failed", query=query[:80], error=str(error), exc_info=True)
        return f"❌ Search failed: {html.escape(str(error)[:120])}"

    if not results:
        return (
            f"🔍 <b>No results found</b>\n\n"
            f"Query: <code>{html.escape(query)}</code>\n\n"
            "Try different keywords or broaden the query."
        )

    lines = [f"🔍 <b>Context Results</b> ({len(results)} found)"]
    lines.append(f"Query: <code>{html.escape(query)}</code>")
    lines.append("")

    for index, item in enumerate(results, start=1):
        score_pct = int(item.score * 100)
        icon = "🧠" if item.entry_type == "memory" else "📄"
        title = html.escape(item.title)
        snippet = html.escape(item.snippet)
        lines.append(f"{icon} <b>{index}. {title}</b> ({score_pct}%)")
        if item.memory_key:
            lines.append(f"   key: <code>{html.escape(item.memory_key)}</code>")
        if item.source_path:
            lines.append(f"   source: <code>{html.escape(item.source_path)}</code>")
        lines.append(f"   {snippet}")
        lines.append("")

    if not bot.context_store.vector_ready:
        lines.append("⚠️ semantic vectors unavailable; results are lexical-only.")

    return "\n".join(lines).rstrip()
