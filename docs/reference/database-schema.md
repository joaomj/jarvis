# Database Schema

SQLite database structure for Jarvis.

## Core Tables

### users
Telegram authorization allowlist.

```sql
CREATE TABLE users (
    telegram_user_id INTEGER PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### messages
Message audit trail.

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,
    direction TEXT NOT NULL,  -- 'inbound' | 'outbound'
    content TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### responses
Logged AI responses.

```sql
CREATE TABLE responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    model TEXT NOT NULL,
    content TEXT NOT NULL,
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
    author_username TEXT,
    author_name TEXT,
    author_verified BOOLEAN,
    text TEXT NOT NULL,
    created_at TIMESTAMP,
    bookmarked_at TIMESTAMP,
    tweet_url TEXT NOT NULL,
    like_count INTEGER,
    retweet_count INTEGER,
    reply_count INTEGER,
    impression_count INTEGER,
    bookmark_count INTEGER,
    media_urls TEXT,
    urls_expanded TEXT,
    context_annotations TEXT,
    raw_json TEXT,
    last_synced_at TIMESTAMP
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
    total_bookmarks INTEGER,
    sync_in_progress BOOLEAN,
    first_sync_complete BOOLEAN
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
    assigned_at TIMESTAMP,
    PRIMARY KEY (tweet_id, folder_id),
    FOREIGN KEY (tweet_id) REFERENCES x_bookmarks(tweet_id),
    FOREIGN KEY (folder_id) REFERENCES x_bookmark_folders(folder_id)
);
```

## Knowledge Base Tables

### kb_documents
Metadata for saved URLs and documents.

```sql
CREATE TABLE kb_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_canonical TEXT UNIQUE,
    title TEXT,
    markdown_path TEXT UNIQUE NOT NULL,
    content_hash TEXT,
    indexed_at TIMESTAMP
);
```

### kb_chunks
Document chunks for retrieval.

```sql
CREATE TABLE kb_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    heading TEXT,
    UNIQUE(document_id, chunk_index)
);
```

### kb_chunks_fts
FTS5 virtual table for full-text search.

```sql
CREATE VIRTUAL TABLE kb_chunks_fts USING fts5(
    chunk_text,
    heading,
    content=kb_chunks,
    content_rowid=id
);
```

## Memory Tables

### memory_entries
Curated memories and facts.

```sql
CREATE TABLE memory_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    category TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
```

### context_embeddings
Vector embeddings metadata.

```sql
CREATE TABLE context_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    entry_type TEXT NOT NULL,
    embedding_model TEXT,
    created_at TIMESTAMP
);
```

### context_vec
Virtual table for sqlite-vec (created at runtime).

### context_links
Knowledge graph edges.

```sql
CREATE TABLE context_links (
    source_id INTEGER,
    target_id INTEGER,
    relation TEXT,
    weight REAL DEFAULT 1.0,
    created_at TIMESTAMP,
    PRIMARY KEY (source_id, target_id, relation)
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
-- Bookmark queries
CREATE INDEX idx_bookmarks_bookmarked_at ON x_bookmarks(bookmarked_at);
CREATE INDEX idx_bookmarks_created_at ON x_bookmarks(created_at);

-- Folder queries
CREATE INDEX idx_bookmark_folders_tweet_id ON x_bookmark_folder_assignments(tweet_id);
CREATE INDEX idx_bookmark_folders_folder_id ON x_bookmark_folder_assignments(folder_id);

-- KB queries
CREATE INDEX idx_kb_documents_url ON kb_documents(url_canonical);
CREATE INDEX idx_kb_documents_indexed ON kb_documents(indexed_at);
CREATE INDEX idx_kb_chunks_document ON kb_chunks(document_id, chunk_index);
```
