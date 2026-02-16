"""Jarvis command handlers.

Handles bridge-native commands that OpenCode doesn't have direct API for.
"""

import html
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from jarvis.logging_config import get_logger

if TYPE_CHECKING:
    from jarvis.bot import JarvisBot

MAX_TEXT_LENGTH = 100
MAX_BOOKMARKS_TO_SHOW = 10

logger = get_logger("commands")


async def handle_intercept_command(
    cmd: str, args: str, user_id: int, bot: "JarvisBot"
) -> str:
    """Handle intercepted OpenCode commands.

    Args:
        cmd: Command name (models, new, sessions)
        args: Command arguments
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message for user
    """
    handlers = {
        "models": _handle_models,
        "new": _handle_new_session,
        "sessions": _handle_list_sessions,
    }

    handler = handlers.get(cmd)
    if handler:
        return await handler(args, user_id, bot)

    return f"Unknown command: /{cmd}"


async def handle_bridge_command(
    cmd: str, args: str, user_id: int, bot: "JarvisBot"
) -> str:
    """Handle bridge-native commands.

    Args:
        cmd: Command name (switch, agent, model)
        args: Command arguments
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message for user
    """
    handlers = {
        "switch": _handle_switch,
        "agent": _handle_agent,
        "model": _handle_model,
    }

    handler = handlers.get(cmd)
    if handler:
        return await handler(args, user_id, bot)

    return f"Unknown bridge command: /{cmd}"


async def _handle_models(_args: str, user_id: int, bot: "JarvisBot") -> str:
    """Show available models and current model.

    Args:
        args: Command arguments (unused)
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message with available models
    """
    try:
        current = bot._get_model_for_user(user_id)

        lines = ["📋 <b>Available Models</b>\n"]

        if current:
            lines.append(f"Current: <code>{html.escape(current)}</code>")

        models = [
            "anthropic/claude-sonnet-4-20250514",
            "anthropic/claude-opus-4-20250514",
            "openai/gpt-4o",
            "google/gemini-2.5-pro",
        ]

        lines.append("\n<b>Favorites</b>:")
        for i, model in enumerate(models, 1):
            lines.append(f"{i}. <code>{html.escape(model)}</code>")

        lines.append("\nSet: <code>!model provider/model</code>")
        lines.append("Fav: <code>!models</code> then reply with number")

        return "\n".join(lines)
    except Exception as e:
        logger.error("_handle_models_failed", error=str(e), exc_info=True)
        return "❌ Failed to load models. Please try again."


async def _handle_new_session(args: str, user_id: int, bot: "JarvisBot") -> str:
    """Create new OpenCode session.

    Args:
        args: Optional session title
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message
    """
    title = args or f"Jarvis Session {user_id}"

    try:
        if not bot.opencode:
            return "❌ OpenCode client not initialized"

        session_id = await bot.opencode.create_session(title=title)
        bot.sessions[user_id] = session_id

        logger.info(
            "Created new session",
            session_id=session_id,
            title=title,
            user_id=user_id,
        )
        return f"✅ New session created:\n<code>{session_id}</code>"
    except Exception as e:
        logger.error("Failed to create session", error=str(e), user_id=user_id)
        return f"❌ Failed to create session: {html.escape(str(e))}"


async def _handle_list_sessions(_args: str, user_id: int, bot: "JarvisBot") -> str:
    """List user sessions.

    Args:
        args: Command arguments (unused)
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message with session info
    """
    try:
        current_session = bot.sessions.get(user_id, "None")

        lines = [
            "📋 <b>Your Sessions</b>\n",
            f"Current: <code>{current_session[:16]}...</code>" if current_session != "None" else "No active session",
            "\nTo create new: /new",
            "To switch: /switch &lt;session_id&gt;",
        ]

        return "\n".join(lines)
    except Exception as e:
        logger.error("_handle_list_sessions_failed", error=str(e), exc_info=True)
        return "❌ Failed to list sessions. Please try again."


