# Technical Context

> Source of truth for Jarvis architecture, decisions, and engineering detail.
> Update this when the system changes.

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

## Architecture

### Core Pattern

Files are the source of truth; databases are derived indexes.
OpenCode sessions are the memory -- no separate curated memory store.

### Medallion Data Architecture

```
vault/
  raw/                              Bronze layer (source data, immutable)
    opencode/opencode.db            OpenCode sessions/messages (via XDG_DATA_HOME)
    bookmarks/                      X bookmark markdown artifacts
    url-saves/                      Firecrawl-scraped URLs
    attachments/                    Telegram attachments

  index/                            Silver layer (processed indexes)
    jarvis.db                       FTS5 + sqlite-vec + kb_documents + kb_chunks
    favorite_models.json            User model preferences
    opencode-state/                 OpenCode server state
    opencode-logs/                  OpenCode server logs
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

## State Machines

### Message Processing (per Telegram update)

```
                          Telegram Update
                               |
                     +---------+---------+
                     |                   |
                 callback_query      message
                     |                   |
                [permission?]      +-----+------+
                yes/    \no        |            |
                  |      |    attachment?    has text?
         handle_perm  handle   only?          |
         callback    feedback    |         +--+--+
                     callback   reply +---+  process
                     (thumbs)   path  |  input
                                     no  |
                                         |
                               +----is private?----+
                               |                   |
                            strip             skip retrieval
                            marker             log message
                               |                   |
                               +--------+----------+
                                        |
                                   is URL only?
                                   yes/     \no
                                 hint save    |
                                              |
                                    interaction guard
                                    active?       |
                                    yes/    \no   |
                                    block/   |    |
                                    answer   |    |
                                             |    |
                                    starts with / or !?
                                    yes/           \no
                                      |           regular
                                    command      message
                                    route          |
                                      |      +-----+------+
                                   blocked?  has pending   is private?
                                   yes/ \no  prompt?      |
                                   reject  |  yes/ \no    skip
                                           |  wait  |    retrieval
                                           |        |
                                           +---+----+
                                               |
                                     AUTO-RETRIEVAL (if not private)
                                               |
                                    retrieve_context(context_store, opencode_db, text)
                                               |
                                    +----------+-----------+
                                    |                      |
                              KB hybrid search      OpenCode session
                              (FTS5 + sqlite-vec)   history SQL search
                                    |                      |
                                    +-------- RRF --------+
                                               |
                                         system_prefix
                                               |
                                    prompt_async(session_id, text, system=prefix)
                                               |
                                    register_pending_prompt(...)
                                               |
                                    "Working on it..." ack
```

### Event Processing (background SSE loop)

```
  EventProcessor runs a background task that reconnects on failure:

  +--> stream_events() from OpenCode SSE endpoint
  |         |
  |    event received?
  |    no/        \yes
  |    sleep      |
  |    1.5s       +------type?------+
  |    (retry)    |         |        |
  |          question    permission  message
  |          .asked      .asked    .updated
  |              |          |         |
  |         on_question  on_perm   extract session_id
  |         _asked       _asked       |
  |              |          |    +----+------+
  |         show prompt  show     |           |
  |         block input  buttons  not      assistant
  |         until /answer  allow/ pending? completed?
  |         or /cancel   reject  |           |
  |              |          |    skip     _send_completed
  |              |          |             response()
  |              |          |                |
  +--------------+----------+----------------+
                           (loop continues)

  Side effects on completion:
    - pop pending prompt
    - send response to Telegram chat
    - log turn to feedback table (unless private)
    - trigger _on_save_completed if kind=="save"
    - update pinned status (model, agent, tokens)
```

### Session Lifecycle

```
  Bot Start
      |
  initialize()
      |
  health_check(OpenCode)
      |
  SessionManager created
      |
  First message from user
      |
  get_or_create_session(user_id)
      |
  cached? --yes--> return session_id
      |
  no: create_session(title="jarvis-user-{uid}-{timestamp}")
      |
  cache in memory + store in DB
      |
  return (session_id, is_new=True)
      |
  /new command --> extract new session_id from response
                     set_session(user_id, new_id)
      |
  Bot restart --> fresh in-memory cache
                   new session created on first message
```

### Interaction Guard (question/permission blocking)

```
  State per user:  IDLE | QUESTION_PENDING | PERMISSION_PENDING

  IDLE ──question.asked──> QUESTION_PENDING
  IDLE ──permission.asked──> PERMISSION_PENDING

  QUESTION_PENDING:
    /answer ...  ──> question_reply(request_id, answers) ──> IDLE
    /cancel      ──> question_reject(request_id)           ──> IDLE
    /help,/status,/stop  ──> pass through (allowed)
    any other text  ──> "Question pending. Use /answer ... or /cancel."

  PERMISSION_PENDING:
    callback perm:{id}:once   ──> permission_reply(id, "once")    ──> IDLE
    callback perm:{id}:always ──> permission_reply(id, "always")  ──> IDLE
    callback perm:{id}:reject ──> permission_reply(id, "reject")  ──> IDLE
    /help,/status,/stop       ──> pass through (allowed)
    any other text            ──> "A permission request is pending. Use the buttons."
