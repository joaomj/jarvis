# Technical Context

> Source of truth for Jarvis architecture and decisions.
> Update this when architecture changes.

## Project Brief

Jarvis is a **personal AI assistant accessible via Telegram** that bridges mobile chat with OpenCode Server. It enables natural language interaction with an AI coding assistant from anywhere, with additional capabilities like X (Twitter) bookmarks querying.

**Core Requirements:**
- Chat with OpenCode AI via Telegram from mobile phone
- Natural language interface for both AI coding tasks and personal data queries
- No public network exposure (polling mode, runs entirely locally)
- Single-user security model (allowlist-based authorization)
- Automatic data synchronization for external services (X bookmarks)

**Goals:**
- Provide mobile access to OpenCode without TUI interface
- Enable quick queries to personal data (bookmarks, etc.)
- Maintain security and privacy (no public endpoints)
- Minimal infrastructure requirements (single Docker container)

---

## Product Context

### Why Jarvis Exists

**Problem**: OpenCode is a powerful AI coding assistant, but requires a terminal/TUI interface. Mobile users cannot easily access it while on the go.

**Solution**: Jarvis acts as a lightweight Telegram bot that forwards messages to OpenCode Server. Users can chat from their phone, get responses, and access OpenCode's full capabilities (file ops, git, bash commands) via natural language.

**Additional Problem**: Users accumulate X bookmarks but have no easy way to query them naturally.

**Additional Solution**: Jarvis syncs X bookmarks daily and enables natural language queries like "What did I save last week?" directly from Telegram.

### How It Should Work

**Regular Chat Flow:**
1. User types message in Telegram (e.g., "Explain the bug in src/auth.py")
2. Jarvis receives via polling, checks authorization
3. Jarvis sends async prompt to OpenCode (`/session/{id}/prompt_async`)
4. Jarvis subscribes to OpenCode SSE events (`/event`) and tracks session progress
5. On assistant completion event, Jarvis fetches latest assistant message parts
6. Jarvis formats for Telegram (chunking, markdown escaping) and sends response
7. User sees response on phone while bot remains responsive for callbacks

**X Bookmarks Flow:**
1. First message of the day triggers auto-sync
2. Jarvis fetches new bookmarks from X API (daily incremental), with weekly full reconciliation
3. Bookmarks stored in local SQLite database
4. User queries via natural language (e.g., "Show me my recent bookmarks")
5. Jarvis detects bookmark query, searches local DB
6. Results returned as formatted summaries with details option

### User Experience Goals

- **Fast responses**: < 2 seconds for most queries (polling overhead acceptable)
- **Natural language**: No commands to memorize, just ask naturally
- **Context-aware**: Remembers session context across messages
- **Secure**: No public exposure, single user, secrets never logged
- **Reliable**: Graceful error handling with user-friendly messages

### Constraints

- **Latency**: Polling adds ~1-2 second delay to first message of batch
- **Interpretability**: Errors must be clear, with actionable next steps
- **Resources**: Single Mac Mini M4 (16GB) deployment
- **Privacy**: No data leaves local network (except OpenCode API calls)
- **Availability**: Single-user system, no multi-tenant requirements

---

## System Patterns

### Architecture Rationale

**Why Telegram + OpenCode Bridge?**

Chosen because:
1. **Mobile access**: Telegram available everywhere, reliable notifications
2. **No public URLs**: Polling mode eliminates webhook/Tailscale complexity
3. **Minimal interpretation**: Jarvis is thin passthrough, all AI intelligence in OpenCode
4. **Security**: Allowlist-based auth, no OAuth flows needed
5. **Simplicity**: Single container deployment, easy maintenance

**Why Polling Over Webhook?**

| Criterion | Webhook | Polling (Chosen) |
|-----------|----------|------------------|
| Complexity | Needs public URL + Tailscale | Runs entirely locally |
| Latency | Immediate | ~1-2s delay acceptable |
| Reliability | Depends on internet stability | Handles network issues gracefully |
| Setup | Complex infrastructure | Simple, works offline after initial sync |
| Cost | VPS needed ($10/mo+) | Runs on existing Mac Mini |

