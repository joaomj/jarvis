"""Test MemoryManager: SOUL.md, MEMORY.md, USER.md read/write/compact."""
import tempfile
from pathlib import Path

import pytest

from src.memory import MemoryManager


@pytest.fixture
def memory():
    """MemoryManager backed by temp directory."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "SOUL.md").write_text("You are Alfred.")
        (root / "MEMORY.md").write_text("")
        (root / "USER.md").write_text("")
        yield MemoryManager(root)


def test_get_context_returns_soul_and_memory_and_user(memory):
    """get_context concatenates SOUL.md + MEMORY.md + USER.md."""
    memory.update_memory("User prefers short answers.")
    memory.update_user_profile("language", "english")

    ctx = memory.get_context()
    assert "You are Alfred." in ctx
    assert "User prefers short answers." in ctx
    assert "language: english" in ctx


def test_update_memory_enforces_limit(memory):
    """MEMORY.md never exceeds 2200 characters."""
    long_fact = "x" * 2300
    memory.update_memory(long_fact)
    content = memory.read_memory_md()
    assert len(content) <= 2200


def test_update_memory_trims_oldest_on_overflow(memory):
    """When limit exceeded, oldest entries are trimmed first."""
    memory.update_memory("First entry.")
    memory.update_memory("Second entry.")
    memory.update_memory("A" * 2200)  # forces trim
    content = memory.read_memory_md()
    assert "First entry" not in content


def test_update_user_profile(memory):
    """update_user_profile appends key: value to USER.md."""
    memory.update_user_profile("timezone", "UTC")
    content = memory.read_user_md()
    assert "timezone: UTC" in content


def test_read_soul_md(memory):
    """read_soul_md returns SOUL.md content."""
    assert "You are Alfred." in memory.read_soul_md()
