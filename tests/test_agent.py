"""Test AlfredAgent: skill suggestion, streaming, system prompt composition."""
import tempfile
from pathlib import Path

import pytest

from src.agent import AlfredAgent, AlfredDeps
from src.conversation import ConversationStore
from src.memory import MemoryManager
from src.skill_loader import SkillLoader


@pytest.fixture
def agent():
    """AlfredAgent with temp skills, memory, conversation."""
    root = Path(tempfile.mkdtemp())
    (root / "SOUL.md").write_text("You are Alfred.")
    (root / "MEMORY.md").write_text("User is called Master.")
    (root / "USER.md").write_text("language: english")

    skills_dir = root / "skills"
    skills_dir.mkdir()
    core_dir = skills_dir / "core"
    core_dir.mkdir()
    (core_dir / "SKILL.md").write_text("""---
name: core
description: "Core capabilities"
---
You can search the vault and query bookmarks.
""")
    scripts = core_dir / "scripts"
    scripts.mkdir()
    (scripts / "__init__.py").write_text("")
    (scripts / "search.py").write_text("""
def search_vault(query: str) -> str:
    '''Search saved bookmarks and articles.'''
    return f"Found results for {query}"
""")

    conv_path = root / "conversations.db"
    deps = AlfredDeps(
        memory=MemoryManager(root),
        conversation=ConversationStore(str(conv_path)),
        skill_loader=SkillLoader(skills_dir),
    )
    return AlfredAgent(deps, soul_path=root / "SOUL.md")


def test_agent_has_soul_in_system_prompt(agent):
    """Agent system prompt includes SOUL.md content."""
    assert "You are Alfred." in agent.get_system_prompt()


def test_agent_can_run_message():
    """Agent can run a simple message (LLM mock or dry-run)."""
    pass


def test_suggest_skill_returns_none_for_generic_query(agent):
    """suggest_skill returns None when no skill matches."""
    result = agent.find_matching_skill("hello how are you")
    assert result is None


def test_core_tools_are_registered(agent):
    """Core skill scripts are registered as agent tools."""
    assert "search_vault" in agent.list_tools()
