"""Tests for vault-backed memory storage."""

from __future__ import annotations

from jarvis.database import Database
from jarvis.memory_store import MemoryStore


def test_memory_store_add_search_forget_cycle(tmp_path) -> None:
    """Memory entries are persisted, searchable, and forgettable."""
    db = Database(str(tmp_path / "test.db"))
    store = MemoryStore(db=db, vault_root=str(tmp_path / "vault"))

    created = store.add_memory(
        "Tocqueville emphasizes civil associations", tags=["book", "politics"]
    )
    assert created.memory_key.startswith("mem-")
    assert (tmp_path / "vault" / "memories" / f"{created.memory_key}.md").exists()

    matches = store.search("Tocqueville", limit=5)
    assert len(matches) == 1
    assert "civil associations" in matches[0].content

    forgotten = store.forget("Tocqueville")
    assert forgotten is not None
    assert forgotten.memory_key == created.memory_key

    no_matches = store.search("Tocqueville", limit=5)
    assert no_matches == []