**Tradeoff**: Accept 1-2 second delay for simpler setup and no infrastructure costs. For personal use, this is acceptable.

**Why Modular Architecture?**

Chosen because:
1. **Testability**: Each module can be tested independently
2. **Maintainability**: Clear separation of concerns, easier to debug
3. **Extensibility**: New commands/features added to handlers package
4. **Readability**: Files under 300 lines (pre-commit enforced)

**Tradeoff**: Slightly more files than monolithic bot.py, but significantly better organization.

**When to Reconsider:**
- Team grows to 5+ developers (might justify microservices)
- Need to support multiple concurrent users (current architecture scales to ~100)
- Latency becomes critical (might need webhook for sub-second response)

### Data Flow: Regular OpenCode Chat

```
User Message (Telegram)
    ↓
[Authorization Check] - SQLite allowlist lookup
    ↓ (authorized)
[First Message After Restart?]
    ├─ Yes → [Create New Session] - Unique timestamp in title
    │         ↓
    │       [Send Health Probe] - Test message "What day is today?"
    │         ├─ Uses default model (first in favorite_models.json)
    │         └─ Reports model, agent, session info to user
    │         ↓
    │       [Return Early] - Wait for user's next message
    └─ No → [Use Existing Session] - Cached in memory
    ↓
[Detect Command Type] - /command vs regular text
    ↓
[Forward to OpenCode Server]
    ├─ /command → POST /session/{id}/command
    └─ text      → POST /session/{id}/prompt_async
    ↓
[OpenCode Processing]
    ├─ LLM inference
    ├─ File operations (read/write)
    ├─ Git operations
    └─ Bash commands
    ↓
[OpenCode Event Stream] - `message.updated`, `session.diff`, `question.asked`, `permission.asked`
    ↓
[Assistant Completion Detected]
    └─ Jarvis fetches `/session/{id}/message?limit=30` for final assistant parts
    ↓
[Format for Telegram]
    ├─ Markdown escaping
    ├─ Chunking (max 4096 chars)
    └─ Error formatting
    ↓
[Send to User] - Via Telegram API
    ↓
[Log Response] - SQLite (session_id, user_id, model, text)
```

**Interaction Guard:**
- **HOW**: Question/permission flows are stateful and block unrelated user text
- **WHY**: Prevents mixed inputs while the agent is waiting for explicit answers/approval
- **WHAT**: Allowed during active flow: `/help`, `/status`, `/stop`; everything else is blocked or redirected
- **WHERE**: `interaction_manager.py` + `event_processor.py`

**Pinned Status Message:**
- **HOW**: Maintain and update one pinned Telegram message with debounced edits
- **WHY**: Always-visible operational state from mobile
- **WHAT**: Session title, model, agent, approximate context tokens, changed files list
- **WHERE**: `pinned_status.py` + event updates from `session.diff` and `message.updated`

**Session Management:**
- **HOW**: New session created on every bot restart (not just daily)
- **WHY**: Ensures clean state, prevents stale model carryover, predictable behavior
- **WHAT**: Session title includes timestamp: `jarvis-user-{user_id}-{YYYY-MM-DD-HHMMSS}`
- **WHERE**: Session stored in SQLite for audit, cached in memory for fast access

**Startup Health Probe:**
- **HOW**: First message after bot restart triggers test message
- **WHY**: Validates system is working before user starts real work
- **WHAT**: Sends "What day is today?" with default model, reports status to user
- **WHERE**: `bot.py::_send_daily_health_probe()`

**Metrics:**
- **HOW**: Logged at each step with correlation ID
- **WHY**: Debug latency issues, track OpenCode reliability and event-stream health
- **WHAT**: Typical latency: 2-5s end-to-end; user input loop stays responsive during long runs
- **WHERE**: Structured logs in bot, event processor, and OpenCode client

