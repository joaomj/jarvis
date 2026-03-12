"""QMD vault search handlers."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from jarvis.logging_config import get_logger

if TYPE_CHECKING:
    from jarvis.bot import JarvisBot

logger = get_logger("qmd_handlers")

QMD_SCORE_HIGH = 70
QMD_SCORE_MEDIUM = 40
QMD_SNIPPET_MAX_LEN = 150


async def handle_recall(args: str, bot: JarvisBot) -> str:
    """Search vault content using QMD.

    Args:
        args: Search query
        bot: JarvisBot instance

    Returns:
        Response message with search results
    """
    if not args:
        return (
            "🔎 <b>Vault Search</b>\n\n"
            "Usage: <code>/recall &lt;query&gt;</code>\n\n"
            "Searches your vault:\n"
            "• X bookmarks\n"
            "• Saved URLs\n"
            "• Attachments\n"
            "• Memories"
        )

    query = args.strip()

    if not bot.qmd_client:
        logger.warning("qmd_client_not_initialized")
        return "❌ QMD search not available. Check QMD configuration."

    try:
        results = await bot.qmd_client.search(
            query=query,
            limit=bot.settings.qmd_search_limit,
            min_score=bot.settings.qmd_min_score,
        )
    except Exception as e:
        logger.error("qmd_search_failed", error=str(e), query=query[:50], exc_info=True)
        return f"❌ Search failed: {html.escape(str(e)[:100])}"

    if not results:
        return (
            f"🔍 <b>No results found</b>\n\n"
            f"Query: <code>{html.escape(query)}</code>\n\n"
            "Try different keywords or check if QMD has indexed your vault."
        )

    lines = [f"🔍 <b>Vault Results</b> ({len(results)} found)\n"]
    lines.append(f"Query: <code>{html.escape(query)}</code>\n")

    for i, result in enumerate(results, 1):
        score_pct = int(result.score * 100)
        score_emoji = (
            "🟢" if score_pct >= QMD_SCORE_HIGH else "🟡" if score_pct >= QMD_SCORE_MEDIUM else "⚪"
        )

        title = html.escape(result.title or result.display_path)
        context = f" [{html.escape(result.context)}]" if result.context else ""
        snippet = html.escape(
            result.snippet[:QMD_SNIPPET_MAX_LEN] + "..."
            if len(result.snippet) > QMD_SNIPPET_MAX_LEN
            else result.snippet
        )

        lines.append(f"\n{score_emoji} <b>{i}. {title}</b>{context}")
        lines.append(f"   Score: {score_pct}% | <code>{html.escape(result.display_path)}</code>")
        if snippet:
            lines.append(f"   {snippet}")

    lines.append("\n💡 Use <code>/recall {query}</code> to search again")
    return "\n".join(lines)
