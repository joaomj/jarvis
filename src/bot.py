"""Main bot entry point — wires all dependencies."""
from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path
from typing import Any

from src.agent import JarvisAgent, JarvisDeps
from src.config import Settings, get_settings
from src.conversation import ConversationStore
from src.memory import MemoryManager
from src.polling_engine import PollingEngine
from src.skill_loader import SkillLoader
from src.telegram_gateway import TelegramGateway


def create_app(settings: Settings | None = None) -> dict[str, Any]:
    if settings is None:
        settings = get_settings()
    memory = MemoryManager(root_dir=Path(settings.soul_path).parent)
    conversation = ConversationStore(settings.database_path)
    skill_loader = SkillLoader(skills_root=Path("skills"))
    deps = JarvisDeps(
        memory=memory,
        conversation=conversation,
        skill_loader=skill_loader,
    )
    agent = JarvisAgent(
        deps=deps,
        soul_path=memory.root / "SOUL.md",
        model=settings.model,
    )
    gateway = TelegramGateway(agent=agent, skill_loader=skill_loader)
    polling = PollingEngine(
        bot_token=settings.telegram_bot_token,
        interval=settings.telegram_polling_interval,
        timeout=settings.telegram_polling_timeout,
        max_backoff_level=settings.polling_max_backoff_level,
        max_backoff_seconds=settings.polling_max_backoff_seconds,
    )
    return {
        "settings": settings,
        "memory": memory,
        "conversation": conversation,
        "skill_loader": skill_loader,
        "agent": agent,
        "gateway": gateway,
        "polling": polling,
    }


async def handle_update(
    update: dict[str, Any],
    gateway: TelegramGateway,
    settings: Settings,
) -> None:
    message = update.get("message") or {}
    text: str | None = message.get("text")
    user_id: int | None = (message.get("from") or {}).get("id")
    chat_id: int | None = (message.get("chat") or {}).get("id")

    if not text or not user_id or not chat_id:
        return

    if user_id != settings.telegram_user_id:
        return

    async def send_chunk(chunk: str) -> None:
        pass

    await gateway.handle_message(text, user_id, send_chunk)


async def run_bot(settings: Settings | None = None) -> None:
    if settings is None:
        settings = get_settings()
    app = create_app(settings)
    gateway: TelegramGateway = app["gateway"]
    polling: PollingEngine = app["polling"]

    async def handler(update: dict[str, Any]) -> None:
        await handle_update(update, gateway, settings)

    stop_event = asyncio.Event()

    def signal_handler(_sig: int, _: object) -> None:
        polling.stop()
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await polling.start(handler)
    await stop_event.wait()


def main() -> None:
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
