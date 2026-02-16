
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

---
