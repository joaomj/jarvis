"""Raw SQL schema for Jarvis SQLite initialization."""

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
    date_key TEXT NOT NULL,
    model_used TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_date ON opencode_sessions(telegram_user_id, date_key);
CREATE INDEX IF NOT EXISTS idx_sessions_opencode_id ON opencode_sessions(opencode_session_id);

CREATE TABLE IF NOT EXISTS kb_documents (
    id INTEGER PRIMARY KEY,
    markdown_path TEXT UNIQUE NOT NULL,
    url_original TEXT,
    url_canonical TEXT,
    title TEXT,
    domain TEXT,
    captured_at TEXT,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'indexed',
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_kb_documents_url_canonical ON kb_documents(url_canonical);
CREATE INDEX IF NOT EXISTS idx_kb_documents_indexed_at ON kb_documents(indexed_at);

CREATE TABLE IF NOT EXISTS kb_chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    heading TEXT,
    line_start INTEGER NOT NULL,
    line_end INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    UNIQUE(document_id, chunk_index),
    FOREIGN KEY (document_id) REFERENCES kb_documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_document_chunk ON kb_chunks(document_id, chunk_index);

CREATE VIRTUAL TABLE IF NOT EXISTS kb_chunks_fts USING fts5(
    chunk_text,
    heading,
    chunk_id UNINDEXED,
    document_id UNINDEXED
);

CREATE TABLE IF NOT EXISTS kb_ingest_log (
    id INTEGER PRIMARY KEY,
    markdown_path TEXT NOT NULL,
    error TEXT NOT NULL,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS memory_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_key TEXT NOT NULL UNIQUE,
    title TEXT,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL DEFAULT 'fact',
    importance REAL NOT NULL DEFAULT 0.5,
    strength REAL NOT NULL DEFAULT 1.0,
    access_count INTEGER NOT NULL DEFAULT 0,
    is_permanent INTEGER NOT NULL DEFAULT 0,
    last_accessed TIMESTAMP,
    markdown_path TEXT,
    tags_csv TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    forgotten_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_memory_entries_active_created_at
ON memory_entries(active, created_at);

CREATE INDEX IF NOT EXISTS idx_memory_entries_memory_key
ON memory_entries(memory_key);

CREATE TABLE IF NOT EXISTS context_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_type TEXT NOT NULL,
    entry_id INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entry_type, entry_id)
);

CREATE TABLE IF NOT EXISTS context_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    relation TEXT NOT NULL DEFAULT 'related_to',
    strength REAL NOT NULL DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_type, source_id, target_type, target_id)
);

CREATE INDEX IF NOT EXISTS idx_context_embeddings_entry
ON context_embeddings(entry_type, entry_id);

CREATE INDEX IF NOT EXISTS idx_context_links_source
ON context_links(source_type, source_id);

CREATE INDEX IF NOT EXISTS idx_context_links_target
ON context_links(target_type, target_id);
"""
