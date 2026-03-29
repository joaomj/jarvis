# Performance Considerations

Performance characteristics and optimization guidelines.

## Polling Latency

**Measurement:** Time from message send to bot receive (includes Telegram network)

**Typical:** ~1-2 seconds (depends on Telegram polling interval)

**Logged as:** `polling_latency` in structured logs

**Configuration:**
- `TELEGRAM_POLLING_INTERVAL=2.0` (seconds between polls)
- `TELEGRAM_POLLING_TIMEOUT=30` (timeout for getUpdates)

## Query Performance

**Bookmark Queries:**
- Target: <100ms for 1000 bookmarks
- Method: Indexed queries on `bookmarked_at`, `created_at`
- Logged as: `query_execution_time`

**Vault Search:**
- Target: <200ms for hybrid retrieval
- Components:
  - FTS5 lexical search
  - sqlite-vec semantic search
  - RRF fusion
- Logged as: `vault_query` with execution time

## Sync Performance

**X Bookmarks Sync:**
- Daily incremental: 0-1 API calls
- Weekly full reconcile: 10-30 seconds for 100-500 bookmarks
- Rate limited by X API

**Logged metrics:**
- `sync_duration`
- `new_bookmarks`
- `total_bookmarks`

## Storage Growth

**Auto-cleanup:**
- Responses: 30 days
- Bookmarks: Indefinite (consider future pruning)

**Monitoring:**
- Database file size tracked
- Row counts logged at initialization

**Location:** `vault/index/jarvis.db`

## Memory Usage

**Target deployment:** Mac Mini M4 (16GB RAM)

**SQLite memory:** Minimal (embedded, single-user)
**Embedding models:** Loaded on demand
**Context window:** Managed by OpenCode

## Optimization Guidelines

1. **Indexing:** All query patterns have appropriate indexes
2. **Chunking:** Documents chunked by headings for efficient retrieval
3. **Caching:** Sessions cached in memory
4. **Lazy loading:** Embeddings generated on-demand

## Bottlenecks

**Known:**
- Telegram polling adds 1-2s latency
- X API rate limits sync speed
- First embedding load takes time

**Mitigation:**
- Polling is acceptable for personal use
- Incremental sync minimizes API calls
- Models cached after first load
