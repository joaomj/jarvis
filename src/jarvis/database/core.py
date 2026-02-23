"""Core database functionality - connection and schema initialization."""

import sqlite3
from pathlib import Path

from jarvis.logging_config import get_logger

logger = get_logger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    allowed BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER,
    direction TEXT,
    content TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_states (
    telegram_id INTEGER PRIMARY KEY,
    state_type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    telegram_id INTEGER NOT NULL,
    model TEXT,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_responses_telegram_id ON responses(telegram_id);
CREATE INDEX IF NOT EXISTS idx_responses_created_at ON responses(created_at);

CREATE TABLE IF NOT EXISTS x_bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id TEXT UNIQUE NOT NULL,
    author_username TEXT NOT NULL,
    author_name TEXT,
    author_verified BOOLEAN DEFAULT 0,
    text TEXT NOT NULL,
    note_text TEXT,
    created_at TIMESTAMP,
    bookmarked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tweet_url TEXT NOT NULL,
    like_count INTEGER DEFAULT 0,
    retweet_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    impression_count INTEGER DEFAULT 0,
    bookmark_count INTEGER DEFAULT 0,
    media_urls TEXT,
    urls_expanded TEXT,
    context_annotations TEXT,
    raw_json TEXT,
    last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS x_sync_status (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_sync_date TEXT,
    last_sync_at TIMESTAMP,
    last_tweet_id TEXT,
    last_full_sync_date TEXT,
    last_folders_sync_date TEXT,
    total_bookmarks INTEGER DEFAULT 0,
    sync_in_progress BOOLEAN DEFAULT 0,
    first_sync_complete BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS x_oauth_tokens (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    scope TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bookmarks_bookmarked_at ON x_bookmarks(bookmarked_at);
CREATE INDEX IF NOT EXISTS idx_bookmarks_created_at ON x_bookmarks(created_at);

CREATE TABLE IF NOT EXISTS x_bookmark_folders (
    folder_id TEXT PRIMARY KEY,
    folder_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS x_bookmark_folder_assignments (
    tweet_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tweet_id, folder_id),
    FOREIGN KEY (tweet_id) REFERENCES x_bookmarks(tweet_id) ON DELETE CASCADE,
    FOREIGN KEY (folder_id) REFERENCES x_bookmark_folders(folder_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bookmark_folders_tweet_id ON x_bookmark_folder_assignments(tweet_id);
CREATE INDEX IF NOT EXISTS idx_bookmark_folders_folder_id ON x_bookmark_folder_assignments(folder_id);

CREATE TABLE IF NOT EXISTS telegram_turn_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,
    telegram_chat_id INTEGER NOT NULL,
    telegram_in_message_id INTEGER,
    telegram_out_message_id INTEGER,
    source TEXT NOT NULL,
    opencode_session_id TEXT,
    model_full TEXT,
    agent TEXT,
    prompt_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    vote INTEGER,
    voted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_turn_feedback_vote_voted_at ON telegram_turn_feedback(vote, voted_at);
CREATE INDEX IF NOT EXISTS idx_turn_feedback_created_at ON telegram_turn_feedback(created_at);

INSERT OR IGNORE INTO x_sync_status (id) VALUES (1);

CREATE TABLE IF NOT EXISTS opencode_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,
    opencode_session_id TEXT NOT NULL UNIQUE,
    session_title TEXT NOT NULL,
    date_key TEXT NOT NULL,  -- YYYY-MM-DD for daily rotation
    model_used TEXT,          -- Last model used (for debugging/auditing)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_date ON opencode_sessions(telegram_user_id, date_key);
CREATE INDEX IF NOT EXISTS idx_sessions_opencode_id ON opencode_sessions(opencode_session_id);
"""


class DatabaseCore:
    """Core database connection and schema management."""

    db_path: Path
    _message_content_max_length: int
    _response_cleanup_days: int

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)
            self._migrate_sync_status_columns(conn)

    def _migrate_sync_status_columns(self, conn: sqlite3.Connection) -> None:
        """Backfill newer x_sync_status columns for existing databases."""
        cursor = conn.execute("PRAGMA table_info(x_sync_status)")
        column_names = {row[1] for row in cursor.fetchall()}

        if "last_full_sync_date" not in column_names:
            conn.execute("ALTER TABLE x_sync_status ADD COLUMN last_full_sync_date TEXT")

        if "last_folders_sync_date" not in column_names:
            conn.execute("ALTER TABLE x_sync_status ADD COLUMN last_folders_sync_date TEXT")

    def _execute(
        self,
        query: str,
        params: tuple = (),
        *,
        fetch: bool = False,
    ) -> list | None:
        """Execute a query with error handling.

        Args:
            query: SQL query.
            params: Query parameters.
            fetch: Whether to fetch and return results.

        Returns:
            List of rows if fetch=True, None otherwise.
        """
        with sqlite3.connect(self.db_path) as conn:
            if fetch:
                cursor = conn.execute(query, params)
                return cursor.fetchall()
            conn.execute(query, params)
            return None

    def _execute_dict(
        self,
        query: str,
        params: tuple = (),
    ) -> list[dict]:
        """Execute a query and return results as list of dicts.

        Args:
            query: SQL query.
            params: Query parameters.

        Returns:
            List of dictionaries with column names as keys.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