### Data Flow: X Bookmarks Sync

```
First Message of Day
    ↓
[Check Sync Status] - SQLite: x_sync_status.last_sync_date vs today
    ↓ (needs sync)
[Fetch Bookmarks] - X API (httpx)
    ├─ Daily: fetch since_id (incremental)
    └─ Weekly (>= 7 days): fetch all pages (full mirror reconcile)
    ↓
[Parse & Validate] - Pydantic models (Bookmark, Author, Metrics)
    ↓
[Store in Database] - SQLite: x_bookmarks table
    ├─ UPSERT by tweet_id (preserve bookmarked_at, refresh last_synced_at)
    ├─ Weekly full reconcile prunes rows not returned by X API
    └─ Indexes: bookmarked_at, created_at
    ↓
[Update Sync Status] - SQLite: x_sync_status
    ├─ last_sync_date = today
    ├─ last_tweet_id = newest_id
    ├─ last_full_sync_date = date of last weekly full reconcile
    ├─ last_folders_sync_date = date of last folder refresh
    └─ total_bookmarks = count
    ↓
[Continue User Message] - Process normally via OpenCode
```

**Metrics:**
- **HOW**: Timestamps logged at start/end, bookmark counts tracked
- **WHY**: Monitor sync performance, detect rate limit issues
- **WHAT**: Daily incremental is usually 0-1 API calls; weekly full reconcile fetches all pages
- **WHERE**: Logged as "sync_completed" with new_bookmarks, total_bookmarks

### Data Flow: X Bookmarks Query

```
User Query (Telegram) - "What did I save last week?"
    ↓
[Detect Bookmark Query] - Keywords + time expression matching
    ├─ Keywords: saved, bookmarked, my tweets, my bookmarks
    ├─ Time: last week, yesterday, today, recent
    └─ Pattern: must have keyword AND (time OR "recent")
    ↓ (match)
[Parse Time Range] - Convert natural time to ISO dates
    ├─ "last week" → (now - 7 days) to now
    ├─ "yesterday" → start of yesterday to end of yesterday
    └─ "today" → start of today to now
    ↓
[Query Database] - SQLite: SELECT WHERE bookmarked_at BETWEEN ? AND ?
    ├─ Indexed query on bookmarked_at
    └─ ORDER BY bookmarked_at DESC
    ↓
[Format Results] - Summaries with author, text preview, date
    ├─ Max 10 shown (with "X more" if more)
    ├─ HTML escaping for Telegram
    └─ Option for details on specific tweet
    ↓
[Send to User] - Via Telegram API
```

**Metrics:**
- **HOW**: Query execution time logged, result count tracked
- **WHY**: Monitor query performance, detect indexing issues
- **WHAT**: Typical query: <100ms for 1000 bookmarks
- **WHERE**: Logged as "query_bookmarks" with results count, execution_time

### State Machine: Bookmark Sync Lifecycle

```
[Idle] ←→ [Check Sync Status]
     ↓              ↓
  daily trigger   compare dates
     ↓              ↓
[Needs Sync?] ──no──→ [Continue User Message]
     ↓ yes
[Start Sync]
     ↓
[Set sync_in_progress = true]
     ↓
[Fetch from X API]
     ↓ (success)
[Store Bookmarks]
     ↓
[Update Status]
     ├─ last_sync_date = today
     ├─ last_tweet_id = newest
     └─ total_bookmarks = count
     ↓
[Set sync_in_progress = false]
     ↓
[Continue User Message]
```

**Error Handling:**
- **API failure**: Log error, set sync_in_progress=false, retry tomorrow
- **Database error**: Log error, set sync_in_progress=false, notify user on next query
- **Token expired**: Auto-refresh tokens, log warning, continue
- **Rate limit**: Wait and retry with exponential backoff, log warning

### Component Relationships

