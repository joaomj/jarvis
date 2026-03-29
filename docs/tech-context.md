# Technical Context

> Source of truth for Jarvis architecture and decisions.
> Update this when architecture changes.

## Project Brief

Jarvis is a **personal AI assistant accessible via Telegram** that bridges mobile chat with OpenCode Server.

**Core Requirements:**
- Chat with OpenCode AI via Telegram from mobile phone
- Natural language interface for AI coding tasks and personal data queries
- No public network exposure (polling mode)
- Single-user security model
- Automatic data synchronization (X bookmarks)

**Goals:**
- Mobile access to OpenCode without TUI
- Quick queries to personal data
- Security and privacy
- Minimal infrastructure

## Architecture Overview

### Medallion Data Architecture

```
vault/
├── raw/                              # Bronze layer (source data, immutable)
│   ├── opencode/opencode.db          # OpenCode sessions/messages (via XDG_DATA_HOME)
│   ├── bookmarks/                    # X bookmark markdown artifacts
│   ├── url-saves/                    # Firecrawl-scraped URLs
│   └── attachments/                  # Telegram attachments
│
└── index/                            # Silver layer (processed indexes)
    ├── jarvis.db                     # FTS5 + sqlite-vec + kb_documents + kb_chunks
    ├── favorite_models.json          # User model preferences
    ├── opencode-state/               # OpenCode server state
    └── opencode-logs/                # OpenCode server logs
```

### Why Telegram + OpenCode Bridge?

1. **Mobile access**: Telegram available everywhere
2. **No public URLs**: Polling eliminates webhook complexity
3. **Thin bridge**: All AI intelligence in OpenCode
4. **Security**: Allowlist-based auth
5. **Simplicity**: Single container deployment

### Why Polling Over Webhook?

| Criterion | Webhook | Polling |
|-----------|---------|---------|
| Complexity | Public URL needed | Runs locally |
| Latency | Immediate | ~1-2s acceptable |
| Cost | VPS $10+/mo | Existing hardware |

### Core Pattern

Files are the source of truth; databases are derived indexes.
OpenCode sessions are the memory -- no separate curated memory store.

**Source of truth:** `vault/raw/`
- OpenCode conversation history (auto-managed)
- X bookmark markdown artifacts
- Saved URLs and attachments

**Derived index:** `vault/index/jarvis.db`
- FTS5 for keyword search
- sqlite-vec for semantic embeddings
- RRF fusion ranking

## System Patterns

### Data Flows

**Regular Chat (with auto-retrieval):**
```
Telegram Message → Auth Check → Hybrid Search (KB + OpenCode history)
    → Inject context as system prefix → OpenCode Session → SSE Events → Telegram Response
```

**X Bookmarks:**
```
Daily Trigger → X API → SQLite Storage → Markdown Artifacts → KB Index
```

**URL Save:**
```
/save <url> → Firecrawl Scrape → vault/raw/url-saves/ → KB Index → Embeddings
```

### Key Design Decisions

**OpenCode is the memory:** Every Jarvis conversation is an OpenCode session.
Conversation history lives in OpenCode's SQLite DB at `vault/raw/opencode/`.
No separate curated memory store needed.

**Auto-retrieval on every message:** Hybrid search (FTS5 BM25 + sqlite-vec semantic + RRF fusion)
runs against KB content AND OpenCode conversation history. Results injected as system prefix
into `prompt_async`.

**Command discoverability:** Commands fetched from OpenCode's `GET /command` API
and registered in Telegram's native command menu via `set_my_commands` on startup.

**Interaction Guard:** Question/permission flows are stateful and block unrelated user text.

**Session Management:** New session created on every bot restart for clean state.

**Retrieval Strategy:** BM25-first lexical search with semantic fallback via sqlite-vec.

## Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Package Manager | PDM |
| Telegram | python-telegram-bot 21+ |
| HTTP Client | httpx |
| Config | pydantic-settings |
| Logging | structlog |
| Database | SQLite + sqlite-vec |
| Embeddings | BAAI/bge-m3 (local, 1024-dim) |
| Container | Docker |

## Detailed Documentation

- [Configuration](reference/configuration.md) - Environment variables and settings
- [Deployment](reference/deployment.md) - Production and development setup
- [Database Schema](reference/database-schema.md) - SQLite table definitions
- [Commands](reference/commands.md) - All available commands
- [Security](reference/security.md) - Security model and practices
- [Performance](reference/performance.md) - Performance characteristics
- [Roadmap](ROADMAP.md) - Implementation phases and priorities

## External References

- [OpenCode Server API](https://opencode.ai/docs/server)
- [OpenCode Commands](https://opencode.ai/docs/commands/)
