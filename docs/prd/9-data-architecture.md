
## 9. Data Architecture

### 9.1 Folder Structure

```
data/                                    # Root data directory (Syncthing-synced)
|-- articles/                            # Original extracted content
|   |-- x-2026-01-31-karpathy-llm.md
|   |-- x-2026-01-30-andrej-backprop.md
|   |-- substack-2026-01-31-stratechery.md
|   `-- web-2026-01-31-some-blog.md
|
|-- summaries/                           # Generated summaries
|   |-- x-2026-01-31-karpathy-llm.md
|   `-- substack-2026-01-31-stratechery.md
|
|-- conversations/                       # Chat history (append-only JSONL)
|   |-- 2026-01-31.jsonl
|   |-- 2026-01-30.jsonl
|   `-- .index.json                     # Quick lookup index
|
|-- memories/                            # Future: Agent learnings
|   |-- user-preferences.yaml
|   `-- learned-facts.md
|
|-- voice/                               # Temporary voice files (auto-cleaned)
|   `-- .gitkeep
|
|-- logs/                                # Structured application logs
|   |-- jarvis-2026-01-31.jsonl
|   `-- jarvis-2026-01-30.jsonl
|
`-- config/                              # User configuration
    |-- user.yaml                        # User preferences
    `-- x-cookies.json                   # X authentication (encrypted)
```

### 9.2 Article Markdown Schema

```yaml
# Frontmatter
---
source: x | substack | web
url: https://original-url.com
title: "Article Title"
author: "@username"
author_name: "Full Name"
fetched_at: 2026-01-31T14:30:00Z
correlation_id: abc-123-def
tweet_count: 12                         # X threads only
word_count: 1500
reading_time_minutes: 7
tags: []                                 # Future: auto-generated
---

# Article Title

Original content in markdown format...

## Thread (for X)

### Tweet 1
Content...

### Tweet 2
Content...
```

### 9.3 Conversation JSONL Schema

```json
{
  "id": "msg-uuid-123",
  "timestamp": "2026-01-31T14:30:00Z",
  "correlation_id": "req-abc-123",
  "direction": "incoming|outgoing",
  "type": "text|voice|command|file",
  "command": "/summarize",
  "content": "Message content...",
  "metadata": {
    "telegram_message_id": 12345,
    "telegram_chat_id": 67890,
    "voice_duration_seconds": 15,
    "opencode_session_id": "ses-xyz"
  },
  "private": false
}
```

### 9.4 Log Entry Schema

```json
{
  "timestamp": "2026-01-31T14:30:00.123Z",
  "level": "INFO",
  "correlation_id": "req-abc-123",
  "service": "jarvis.gateway",
  "event": "summarize_complete",
  "data": {
    "url": "https://x.com/...",
    "duration_ms": 2500,
    "tokens_used": 1200,
    "source": "x"
  }
}
```

### 9.5 Database Schema (SQLite)

Jarvis uses SQLite for structured data storage:

```
.jarvis/jarvis.db
├── users                          # Telegram user allowlist
├── messages                       # Message audit log
├── user_states                    # Conversation state machine
├── responses                      # LLM response history
├── x_bookmarks                    # X/Twitter bookmarked posts
├── x_sync_status                  # Bookmark sync metadata
├── x_oauth_tokens                 # X API OAuth 2.0 tokens
├── x_bookmark_folders             # Bookmark folder definitions
└── x_bookmark_folder_assignments  # Junction table (bookmark <-> folder)
```

#### Core Tables

**users** - Telegram user authorization
```sql
CREATE TABLE users (
    telegram_id INTEGER PRIMARY KEY,
    allowed BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**messages** - Message history for audit trail
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER,
    direction TEXT,           -- 'incoming' or 'outgoing'
    content TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**responses** - LLM responses (30-day auto-cleanup)
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

#### X Bookmarks Tables

**x_bookmarks** - Full bookmark data
```sql
CREATE TABLE x_bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id TEXT UNIQUE NOT NULL,
    author_username TEXT NOT NULL,
    author_name TEXT,
    author_verified BOOLEAN DEFAULT 0,
    text TEXT NOT NULL,
    note_text TEXT,           -- User's private note
    created_at TIMESTAMP,     -- Tweet creation time
    bookmarked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Sync time (not actual bookmark time)
    tweet_url TEXT NOT NULL,
    like_count INTEGER DEFAULT 0,
    retweet_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    impression_count INTEGER DEFAULT 0,
    bookmark_count INTEGER DEFAULT 0,
    media_urls TEXT,          -- JSON array
    urls_expanded TEXT,       -- JSON array
    context_annotations TEXT, -- JSON array (X API topic classification)
    raw_json TEXT,            -- Full API response
    last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**x_sync_status** - Sync state tracking (single row, id=1)
```sql
CREATE TABLE x_sync_status (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_sync_date TEXT,
    last_sync_at TIMESTAMP,
    last_tweet_id TEXT,       -- For incremental sync
    total_bookmarks INTEGER DEFAULT 0,
    sync_in_progress BOOLEAN DEFAULT 0,
    first_sync_complete BOOLEAN DEFAULT 0
);
```

**x_oauth_tokens** - OAuth 2.0 credentials (single row, id=1)
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

#### Bookmark Folders (New)

**x_bookmark_folders** - Folder definitions from X API
```sql
CREATE TABLE x_bookmark_folders (
    folder_id TEXT PRIMARY KEY,    -- X API folder ID
    folder_name TEXT NOT NULL,      -- Human-readable name
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**x_bookmark_folder_assignments** - Many-to-many junction
```sql
CREATE TABLE x_bookmark_folder_assignments (
    tweet_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tweet_id, folder_id),
    FOREIGN KEY (tweet_id) REFERENCES x_bookmarks(tweet_id) ON DELETE CASCADE,
    FOREIGN KEY (folder_id) REFERENCES x_bookmark_folders(folder_id) ON DELETE CASCADE
);

CREATE INDEX idx_bookmark_folders_tweet_id ON x_bookmark_folder_assignments(tweet_id);
CREATE INDEX idx_bookmark_folders_folder_id ON x_bookmark_folder_assignments(folder_id);
```

**Design Rationale:**
- Junction table enables bookmarks to exist in multiple folders (e.g., "Context retrieval" + uncategorized)
- CASCADE delete maintains referential integrity
- Separate folder fetching from bookmark data fetching due to X API limitations
- Folder endpoint only returns tweet IDs; cross-referenced with full data from main bookmarks endpoint

---