```
┌─────────────────────────────────────────────────────────┐
│                   Telegram Bot                         │
│            (python-telegram-bot 21+)                  │
└────────────────────┬────────────────────────────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │    Jarvis Bot         │
          │    (bot.py)          │
          │  - Session Manager   │
          │  - Model Selector    │
          │  - Polling Engine    │
          │  - Command Router    │
          └───────────┬───────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
┌─────────────┐ ┌─────────────┐ ┌──────────────────┐
│  Session    │ │   Model    │ │  Command Router  │
│  Manager    │ │  Selector  │ │                  │
│(session_    │ │(model_     │ │ - Blocked        │
│ manager.py) │ │ selector.py│ │ - Bridge-native  │
└──────┬──────┘ └──────┬──────┘ │ - Intercept      │
       │               │        │ - Pass-through   │
       │               │        └───────┬──────────┘
       │               │                │
       │               │ Regular Chat   │ Bookmarks
       ▼               ▼                │
┌──────────────┐  ┌─────────────┐        │
│ OpenCode     │  │ OpenCode    │        │
│ Client       │  │ Client      │        │
└──────┬───────┘  └──────┬──────┘        │
       │                 │               │
       ▼                 ▼               ▼
┌──────────────────┐             ┌────────────────────┐
│  OpenCode Server │             │  Bookmarks Handler │
│                  │             │ (handlers/bookmarks│
│ - LLM inference  │             │              .py) │
│ - File ops      │             │                    │
│ - Git ops      │             └────────┬───────────┘
│ - Bash cmds    │                      │
└──────────────────┘                      │
       │                                  │
       │ X Bookmarks                      ▼
       ▼                          ┌────────────────────┐
┌──────────────────┐             │  Bookmarks Sync    │
│  Bookmarks       │             │    (sync.py)       │
│  Client         │             │                    │
│ (bookmarks/     │             │ - Auto-sync        │
│  client.py)     │             │ - Daily incremental│
│  + parser.py    │             │ - Weekly reconcile │
└────────┬────────┘             └─────────┬───────────┘
         │                               │
         ▼                               ▼
┌──────────────────┐             ┌────────────────────┐
│    X API Client  │             │  SQLite Database   │
│     (httpx)      │             │   (database/)     │
│                  │             │                    │
│ - OAuth 2.0     │             │ - users.py        │
│ - Rate limiting │             │ - messages.py     │
│ - Pagination    │             │ - bookmarks.py    │
└────────┬────────┘             │ - oauth.py        │
         │                     │ - core.py          │
         ▼                     └────────────────────┘
   (External X API)
```
---

## Tech Context

### Technology Stack

| Layer | Technology | Why Chosen |
|-------|------------|------------|
| **Language** | Python 3.11+ | Async support, type hints, rich ecosystem |
| **Package Manager** | PDM | Modern, PEP 621 compliant, lockfile |
| **Telegram** | python-telegram-bot 21+ | Async, well-maintained, official docs |
| **HTTP Client** | httpx | Async, HTTP/2 support |
| **X API Client** | httpx (custom) | OAuth 2.0 PKCE, auto-refresh tokens |
| **Config** | pydantic-settings | Validation, type-safe, .env support |
| **Logging** | structlog | Structured JSON, correlation IDs, thread-safe |
| **Database** | SQLite | Zero config, embedded, sufficient for single user |
| **Container** | Docker + Orbstack | Isolation, easy deployment, fast on Mac |

### OpenCode Integration

**Working Directory Strategy:**
- `working_dir: /projects` (container) mounted from `~/projects` (host)
- Session data in `/root/.opencode` (via `OPENCODE_HOME`)
- Config in `/root/.config/opencode` (Docker volume)

**Why?**
- File references work: `@jarvis/src/config.py` resolves correctly
- Each project can have its own `AGENTS.md`
- Git operations work naturally (same filesystem)
- Session metadata persists across container restarts

**API Endpoints Used:**

| Endpoint | Purpose | Method |
|----------|---------|---------|
| `/global/health` | Health check | GET |
| `/session` | Create session | POST |
| `/session/{id}/message` | Send regular text | POST |
| `/session/{id}/command` | Execute slash command | POST |

