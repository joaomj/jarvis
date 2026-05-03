"""PydanticAI agent with skill loading, streaming, and ask-before-acting."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from src.conversation import ConversationStore
from src.memory import MemoryManager
from src.skill_loader import Skill, SkillLoader

PROVIDER_BASE_URLS: dict[str, str] = {
    "opencode-go": "https://opencode.ai/zen/go/v1",
}


@dataclass
class AlfredDeps:
    memory: MemoryManager
    conversation: ConversationStore
    skill_loader: SkillLoader
    active_skill: Skill | None = None


def build_model(model_str: str, api_key: str = "") -> OpenAIChatModel | str:
    """Build a PydanticAI model from a 'provider:model' string.

    For OpenAI-compatible providers (opencode-go), returns an OpenAIChatModel
    with the appropriate base_url. For built-in providers, returns the string
    so PydanticAI resolves it.
    """
    if ":" not in model_str:
        return model_str

    provider, _, model_name = model_str.partition(":")

    if provider in PROVIDER_BASE_URLS:
        return OpenAIChatModel(
            model_name,
            provider=OpenAIProvider(
                base_url=PROVIDER_BASE_URLS[provider],
                api_key=api_key,
            ),
        )

    return model_str


class AlfredAgent:
    def __init__(
        self,
        deps: AlfredDeps,
        soul_path: Path,
        model: str = "opencode-go:deepseek-v4-flash",
        api_key: str = "",
    ) -> None:
        self.deps = deps
        self.soul_path = soul_path
        self._model_str = model
        self._api_key = api_key
        self._tools: dict[str, Any] = {}
        self._agent: Agent[AlfredDeps] | None = None

        self._register_core_tools()

    def _get_agent(self) -> Agent[AlfredDeps]:
        if self._agent is None:
            model = build_model(self._model_str, self._api_key)
            self._agent = Agent(
                model=model,
                deps_type=AlfredDeps,
            )
            self._agent.system_prompt(self._build_system_prompt)
        return self._agent

    @staticmethod
    def _build_system_prompt(ctx: RunContext[AlfredDeps]) -> str:
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

    def update_model(self, model_str: str, api_key: str = "") -> None:
        """Hot-swap the LLM model at runtime."""
        self._model_str = model_str
        self._api_key = api_key
        self._agent = None

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