```

### Polling Engine (backoff state)

```
  +--> getUpdates(offset, timeout=30s)
  |         |
  |    updates?
  |    yes/     \no
  |    process   sleep(interval)
  |    each      |
  |    update    |
  |    offset++  |
  |         |    |
  |    reset backoff=1
  |         |    |
  |         +----+
  |              |
  |    exception?
  |         |
  |    delay = min(2^backoff, 60s)
  |    backoff = min(backoff+1, 6)
  |    sleep(delay)
  |         |
  +---------+ (loop)

  Exponential backoff: 2s, 4s, 8s, 16s, 32s, 60s (capped)
```

### Auto-Retrieval Pipeline (per non-private message)

```
  User text
      |
  +---+---+
  |       |
  KB      OpenCode
  hybrid  session
  search  history
  |       |
  |       +-- SQL LIKE on part.data in opencode.db (read-only)
  |          joins: part -> message -> session
  |          returns (snippet, session_title) pairs
  |
  +-- ContextStore.search(query, limit=6)
       |
       +-- FTS5 lexical candidates (build_fts_query -> OR-joined tokens)
       +-- sqlite-vec semantic candidates (embed_text -> cosine neighbors)
       |
       +-- RRF fusion: score += 1/(60 + rank) for each list
       |
       +-- hydrate top results -> ContextResult(snippet, source, score)
       +-- deduplicate by normalized text prefix
       +-- cap at 2000 chars total
       |
       returns system_prefix string (or empty if no results)
```

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

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| UI layer | Telegram | Mobile-first, no public ports, polling mode |
| Memory | OpenCode sessions DB (read-only) | No separate curated memory store; OpenCode is the memory |
| Auto-retrieval | Every message | Hybrid search runs automatically; no explicit /recall needed |
| Retrieval method | Hybrid (FTS5 + sqlite-vec + RRF fusion) | BM25 + semantic, fused via Reciprocal Rank Fusion |
| Source priority | Attached > vault/ > reputable web > general web | Most specific context first |
| Command routing | OpenCode `GET /command` + Telegram `set_my_commands` | No custom help command; commands appear natively in Telegram menu |
| Architecture | Medallion (bronze + silver) | Raw data in vault/raw/, processed indexes in vault/index/ |
| PDF extraction | LLM-based via OpenCode | Avoid fragile traditional PDF parsers |
| Container | Non-root, read-only /app, no new privileges | Defense in depth |
| Polling vs webhooks | Polling | No public URLs, runs locally, ~1-2s latency acceptable |

## Embedding Strategy

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Model | BAAI/bge-m3 | Multilingual, strong dense retrieval, runs locally on M4 |
| Dimensions | 1024 | Standard for BGE-M3 dense mode |
| Chunk size | 1800 chars | Fits within BGE-M3's 8192 token context |
| Overlap | ~200 chars (10-15%) | Handles cross-boundary topics |
| Normalization | title + heading + chunk_text (truncated 2000 chars) | Includes structural context |
| Distance | Cosine | Standard for normalized dense vectors |
| Storage | sqlite-vec (local, embedded) | No external dependencies |

## Configuration

All settings via environment variables, validated by pydantic-settings (`config.py`).

### Required

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_ID` | Telegram bot token from @BotFather |
| `TELEGRAM_USER_ID` | Authorized Telegram user ID |
| `OPENCODE_URL` | OpenCode Server URL (default: `http://localhost:4096`) |
| `OPENCODE_SERVER_PASSWORD` | OpenCode Server password |

### Optional (with defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_POLLING_INTERVAL` | `1.0` | Seconds between polls (min 0.5) |
| `TELEGRAM_POLLING_TIMEOUT` | `30` | getUpdates timeout (10-120s) |
| `DATABASE_PATH` | `vault/index/jarvis.db` | SQLite database path |
| `ENABLE_MESSAGE_AUDIT` | `true` | Message audit trail |
| `FAVORITE_MODELS_PATH` | `vault/index/favorite_models.json` | Model preferences file |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `VAULT_ROOT` | `vault` | Root directory for vault artifacts |
| `X_CLIENT_ID` | None | X OAuth 2.0 Client ID (bookmarks disabled if absent) |
| `X_CLIENT_SECRET` | None | X OAuth 2.0 Client Secret |
| `KB_CONTENT_DIR` | `vault/raw/url-saves` | Saved markdown content directory |
| `KB_MAX_CHUNKS_PER_QUERY` | `6` | Max retrieved chunks per query |
| `KB_CHUNK_SIZE_CHARS` | `1800` | Max chunk size for indexing |
| `POLLING_MAX_BACKOFF_SECONDS` | `60` | Backoff delay cap |