**Model Format:**
OpenCode requires model as object:
```json
{
  "model": {
    "providerID": "opencode",
    "modelID": "glm-5"
  }
}
```

Jarvis parses `provider/model` strings (e.g., `anthropic/claude-sonnet`) and converts to this format. Model and agent info are extracted from response `info` object.

### X Bookmarks Integration

**Authentication Strategy:**

**HOW**: OAuth 2.0 PKCE (Authorization Code Flow with PKCE)

**WHY**:
- X API Bookmarks endpoint requires user-context authentication (app-only Bearer token returns 403 Forbidden)
- OAuth 2.0 PKCE is the standard for confidential clients (bots, automated apps)
- `offline.access` scope provides refresh token for long-term access without re-authorization
- Tokens stored in database (not .env) because they rotate frequently

**WHAT**: 
- One-time setup via `scripts/setup_x_oauth.py` opens browser for user authorization
- Scopes: `bookmark.read`, `tweet.read`, `users.read`, `offline.access`
- Access token auto-refreshes when expired (5-minute buffer)
- API endpoint: `/2/users/{user_id}/bookmarks` (requires actual user ID, not "me")

**WHERE**: 
- OAuth setup: `scripts/setup_x_oauth.py`
- Token storage: `x_oauth_tokens` table in SQLite
- API client: `src/jarvis/bookmarks/client.py`

**Security**: 
- Client secret never exposed to browser (confidential client)
- Tokens stored in database, filtered from logs
- Callback server runs on localhost only (127.0.0.1:8080)

**Cost**: X API is pay-per-use ($0.005 per bookmark request as of 2026)

**Sync Strategy:**

**HOW**:
- Trigger: First Telegram message of each day
- Mode: Daily incremental sync + weekly full mirror reconcile (>=7 days)
- Pagination: Daily uses `since_id`; weekly full reconcile paginates all bookmarks
- Folder sync: Folder assignments are rebuilt weekly during full reconcile
- Payload minimization: bookmark fetch requests only `id`, `text`, `created_at`, and `author.username`
- Status tracking: `x_sync_status` stores last_sync_date, last_tweet_id, last_full_sync_date, last_folders_sync_date, total_bookmarks
- Authentication: OAuth 2.0 tokens auto-refresh when expired

**WHY**:
- Daily sync balances freshness vs. API cost ($0.005/request)
- Incremental sync minimizes daily API usage
- Weekly full reconcile keeps local DB as a true mirror (handles deletions/unbookmarks)
- On-message trigger eliminates background scheduler complexity
- Status tracking enables idempotent syncs (retry-safe)
- Token refresh ensures continuous access without re-authorization

**WHAT**:
- Daily sync is optimized for low cost by fetching only new bookmarks
- Weekly full reconcile cost scales with total bookmarks and folder pagination
- Sync frequency: Daily incremental + weekly full reconcile

**WHERE**:
- Sync logic: `src/jarvis/bookmarks/sync.py`
- Token management: `src/jarvis/bookmarks/client.py::_get_valid_access_token()`
- User ID fetch: `src/jarvis/bookmarks/client.py::_get_user_id()`
- Status table: `x_sync_status` in SQLite database
- Auto-sync trigger: `bot.py::_handle_update()`

**Query Interface:**

**HOW**:
- Natural language detection via keyword + time expression matching
- Keywords: saved, bookmarked, my tweets, my bookmarks, saved posts
- Time expressions: last week, yesterday, today, last month, past week, recent
- Time parsing: Convert natural time to ISO date ranges
- Database query: Indexed `SELECT WHERE bookmarked_at BETWEEN ? AND ?`
- Result formatting: HTML escaping, max 10 results shown, details option

**WHY**:
- Natural language matches user mental model (no commands to memorize)
- Keyword matching is fast and reliable for this use case
- Time expressions are common patterns people use
- Indexed queries ensure fast responses even with thousands of bookmarks
- HTML escaping prevents Telegram rendering issues

