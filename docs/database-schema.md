# Database Schema

SQLite database structure for Jarvis.

## Core Tables

### users
Telegram authorization allowlist.

```sql
CREATE TABLE users (
    telegram_id INTEGER PRIMARY KEY,
    allowed BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### messages
Message audit trail.

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER,
    direction TEXT,
    content TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### user_states
Active interaction states (e.g., OAuth flow, file upload).

```sql
CREATE TABLE user_states (
    telegram_id INTEGER PRIMARY KEY,
    state_type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### responses
Logged AI responses.

```sql
CREATE TABLE responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    telegram_id INTEGER NOT NULL,
    model TEXT,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### opencode_sessions
Mapping between Telegram users and OpenCode sessions.

```sql
CREATE TABLE opencode_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,
    opencode_session_id TEXT NOT NULL UNIQUE,
    session_title TEXT NOT NULL,
    date_key TEXT NOT NULL,
    model_used TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## X Bookmarks Tables

### x_bookmarks
Stored bookmark data from X API.

```sql
CREATE TABLE x_bookmarks (
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
```

### x_sync_status
Tracks sync state.

```sql
CREATE TABLE x_sync_status (
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
```

### x_bookmark_folders
Folder definitions.

```sql
CREATE TABLE x_bookmark_folders (
    folder_id TEXT PRIMARY KEY,
    folder_name TEXT NOT NULL,
    created_at TIMESTAMP
);
```

### x_bookmark_folder_assignments
Many-to-many bookmark-folder relationships.

```sql
CREATE TABLE x_bookmark_folder_assignments (
    tweet_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tweet_id, folder_id),
    FOREIGN KEY (tweet_id) REFERENCES x_bookmarks(tweet_id) ON DELETE CASCADE,
    FOREIGN KEY (folder_id) REFERENCES x_bookmark_folders(folder_id) ON DELETE CASCADE
);
```

### x_oauth_tokens
OAuth 2.0 token storage.

```sql
CREATE TABLE x_oauth_tokens (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    scope TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Feedback Tables

### telegram_turn_feedback
Thumbs up/down feedback on AI responses.

```sql
CREATE TABLE telegram_turn_feedback (
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
```

## Knowledge Base Tables

### kb_documents
Metadata for saved URLs and documents.

```sql
CREATE TABLE kb_documents (
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
```

### kb_chunks
Document chunks for retrieval.

```sql
CREATE TABLE kb_chunks (
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
```

### kb_chunks_fts
FTS5 virtual table for full-text search.

```sql
CREATE VIRTUAL TABLE kb_chunks_fts USING fts5(
    chunk_text,
    heading,
    chunk_id UNINDEXED,
    document_id UNINDEXED
);
```

### kb_ingest_log
Failed ingestion attempts for debugging.

```sql
CREATE TABLE kb_ingest_log (
    id INTEGER PRIMARY KEY,
    markdown_path TEXT NOT NULL,
    error TEXT NOT NULL,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Embedding Tables (Runtime-Created)

### context_embeddings
Tracks embedding status for entries.

```sql
CREATE TABLE context_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_type TEXT NOT NULL,
    entry_id INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entry_type, entry_id)
);
```

### context_vec
Virtual table for sqlite-vec embeddings (created at runtime via `context_vector_store.ensure_vector_schema()`).

```sql
CREATE VIRTUAL TABLE context_vec USING vec0(
    embedding float[1024]
);
```

## Query Examples

### Latest Bookmarks

```sql
SELECT author_username, substr(text, 1, 80) AS preview, created_at
FROM x_bookmarks
ORDER BY created_at DESC
LIMIT 20;
```

### Search by Keyword

```sql
SELECT tweet_id, author_username, substr(text, 1, 100) AS preview
FROM x_bookmarks
WHERE text LIKE '%agent%'
ORDER BY created_at DESC
LIMIT 50;
```

### Top Authors

```sql
SELECT author_username, COUNT(*) AS total
FROM x_bookmarks
GROUP BY author_username
ORDER BY total DESC
LIMIT 20;
```

### Folder Contents

```sql
SELECT b.author_username, substr(b.text, 1, 100) AS preview, b.tweet_url
FROM x_bookmarks b
JOIN x_bookmark_folder_assignments a ON a.tweet_id = b.tweet_id
JOIN x_bookmark_folders f ON f.folder_id = a.folder_id
WHERE f.folder_name = 'Your Folder Name'
ORDER BY b.created_at DESC;
```

### Sync Health Check

```sql
SELECT last_sync_date, total_bookmarks, sync_in_progress
FROM x_sync_status
WHERE id = 1;
```

### Export to CSV

```sql
.headers on
.mode csv
.output bookmarks.csv
SELECT tweet_id, author_username, text, tweet_url, created_at
FROM x_bookmarks
ORDER BY created_at DESC;
```

## Indexes

```sql
-- Response queries
CREATE INDEX idx_responses_telegram_id ON responses(telegram_id);
CREATE INDEX idx_responses_created_at ON responses(created_at);

-- Bookmark queries
CREATE INDEX idx_bookmarks_bookmarked_at ON x_bookmarks(bookmarked_at);
CREATE INDEX idx_bookmarks_created_at ON x_bookmarks(created_at);

-- Folder queries
CREATE INDEX idx_bookmark_folders_tweet_id ON x_bookmark_folder_assignments(tweet_id);
CREATE INDEX idx_bookmark_folders_folder_id ON x_bookmark_folder_assignments(folder_id);

-- Session queries
CREATE INDEX idx_sessions_user_date ON opencode_sessions(telegram_user_id, date_key);
CREATE INDEX idx_sessions_opencode_id ON opencode_sessions(opencode_session_id);

-- Feedback queries
CREATE INDEX idx_turn_feedback_vote_voted_at ON telegram_turn_feedback(vote, voted_at);
CREATE INDEX idx_turn_feedback_created_at ON telegram_turn_feedback(created_at);

-- KB queries
CREATE INDEX idx_kb_documents_url_canonical ON kb_documents(url_canonical);
CREATE INDEX idx_kb_documents_indexed_at ON kb_documents(indexed_at);
CREATE INDEX idx_kb_chunks_document_chunk ON kb_chunks(document_id, chunk_index);

-- Embedding queries
CREATE INDEX idx_context_embeddings_entry ON context_embeddings(entry_type, entry_id);
```
