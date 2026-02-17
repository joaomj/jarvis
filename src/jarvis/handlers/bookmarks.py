"""Bookmark query handling.

Natural language processing for X bookmark queries.
"""

import html
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from jarvis.logging_config import get_logger

if TYPE_CHECKING:
    from jarvis.bot import JarvisBot

logger = get_logger("bookmarks_query")


async def query_bookmarks(query: str, bot: "JarvisBot") -> str:
    """Query bookmarks using natural language.

    Args:
        query: Natural language query about bookmarks.
        bot: JarvisBot instance.

    Returns:
        Response message with bookmark summaries.
    """
    try:
        query_lower = query.lower()

        if "last week" in query_lower or "past week" in query_lower:
            end_date = datetime.now(UTC)
            start_date = end_date - timedelta(days=7)
            bookmarks = bot.db.get_bookmarks_by_time_range(
                start_date.isoformat(),
                end_date.isoformat(),
            )
            time_range = "last week"
        elif "last month" in query_lower or "past month" in query_lower:
            end_date = datetime.now(UTC)
            start_date = end_date - timedelta(days=30)
            bookmarks = bot.db.get_bookmarks_by_time_range(
                start_date.isoformat(),
                end_date.isoformat(),
            )
            time_range = "last month"
        elif "today" in query_lower:
            end_date = datetime.now(UTC)
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            bookmarks = bot.db.get_bookmarks_by_time_range(
                start_date.isoformat(),
                end_date.isoformat(),
            )
            time_range = "today"
        else:
            sync_status = bot.db.get_sync_status()
            if sync_status:
                total = sync_status.get("total_bookmarks", 0)
                return (
                    f"📚 <b>X Bookmarks</b>\n\n"
                    f"You have <b>{total}</b> bookmarks saved.\n\n"
                    "Try asking:\n"
                    "• \"What did I save in the last week?\"\n"
                    "• \"Show me my recent bookmarks\"\n"
                    "• \"Tell me about my AI/ML tweets\""
                )
            return "📚 No bookmarks synced yet. Use /x-auth to connect your X account."

        if not bookmarks:
            return f"📚 No bookmarks found in the {time_range}."

        max_display = bot.settings.bookmarks_max_display_count
        preview_length = bot.settings.bookmarks_text_preview_length
        lines = [f"📚 <b>Bookmarks from the {time_range}</b> ({len(bookmarks)} total)\n"]

        for i, bm in enumerate(bookmarks[:max_display], 1):
            author = bm["author_username"]
            text = bm["text"][:preview_length] + "..." if len(bm["text"]) > preview_length else bm["text"]
            lines.append(f"\n<b>{i}.</b> @{html.escape(author)}\n{html.escape(text)}")

        if len(bookmarks) > max_display:
            lines.append(f"\n<i>... and {len(bookmarks) - max_display} more</i>")

        lines.append("\n\nReply with a number for details, or ask another question.")

        return "\n".join(lines)

    except Exception as e:
        logger.error("query_bookmarks_failed", error=str(e), exc_info=True)
        return f"❌ Failed to query bookmarks: {html.escape(str(e))}"