**WHAT**:
- Query latency: <100ms for 1000 bookmarks (indexed)
- Result limit: 10 shown, with "X more" if more available
- Accuracy: ~95% for common patterns (improvable with LLM parsing)

**WHERE**:
- Query detection: `handlers/bookmarks.py::is_bookmark_query()`
- Query handling: `handlers/bookmarks.py::handle_bookmark_query()`
- Natural language parsing: `handlers/bookmarks.py::query_bookmarks()`

**Tradeoffs:**
- **Current**: Simple keyword matching, no semantic search
- **Future enhancement**: LLM-based intent detection for better accuracy
- **Current**: Text-based search only
- **Future enhancement**: Vector embeddings for semantic search
- **bookmarked_at limitation**: X API doesn't return bookmark timestamp; column shows sync time, not actual bookmark action time. Use `id` order as proxy for bookmark recency.

**Database Schema:**

**x_oauth_tokens table:**
- `id` (INTEGER PRIMARY KEY CHECK (id = 1)) - Single row for single-user bot
- `access_token` (TEXT NOT NULL) - OAuth 2.0 access token (expires in ~2 hours)
- `refresh_token` (TEXT NOT NULL) - OAuth 2.0 refresh token (long-lived)
- `expires_at` (TIMESTAMP NOT NULL) - Token expiration timestamp
- `scope` (TEXT) - Granted scopes
- `created_at`, `updated_at` (TIMESTAMP) - Token metadata

**x_bookmarks table:**
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT) - Internal row ID
- `tweet_id` (TEXT UNIQUE NOT NULL) - Tweet unique identifier
- `author_username`, `author_name`, `author_verified` - Author info
- `text` (TEXT NOT NULL) - Tweet content
- `created_at`, `bookmarked_at` (TIMESTAMP) - Time metadata
- `tweet_url` (TEXT NOT NULL) - Link to tweet
- `like_count`, `retweet_count`, `reply_count`, `impression_count`, `bookmark_count` (INTEGER) - Engagement metrics
- `media_urls` (TEXT) - JSON array of media URLs
- `urls_expanded` (TEXT) - JSON array of expanded URLs
- `context_annotations` (TEXT) - JSON array of context annotations (legacy/optional)
- `raw_json` (TEXT) - Raw payload snapshot for troubleshooting
- `last_synced_at` (TIMESTAMP) - Last successful sync timestamp for this bookmark

**x_bookmark_folders table:**
- `folder_id` (TEXT PRIMARY KEY) - Folder ID from X API
- `folder_name` (TEXT NOT NULL) - Folder display name
- `created_at` (TIMESTAMP) - First time seen locally

**x_bookmark_folder_assignments table:**
- `tweet_id` (TEXT NOT NULL) - Bookmark tweet ID
- `folder_id` (TEXT NOT NULL) - Folder ID
- `assigned_at` (TIMESTAMP) - Assignment sync timestamp
- Composite primary key `(tweet_id, folder_id)`
- Foreign keys to `x_bookmarks(tweet_id)` and `x_bookmark_folders(folder_id)` with cascade delete

**x_sync_status table:**
- `id` (INTEGER PRIMARY KEY CHECK (id = 1)) - Single row
- `last_sync_date` (TEXT) - ISO date string of last sync (YYYY-MM-DD)
- `last_sync_at` (TIMESTAMP) - Full timestamp of last sync
- `last_tweet_id` (TEXT) - Most recent tweet ID synced
- `last_full_sync_date` (TEXT) - Last weekly full mirror reconcile date
- `last_folders_sync_date` (TEXT) - Last folder membership refresh date
- `total_bookmarks` (INTEGER) - Total count of bookmarks in DB
- `sync_in_progress` (BOOLEAN) - Prevents concurrent syncs
- `first_sync_complete` (BOOLEAN) - Distinguishes first run from subsequent runs

