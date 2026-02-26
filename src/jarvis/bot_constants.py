"""Shared constants and helpers for bot behavior."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

BOOKMARK_KEYWORDS = {
    "what did i save",
    "from my saved",
    "my saved",
    "bookmarked",
    "my tweets",
    "my bookmarks",
    "saved posts",
}

SAVE_INTENT_KEYWORDS = {
    "save",
    "scrape",
    "read later",
    "knowledge base",
    "add to knowledge base",
}

KB_QUERY_KEYWORDS = {
    "considering my knowledge base",
    "from what i saved",
    "from my saved articles",
    "knowledge base",
    "saved articles",
}

TIME_EXPRESSIONS = {
    "last week",
    "past week",
    "last month",
    "past month",
    "yesterday",
    "today",
    "recent",
}

WEEKLY_RECONCILE_DAYS = 7


def build_feedback_keyboard(turn_id: int) -> InlineKeyboardMarkup:
    """Build inline keyboard with thumbs up/down buttons."""
    keyboard = [
        [
            InlineKeyboardButton("👍", callback_data=f"fb:{turn_id}:up"),
            InlineKeyboardButton("👎", callback_data=f"fb:{turn_id}:down"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
