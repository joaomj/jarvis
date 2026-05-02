"""SQLite-backed conversation history with FTS5 search."""
from __future__ import annotations

import sqlite3
import uuid


class ConversationStore:
    def __init__(self, db_path: str) -> None:
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            correlation_id TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts
            USING fts5(content, session_id, tokenize='porter unicode61',
                       content='conversations', content_rowid='id');
        CREATE TRIGGER IF NOT EXISTS conversations_ai AFTER INSERT ON conversations
        BEGIN
            INSERT INTO conversations_fts(rowid, content, session_id)
            VALUES (new.id, new.content, new.session_id);
        END;
        CREATE TRIGGER IF NOT EXISTS conversations_ad AFTER DELETE ON conversations
        BEGIN
            INSERT INTO conversations_fts(conversations_fts, rowid, content, session_id)
            VALUES ('delete', old.id, old.content, old.session_id);
        END;
        """)

    def new_session(self) -> str:
        return str(uuid.uuid4())

    def add_message(
        self, session_id: str, role: str, content: str, correlation_id: str
    ) -> None:
        self.db.execute(
            """INSERT INTO conversations (session_id, role, content, correlation_id)
               VALUES (?, ?, ?, ?)""",
            (session_id, role, content, correlation_id),
        )
        self.db.commit()

    def get_history(
        self, session_id: str, limit: int = 50
    ) -> list[dict[str, object]]:
        rows = self.db.execute(
            """SELECT role, content, correlation_id, created_at
               FROM conversations
               WHERE session_id = ?
               ORDER BY id DESC LIMIT ?""",
            (session_id, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def search_conversations(self, query: str) -> list[dict[str, object]]:
        rows = self.db.execute(
            """SELECT c.role, c.content, c.correlation_id, c.created_at, c.session_id
               FROM conversations_fts f
               JOIN conversations c ON f.rowid = c.id
               WHERE conversations_fts MATCH ?
               ORDER BY rank LIMIT 20""",
            (query,),
        ).fetchall()
        return [dict(r) for r in rows]

    def clear_session(self, session_id: str) -> None:
        self.db.execute(
            "DELETE FROM conversations WHERE session_id = ?",
            (session_id,),
        )
        self.db.commit()
