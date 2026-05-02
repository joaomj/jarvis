"""PydanticAI agent with skill loading, streaming, and ask-before-acting."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext

from src.conversation import ConversationStore
from src.memory import MemoryManager
from src.skill_loader import Skill, SkillLoader


@dataclass
class JarvisDeps:
    memory: MemoryManager
    conversation: ConversationStore
    skill_loader: SkillLoader
    active_skill: Skill | None = None


class JarvisAgent:
    def __init__(
        self,
        deps: JarvisDeps,
        soul_path: Path,
        model: str = "anthropic:claude-sonnet-4-20250514",
    ) -> None:
        self.deps = deps
        self.soul_path = soul_path
        self._model = model
        self._tools: dict[str, Any] = {}
        self._agent: Agent[JarvisDeps] | None = None

        self._register_core_tools()

    def _get_agent(self) -> Agent[JarvisDeps]:
        if self._agent is None:
            self._agent = Agent(
                model=self._model,
                deps_type=JarvisDeps,
            )
            self._agent.system_prompt(self._build_system_prompt)
        return self._agent

    @staticmethod
    def _build_system_prompt(ctx: RunContext[JarvisDeps]) -> str:
        parts = [ctx.deps.memory.get_context()]
        if ctx.deps.active_skill:
            parts.append(
                f"[Active Skill: {ctx.deps.active_skill.name}]\n"
                f"{ctx.deps.active_skill.instructions}"
            )
        return "\n\n".join(parts)

    def _register_core_tools(self) -> None:
        core = self.deps.skill_loader.load_core_skills()
        for skill in core:
            for name, fn in skill.tools.items():
                self._tools[name] = fn

    def get_system_prompt(self) -> str:
        return self.deps.memory.get_context()

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())

    def find_matching_skill(self, query: str) -> str | None:
        q = query.lower()
        for name in self.deps.skill_loader.list_skills():
            skill = self.deps.skill_loader.load_skill(name)
            if name in q or skill.description.lower() in q:
                return name
        return None

    async def run_stream(
        self, message: str, skill: Skill | None = None
    ) -> AsyncIterator[str]:
        self.deps.active_skill = skill
        agent = self._get_agent()
        try:
            async with agent.run_stream(message, deps=self.deps) as result:
                async for chunk in result.stream():
                    yield chunk
        finally:
            self.deps.active_skill = None
