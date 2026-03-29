# Roadmap

Jarvis: a personal AI assistant (butler, consigliere) accessible via Telegram, bridging mobile chat with OpenCode Server.

## Vision & Principles

- **Single continuous chat** - no thread management UI. All organization happens in the background.
- **Memory sovereignty** - memories, logs, and learnings stored locally in `vault/`, portable and syncable.
- **LLM independence** - models/providers swappable without losing assistant usefulness.
- **Self-improving** - the agent must passively learn from its user over time.
- **Thin bridge** - Jarvis bridges Telegram to OpenCode; all AI intelligence stays in OpenCode.
- **No full autonomy** - the agent does not have unrestricted OS/filesystem access. Allowlist-only.
- **Auto-context** - every message automatically retrieves relevant context from the knowledge base and conversation history. No explicit recall/remember commands needed.

## Hardware & Constraints

- Mac Mini M4 (16GB RAM, 256GB SSD) as primary host
- iPhone 16 for mobile access
- Home network on ISP router (no admin access)
- Familiar with Tailscale and Cloudflare tunnels

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| UI layer | Telegram | Mobile-first, no public ports, polling mode |
| Memory storage | `vault/` (files) | Files are source of truth; databases are derived indexes |
| Cloud sync | Ignore for now | Local-first; reconsider Syncthing/git later |
| Source-grounded mode | No special mode | Jarvis detects source-grounded questions and prioritizes retrieved sources |
| Source priority | Attached > vault/ > reputable web > general web | Most specific context first |
| Sourced answers | Default behavior | When web sources help, include high-reputation citations without extra confirmation |
| Commands | OpenCode custom commands | Thin bridge; leverage OpenCode extensibility |
| PDF extraction | LLM-based via OpenCode | Avoid fragile traditional PDF parsers |
| Retrieval | Hybrid (FTS5 + sqlite-vec + RRF fusion) | BM25 + semantic, fused via Reciprocal Rank Fusion |
| Command discoverability | OpenCode `GET /command` + Telegram `set_my_commands` | No custom help command needed; commands appear natively in Telegram menu |
| Conversation memory | OpenCode sessions DB (read-only) | Leverage OpenCode's built-in session management; no separate memory store |
| Architecture | Medallion (bronze + silver) | Raw data in `vault/raw/`, processed indexes in `vault/index/` |
| Software philosophy | Open source, no vendor lock-in | Prefer portable solutions |

## Use Cases (Priority Order)

### High Priority / Active Pain Point
- **Summarize saved content** - X bookmarks, Substack newsletters, articles. Option to save as local markdown. This is the most urgent use case.

