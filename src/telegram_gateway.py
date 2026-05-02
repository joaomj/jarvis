"""Telegram gateway: polling, message routing, streaming responses."""
from __future__ import annotations

import uuid
from typing import Any

from src.agent import JarvisAgent
from src.skill_loader import SkillLoader


def generate_correlation_id() -> str:
    return str(uuid.uuid4())


class TelegramGateway:
    def __init__(
        self,
        agent: JarvisAgent,
        skill_loader: SkillLoader,
    ) -> None:
        self.agent = agent
        self.skill_loader = skill_loader

    async def handle_message(
        self, text: str, _user_id: int, send_chunk: Any
    ) -> str:
        """Route a message and stream the response."""
        cid = generate_correlation_id()

        if text.startswith("/"):
            await send_chunk("Working on it...")
            parts = text.split(maxsplit=1)
            command = parts[0][1:]
            args = parts[1] if len(parts) > 1 else ""
            skill = self.skill_loader.load_skill(command)
            async for chunk in self.agent.run_stream(args or text, skill=skill):
                await send_chunk(chunk)
            return cid

        suggestion = self.agent.find_matching_skill(text)
        if suggestion:
            return f"SKILL:{suggestion}"

        async for chunk in self.agent.run_stream(text):
            await send_chunk(chunk)
        return cid