### Favorite Models

Create `vault/index/favorite_models.json`:
```json
[
  "openai/gpt-5.2",
  "zai/glm-4.7",
  "openai/gpt-5.3-codex"
]
```
First model is default for new sessions.

## Security Model

| Layer | Method | Implementation |
|-------|--------|----------------|
| Authentication | Telegram user ID allowlist | `database/users.py::is_user_allowed()` |
| Network | Polling only, no public ports | `polling_engine.py` -- outbound only |
| Secrets | Split `.env` files per service | `.env` (Telegram/X) + `.env.opencode` (LLM keys) |
| Logging | Structured JSON, secrets filtered | `logging_config.py` -- httpx INFO suppressed |
| Container | Non-root, read-only, no-new-privileges, cap_drop ALL | Docker multi-stage build + compose |
| Database | SQLite file, gitignored, parameterized queries | `vault/index/jarvis.db` |
| X OAuth | OAuth 2.0 PKCE, tokens in DB (not .env) | Callback on localhost only |
| Supply chain | OpenCode image pinned by digest | Tag + SHA256 in docker-compose.yml |
| Network isolation | Bridge network, no ports exposed | `jarvis-net` -- opencode only reachable by jarvis |

## Performance

| Metric | Target | Notes |
|--------|--------|-------|
| Polling latency | ~1-2s | Includes Telegram network |
| Bookmark queries | <100ms for 1K bookmarks | Indexed queries |
| Vault search (hybrid) | <200ms | FTS5 + sqlite-vec + RRF |
| X sync (incremental) | 0-1 API calls | Daily, rate-limited |
| X sync (full) | 10-30s for 100-500 bookmarks | Weekly reconcile |
| Auto-cleanup | Responses: 30 days | Bookmarks kept indefinitely |

## Commands

### Local Commands (handled by Jarvis)

| Command | Description |
|---------|-------------|
| `/models` | Show and select favorite models |
| `/new [title]` | Create new session |
| `/sessions` | List your sessions |
| `/model <provider/model>` | Set model directly |
| `/save <url>` | Save URL to vault for later retrieval |

### OpenCode Commands (forwarded)

All non-blocked commands are forwarded to OpenCode Server via `!` prefix (e.g., `!compact`, `!undo`, `!share`).

### Blocked Commands (TUI-only)

`/exit`, `/quit`, `/q`, `/editor`, `/themes`, `/theme` -- blocked because they require the TUI interface.

### Auto-Retrieval

Every non-private message automatically gets relevant context injected:
- KB content (bookmarks, saved URLs, attachments)
- OpenCode conversation history
- No explicit `/recall` needed

### Private Mode

Prefix any message with `private:` or `/private ` to skip logging and retrieval.

## Deployment

### Docker Compose (Production)

Two containers on a shared bridge network, health-gated startup.

```
docker compose up -d    # starts opencode, waits for healthy, then starts jarvis
```

| Service | Image | Port | Notes |
|---------|-------|------|-------|
| opencode | `ghcr.io/anomalyco/opencode` (pinned digest) | 4096 (internal only) | Health: TCP check on 4096 |
| jarvis | Built from `Dockerfile` (Alpine + PDM) | None (outbound polling) | Depends on opencode healthy |

**Network:** `jarvis-net` (bridge, not internal -- both need outbound). No `ports:` on opencode -- only reachable via Docker DNS.

**Bind mount:** `.:/app/project` on both services. Vault paths (`vault/raw/`, `vault/index/`) resolve via `WORKDIR /app/project` + config.py defaults.

**Secrets split:**
- `.env` -- Telegram bot token, user ID, X OAuth, Jarvis settings
- `.env.opencode` -- LLM provider API keys, server password, log level

**Security hardening:**
- Both containers: `no-new-privileges:true`, `cap_drop: ALL`
- Jarvis: `read_only: true`, tmpfs for `/tmp`
- OpenCode image pinned by tag + SHA256 digest

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| WORKDIR | `/app/project` | config.py defaults (`vault/index/jarvis.db`, etc.) resolve relative to CWD |
| Bind mount | `.:/app/project` (single) | Covers vault, `.opencode/`, and source code |
| OpenCode healthcheck | TCP probe via `/dev/tcp` | Image may lack wget/curl; Jarvis does real HTTP check |
| init: true | On opencode service | Proper PID 1 signal handling (zombie reaping) |

## Observability

- Structured JSON logs to stdout/stderr (structlog)
- Correlation IDs passed through all requests
- Key metrics logged: `polling_latency`, `query_execution_time`, `vault_query`, `sync_duration`
- Secret patterns filtered before output
- httpx INFO logs suppressed (exposes tokens)

## External References

- [OpenCode Server API](https://opencode.ai/docs/server)
- [OpenCode Commands](https://opencode.ai/docs/commands/)
- [Database Schema](database-schema.md)
- [Roadmap](roadmap.md)
