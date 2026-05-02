"""Test ConversationStore: message history, FTS5 search, session lifecycle."""
import tempfile
from pathlib import Path

import pytest

from src.conversation import ConversationStore


@pytest.fixture
def store():
    """Create a ConversationStore backed by a temporary database."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test_conversations.db"
        yield ConversationStore(str(db_path))


def test_add_and_retrieve_messages(store):
    """Messages are persisted and retrievable in order."""
    sid = store.new_session()
    store.add_message(sid, "user", "Hello", "corr-1")
    store.add_message(sid, "assistant", "Hi there", "corr-2")

    history = store.get_history(sid)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello"
    assert history[1]["role"] == "assistant"


def test_get_history_respects_limit(store):
    """get_history returns at most `limit` messages."""
    sid = store.new_session()
    for i in range(10):
        store.add_message(sid, "user", f"msg {i}", f"corr-{i}")

    history = store.get_history(sid, limit=5)
    assert len(history) == 5
    assert history[0]["content"] == "msg 5"


def test_new_session_creates_unique_id(store):
    """Each new_session() returns a different id."""
    sid1 = store.new_session()
    sid2 = store.new_session()
    assert sid1 != sid2


def test_search_conversations_finds_content(store):
    """FTS5 search retrieves messages containing the query."""
    sid = store.new_session()
    store.add_message(sid, "user", "quantum computing is fascinating", "corr-1")
    store.add_message(sid, "assistant", "Yes, it is", "corr-2")

    results = store.search_conversations("quantum")
    assert len(results) > 0
    assert "quantum" in results[0]["content"]