### Daily Use
- Chat about topics (History, Economics, random questions)
- Personal counselling ("Alfred Pennyworth" persona - Christopher Nolan's trilogy)
- Software engineering via OpenCode (remote command)

### Research
- Detailed technical reports from trustworthy sources (not Reddit)
- Research paper reliability analysis (statistical methodology)
- PDF document discussion (like Google's NotebookLM) - send PDF, discuss using only that source

### On Demand
- Private questions (not recorded)
- Summarize arbitrary PDFs, markdown files, books

## Current Status

Jarvis is a local Telegram bot that bridges mobile chat to OpenCode Server. All commands are routed through OpenCode (local command handling was removed).

**Implemented:**
- Telegram bridge with polling mode
- Local persistence (SQLite)
- X bookmarks sync (OAuth2, daily incremental)
- URL save with KB indexing (`/save`) to `vault/raw/url-saves/`
- Attachment ingestion to `vault/raw/attachments/`
- Hybrid retrieval (FTS5 + sqlite-vec + RRF fusion)
- Auto-retrieval (every message gets relevant KB + conversation context injected)
- Feedback mechanism (thumbs up/down on responses)
- Model/agent visibility via pinned status message (session, model, agent, context tokens)
- Model selection from favorites list (`/models`)
- Session management (daily rotation, persistence, `/new`, `/switch`)
- Event processing (SSE handling from OpenCode)
- Sync health monitoring (drift detection and repair)
- Command routing (blocks TUI-only commands like `/exit`, `/editor`)
- Command discoverability (Telegram menu via `set_my_commands` from OpenCode `GET /command`)
- Health probe (daily startup check with model info)
- Medallion architecture (bronze: `vault/raw/`, silver: `vault/index/`)
- OpenCode runs with `XDG_DATA_HOME=vault/raw/` (sessions DB lives in vault)

**On Hold:**
- PDF extraction (LLM quality varies by model; needs per-model evaluation)

**Not Planned:**
- Voice input (STT)
- Command discoverability via `/help-jarvis` (replaced by native Telegram command menu)

## Implementation Phases

### Phase 1-6: [COMPLETE]

- Phase 1: Establish vault/ as source of truth
- Phase 2: Private mode
- Phase 3: Curated memory (removed: replaced by OpenCode conversation history)
- Phase 4: Source-grounded answers
- Phase 5: Attached files as sources
- Phase 6: Hybrid retrieval

### Phase 7: PDF Ingestion [ON HOLD]

LLM-based PDF extraction quality varies by model. Revisit when a reliable approach is identified.

### Phase 8: Memory System Overhaul [COMPLETE]

Replaced curated memory system with OpenCode conversation history:
- Removed `memory_entries` table, `MemoryStore`, `BotMemoryMixin`
- Removed per-message LLM classification tax for memory intents
- Removed `/recall`, `/remember`, `/forget` commands
- Added auto-retrieval: every message automatically gets relevant KB + conversation context
- Added conversation history search via OpenCode DB (read-only)

### Phase 9: [COMPLETE]

Unified hybrid context retrieval with semantic search. RRF fusion of FTS5 + sqlite-vec results.

### Phase 10: UX Improvements [COMPLETE]

- Feedback mechanism (thumbs up/down inline keyboard)
- Model/agent visibility (pinned status message)
- Command discoverability (Telegram command menu via `set_my_commands`)

### Phase 11: Medallion Architecture [COMPLETE]

- Restructured vault/ into `vault/raw/` (bronze) and `vault/index/` (silver)
- OpenCode runs with `XDG_DATA_HOME=vault/raw/` (sessions DB in vault)
- Database moved to `vault/index/jarvis.db`
- Dead code removed (System B: hybrid_retrieval, embedding, embedding_indexer, embedding_ops)

## Priority Order

### Immediate

1. Verify OpenCode creates DB in vault/raw/opencode/ on startup
2. Verify end-to-end: OpenCode health check + auto-retrieval on messages

### Short-term

2. Evaluate PDF extraction approaches per model
3. Passive learning / self-improvement research

### Medium-term

4. Cloud sync strategy (Syncthing vs git-based)

## Open Questions

- Approach for agent learning (passive improvement from user interactions)
- Approach for reliable skill/tool invocation by the agent
- Cloud sync strategy (Syncthing vs git-based)

## References

### Memory & Agent Architecture
- [Agent Skills vs. Rules vs. Commands vs. Subagents](https://x.com/tempoimmaterial/status/2014054104658526645)
- [WTF is a Context Graph?](https://x.com/parcadei/status/2013713799719559480)
- [Memory as reasoning](https://blog.plasticlabs.ai/blog/Memory-as-Reasoning)
- [sqlite-vec - local vector search for SQLite](https://github.com/asg017/sqlite-vec)
- [How Clawdbot Remembers Everything](https://x.com/manthanguptaa/status/2015780646770323543)
- [The Three-Layer Memory System Upgrade for Clawdbot](https://x.com/spacepixel/status/2015967798636556777)
- [Build Agents That Learn](https://x.com/ashpreetbedi/status/2016318096772936159)
- [Agents Need a Database](https://x.com/ashpreetbedi/status/2015935966268018823)
- [Dynamic context discovery](https://cursor.com/blog/dynamic-context-discovery)
- [How to build agents with filesystems and bash](https://vercel.com/blog/how-to-build-agens-with-filesystems-and-bash)

### Tools & Plugins
- [opencode-telegram-bot](https://github.com/grinev/opencode-telegram-bot) - closest implementation to reference
- [supermemory](https://github.com/supermemoryai/opencode-supermemory) - OpenCode memory plugin
- [websearch citations](https://github.com/ghoulr/opencode-websearch-cited)
- [OpenCode Commands](https://opencode.ai/docs/commands/)

### Research Sources
- [Semantic Scholar API](https://www.semanticscholar.org/product/api/tutorial) - 1 req/s with API key
- [Anna's Archive API](https://annas-archive.li/faq#api) - free books/papers