**Indexes:**
- `idx_bookmarks_bookmarked_at` on `x_bookmarks(bookmarked_at)` - Fast time-range queries
- `idx_bookmarks_created_at` on `x_bookmarks(created_at)` - Fast tweet creation queries
- `idx_bookmark_folders_tweet_id` on `x_bookmark_folder_assignments(tweet_id)` - Fast export by tweet
- `idx_bookmark_folders_folder_id` on `x_bookmark_folder_assignments(folder_id)` - Fast export by folder

### Error Handling Strategy

**Three Severity Levels:**

| Severity | Behavior | Examples |
|----------|----------|----------|
| **FATAL** | Logs critical error, raises exception, bot exits | Database init failed, OpenCode unhealthy |
| **WARNING** | Logs warning with context, continues operation | Message audit log fail, response log fail |
| **USER ERROR** | Returns user-friendly error message, logs details | Invalid command, malformed input |

**All Errors Logged With Context:**
- `user_id`: Which user triggered the error
- `session_id`: Which session (if applicable)
- `operation`: What action failed (sync, query, send_message, etc.)
- `error`: Error message/stack trace
- `correlation_id`: Unique ID for request tracking

**Why Context Matters:**
- Debugging: Quickly identify which user/session is affected
- Monitoring: Track error rates per operation
- Analysis: Identify common failure patterns

### Security Model

**Authentication:**
- **How**: Telegram user ID allowlist in SQLite database
- **Why**: Simple, no OAuth complexity, works with Telegram's existing auth
- **What**: Single user (can be extended to multi-user allowlist)
- **Where**: `database/users.py::UserManager.is_user_allowed()` checks user_id

**Network Security:**
- **How**: Polling only, no public ports, no webhooks
- **Why**: No attack surface, no need for Tailscale, runs entirely locally
- **What**: Bot makes outbound connections only (to Telegram API, OpenCode, X API)
- **Where**: `polling_engine.py` implements long polling

**Secrets Management:**
- **How**: `.env` file, never committed to git, filtered from logs
- **Why**: Prevents accidental exposure in commits/logs/GitHub
- **What**: All secrets (bot tokens, API keys, passwords) in `.env`
- **Where**: `config.py` reads from `.env` using pydantic-settings

**Logging Security:**
- **How**: Structured JSON with secrets filtering, httpx INFO logs suppressed
- **Why**: httpx INFO logs expose bot tokens (documented issue)
- **What**: All logs filtered for known secret patterns before output
- **Where**: `logging_config.py` implements secret filtering

**Container Security:**
- **How**: Docker multi-stage build, non-root user, read-only filesystem
- **Why**: Defense in depth, least privilege principle
- **What**: Read-only `/app`, no new privileges, resource limits
- **Where**: `Dockerfile` implements security best practices

**Database Security:**
- **How**: SQLite file in `.jarvis/` directory (gitignored), single-user access
- **Why**: No network exposure, no SQL injection (parameterized queries)
- **What**: Contains user data, bookmarks, responses
- **Where**: `.jarvis/jarvis.db` stored in project directory

### Performance Considerations

**Polling Latency:**
- **HOW**: Measured from message send to bot receive (includes Telegram network)
- **WHY**: User experience metric, determines polling interval settings
- **WHAT**: ~1-2 seconds typical (depends on Telegram polling interval)
- **WHERE**: Logged as `polling_latency` in structured logs

**Query Performance:**
- **HOW**: Measured database query execution time
- **WHY**: Ensure bookmarks queries remain fast as collection grows
- **WHAT**: <100ms for 1000 bookmarks (indexed queries)
- **WHERE**: Logged as `query_execution_time` in bookmark queries

**Sync Performance:**
- **HOW**: Measured sync duration and bookmark count
- **WHY**: Monitor API rate limits, detect performance degradation
- **WHAT**: 10-30 seconds for 100-500 bookmarks (rate limited)
- **WHERE**: Logged as `sync_duration` and `new_bookmarks` in sync logs

