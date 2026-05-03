"""Main bot entry point — wires all dependencies."""
from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path
from typing import Any

from src.agent import AlfredAgent, AlfredDeps
from src.config import Settings, get_settings
from src.conversation import ConversationStore
from src.logging_config import setup_logging
from src.memory import MemoryManager
from src.polling_engine import PollingEngine
from src.skill_loader import SkillLoader
from src.telegram_gateway import TelegramGateway

logger = __import__("logging").getLogger(__name__)


def create_app(settings: Settings | None = None) -> dict[str, Any]:
    if settings is None:
        settings = get_settings()
    memory = MemoryManager(root_dir=Path(settings.soul_path).parent)
    conversation = ConversationStore(settings.database_path)
    skill_loader = SkillLoader(skills_root=Path("skills"))
    deps = AlfredDeps(
        memory=memory,
        conversation=conversation,
        skill_loader=skill_loader,
    )
    agent = AlfredAgent(
        deps=deps,
        soul_path=memory.root / "SOUL.md",
        model=settings.model,
        api_key=settings.opencode_go_api_key,
    )
    polling = PollingEngine(
        bot_token=settings.telegram_bot_token,
        interval=settings.telegram_polling_interval,
        timeout=settings.telegram_polling_timeout,
        max_backoff_level=settings.polling_max_backoff_level,
        max_backoff_seconds=settings.polling_max_backoff_seconds,
    )
    gateway = TelegramGateway(
        agent=agent,
        skill_loader=skill_loader,
        conversation=conversation,
        polling=polling,
        settings=settings,
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


async def run_bot(settings: Settings | None = None) -> None:
    if settings is None:
        settings = get_settings()
    setup_logging(settings.log_level)
    app = create_app(settings)
    gateway: TelegramGateway = app["gateway"]
    polling: PollingEngine = app["polling"]

    async def handler(update: dict[str, Any]) -> None:
        await gateway.handle_update(update)

    stop_event = asyncio.Event()

    def signal_handler(_sig: int, _: object) -> None:
        polling.stop()
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("starting_alfred", extra={"env": settings.alfred_env})
    await polling.start(handler)
    await stop_event.wait()


def main() -> None:
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