async def _handle_switch(args: str, user_id: int, bot: "JarvisBot") -> str:
    """Switch to specified session.

    Args:
        args: Session ID to switch to
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message
    """
    try:
        if not args:
            return "Usage: /switch &lt;session_id&gt;"

        session_id = args.strip()
        bot.sessions[user_id] = session_id

        logger.info("Switched session", session_id=session_id, user_id=user_id)
        return f"✅ Switched to session: <code>{session_id}</code>"
    except Exception as e:
        logger.error("_handle_switch_failed", error=str(e), exc_info=True)
        return "❌ Failed to switch session. Please try again."


async def _handle_agent(args: str, user_id: int, _bot: "JarvisBot") -> str:
    """Agent management (placeholder).

    Args:
        args: Command arguments
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message
    """
    try:
        if not args or args.lower() == "get":
            return (
                "🤖 <b>Agent Management</b>\n\n"
                "Agents are configured per-session in OpenCode.\n"
                "Use OpenCode TUI to change agents.\n\n"
                "Current session agents persist automatically."
            )

        if args.lower().startswith("set "):
            agent_name = args[4:].strip()
            logger.info("Agent change requested", agent=agent_name, user_id=user_id)
            return f"✅ Agent <code>{html.escape(agent_name)}</code> will be used for new sessions."

        return (
            "Usage:\n"
            "/agent get - Show agent info\n"
            "/agent set &lt;name&gt; - Set default agent"
        )
    except Exception as e:
        logger.error("_handle_agent_failed", error=str(e), exc_info=True)
        return "❌ Failed to process agent command. Please try again."


async def _handle_model(args: str, user_id: int, bot: "JarvisBot") -> str:
    """Set or show model for session.

    Args:
        args: Model ID or empty to show current
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message
    """
    try:
        if not args:
            current = bot._get_model_for_user(user_id)
            is_custom = user_id in bot._model_preferences

            if current:
                status = "custom" if is_custom else "global"
                return (
                    f"🤖 <b>Current Model</b>\n\n"
                    f"<code>{html.escape(current)}</code>\n\n"
                    f"Source: {status}\n"
                    "Use <code>!model &lt;provider/model&gt;</code> to change."
                )
            return (
                "🤖 <b>Model</b>\n\n"
                "No model set.\n"
                "Use <code>!model &lt;provider/model&gt;</code> to set one."
            )

        model_id = args.strip()

        if "/" not in model_id:
            return (
                "⚠️ Model must be in format: <code>provider/model</code>\n"
                "Example: <code>anthropic/claude-sonnet-4-20250514</code>\n\n"
                "Use !models to see available models."
            )

        bot._model_preferences[user_id] = model_id

        logger.info("Set model preference", model=model_id, user_id=user_id)
        return f"✅ Model set to: <code>{html.escape(model_id)}</code>\n\nThis will be used for your messages."
    except Exception as e:
        logger.error("_handle_model_failed", error=str(e), exc_info=True)
        return "❌ Failed to set model. Please try again."


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

        lines = [f"📚 <b>Bookmarks from the {time_range}</b> ({len(bookmarks)} total)\n"]

        for i, bm in enumerate(bookmarks[:MAX_BOOKMARKS_TO_SHOW], 1):
            author = bm["author_username"]
            text = bm["text"][:MAX_TEXT_LENGTH] + "..." if len(bm["text"]) > MAX_TEXT_LENGTH else bm["text"]
            lines.append(f"\n<b>{i}.</b> @{html.escape(author)}\n{html.escape(text)}")

        if len(bookmarks) > MAX_BOOKMARKS_TO_SHOW:
            lines.append(f"\n<i>... and {len(bookmarks) - MAX_BOOKMARKS_TO_SHOW} more</i>")

        lines.append("\n\nReply with a number for details, or ask another question.")

        return "\n".join(lines)

    except Exception as e:
        logger.error("query_bookmarks_failed", error=str(e), exc_info=True)
        return f"❌ Failed to query bookmarks: {html.escape(str(e))}"