**Storage Growth:**
- **HOW**: Track database file size and row counts
- **WHY**: Prevent unbounded growth, plan cleanup strategies
- **WHAT**: Responses auto-cleanup (30 days), bookmarks indefinite (consider future pruning)
- **WHERE**: Logged in database initialization and cleanup jobs

### Configuration

**Required Environment Variables:**

| Variable | Description | Example |
|----------|-------------|----------|
| `TELEGRAM_BOT_ID` | Telegram bot token from @BotFather | `123456:ABC-xyz123` |
| `TELEGRAM_USER_ID` | Your Telegram user ID from @userinfobot | `123456789` |
| `OPENCODE_URL` | OpenCode Server URL | `http://localhost:4096` |
| `OPENCODE_SERVER_PASSWORD` | OpenCode Server password | `secure_password` |

**Optional Environment Variables:**

| Variable | Description | Default |
|----------|-------------|----------|
| `X_CLIENT_ID` | X OAuth 2.0 Client ID from Developer Console | `None` (bookmarks disabled) |
| `X_CLIENT_SECRET` | X OAuth 2.0 Client Secret from Developer Console | `None` (bookmarks disabled) |
| `X_BEARER_TOKEN` | X API Bearer token (DEPRECATED, use OAuth 2.0) | `None` |
| `TELEGRAM_POLLING_INTERVAL` | Seconds between polling requests | `2.0` |
| `TELEGRAM_POLLING_TIMEOUT` | Timeout for getUpdates in seconds | `30` |
| `LOG_LEVEL` | Python logging level | `INFO` |
| `DATABASE_PATH` | SQLite database file path | `.jarvis/jarvis.db` |
| `ENABLE_MESSAGE_AUDIT` | Enable message audit trail | `true` |
| `FAVORITE_MODELS_PATH` | Path to favorite models JSON | `.jarvis/favorite_models.json` |

**Configuration Files:**

**`.jarvis/favorite_models.json`**:
```json
[
  "openai/gpt-5.2",
  "zai/glm-4.7",
  "openai/gpt-5.3-codex"
]
```

**Why?** 
- First model in list is used as default for new sessions
- Provides quick model selection without typing full provider/model strings
- Used as fallback when OpenCode returns model-related errors

---

## Deployment

### Production Deployment

**Environment:**
- **Host**: Mac Mini M4 (16GB RAM)
- **Container Runtime**: Orbstack (Docker-compatible)
- **Network**: Polling only (no public ports)
- **Storage**: Local SQLite database in `.jarvis/` directory

**How to Deploy:**
```bash
# Clone repository
git clone https://github.com/yourusername/jarvis.git
cd jarvis

# Configure environment
cp .env.example .env
# Edit .env with your tokens

# Start container
docker compose up -d

# View logs
docker compose logs -f
```

**Monitoring:**
- **Health Check**: Container health status
- **Logs**: Structured JSON logs with correlation IDs
- **Metrics**: Sync status, query performance, error rates

**Backups:**
- **Database**: Backup `.jarvis/jarvis.db` regularly
- **Config**: Backup `.env` file (contains secrets)
- **Models**: Backup `.jarvis/favorite_models.json`

### Development Setup

**Install Dependencies:**
```bash
pdm install
```

**Run Locally:**
```bash
pdm run python -m jarvis
```

**Run Tests:**
```bash
# All tests
pdm run pytest

# Specific test file
pdm run pytest tests/test_bookmark_client_sync.py -v

# With coverage
pdm run pytest --cov=src/jarvis --cov-report=term-missing
```

**Lint:**
```bash
# Check code
pdm run ruff check .

# Format code
pdm run ruff format .
```

---

## Related Documents

- [Product Requirements Document](prd/) - Full specification (20 sections)
- [README.md](../README.md) - Quick start guide
- [CHANGELOG.md](../CHANGELOG.md) - History of changes
- [Docker Best Practices](docs/docker-best-practices.md) - Security hardening guide
- [OpenCode Server API](https://opencode.ai/docs/server) - External API reference
