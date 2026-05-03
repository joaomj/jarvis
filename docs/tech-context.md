# Technical Context

Source of truth for Alfred architecture, decisions, and engineering detail.

## Project Brief

Alfred is a **personal AI assistant accessible via Telegram** built with PydanticAI and a skill-based architecture.

**Core Requirements:**
- Chat with AI via Telegram from mobile phone
- Alfred persona (Nolan's Alfred Pennyworth) as default bot personality
- Skill-based commands for specialized tasks (/deep-research, /private, etc.)
- Local memory persistence (SOUL.md, MEMORY.md, USER.md)
- No public network exposure (polling mode)
- Single-user security model

**Goals:**
- Mobile access to a personal AI butler
- Extensible via skills (plugins/tools)
- Security and privacy
- Minimal infrastructure

## Architecture

### Core Pattern

Files are the source of truth; databases are derived indexes.
SOUL.md defines the assistant's identity, MEMORY.md stores learned facts, USER.md stores user profile.

### Component Architecture

```
Telegram (mobile)
    |
    v
polling_engine.py    -- HTTP polling (httpx) to Telegram API
    |
    v
telegram_gateway.py  -- Message routing, skill dispatch, streaming, /model menu
    |
    v
agent.py             -- PydanticAI Agent with skill injection
    |                     AlfredDeps: MemoryManager, ConversationStore, SkillLoader
    |
    +---> skill_loader.py   -- Loads skills/ SKILL.md + scripts
    +---> memory.py         -- SOUL.md / MEMORY.md / USER.md read/write
    +---> conversation.py   -- FTS5-backed message history
    +---> models.py         -- Model registry for /model menu
```

### Why Telegram + Polling?

1. **Mobile access**: Telegram available everywhere
2. **No public URLs**: Polling eliminates webhook complexity
3. **Single-user**: Allowlist-based auth
4. **Simplicity**: Single process deployment

## Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Package Manager | uv |
| AI Framework | PydanticAI |
| LLM Provider | OpenCode Go (OpenAI-compatible) |
| Telegram | Raw HTTP (httpx, polling) |
| Config | pydantic-settings |
| Database | SQLite + FTS5 |
| Logging | Structured JSON with correlation IDs |
| Skill Format | YAML frontmatter + Python scripts |
| Container | Docker (optional) |

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| UI layer | Telegram | Mobile-first, no public ports, polling mode |
| Persona | SOUL.md (committed) | Version-controlled, human-readable identity |
| Memory | File-based (MEMORY.md, USER.md) | Portable, versionable, user data gitignored |
| AI Framework | PydanticAI | Structured agent output, dependency injection |
| LLM Provider | OpenCode Go | Low-cost open models, OpenAI-compatible API |
| Skills | YAML + scripts | Agentskills.io standard, extensible |
| Conversation | SQLite FTS5 | Full-text search, local, zero-dependency |
| Logging | JSON + correlation IDs | Structured, grep-friendly, traceable |
| Polling vs webhooks | Polling | No public URLs, runs locally |

## Configuration

All settings via environment variables, validated by pydantic-settings (`src/config.py`).

### Required

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `TELEGRAM_USER_ID` | Authorized Telegram user ID |
| `OPENCODE_GO_API_KEY` | OpenCode Go API key from opencode.ai/auth |

### Optional (with defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL` | `opencode-go:deepseek-v4-flash` | Model identifier (change via /model) |
| `TELEGRAM_POLLING_INTERVAL` | `1.0` | Seconds between polls (min 0.5) |
| `TELEGRAM_POLLING_TIMEOUT` | `30` | getUpdates timeout (10-120s) |
| `DATABASE_PATH` | `vault/index/alfred.db` | SQLite FTS5 database |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `VAULT_ROOT` | `vault` | Root directory for vault artifacts |
| `POLLING_MAX_BACKOFF_SECONDS` | `60` | Backoff delay cap |

## Security Model

| Layer | Method | Implementation |
|-------|--------|----------------|
| Authentication | Telegram user ID allowlist | `gateway.handle_update()` filters by user ID |
| Network | Polling only, no public ports | `polling_engine.py` — outbound only |
| Secrets | Single `.env` file | gitignored |
| Database | SQLite file, gitignored | `vault/index/alfred.db` |
| Private mode | `/private` command | Message content truncated in logs |

## Performance

| Metric | Target | Notes |
|--------|--------|-------|
| Polling latency | ~1-2s | Includes Telegram network |
| Conversation search | <100ms | FTS5 indexed queries |

## Observability

- Structured JSON logs to stdout
- Correlation ID on every log entry
- Message content logged (truncated for /private)
- Model switch events logged

## External References

- [PydanticAI Documentation](https://ai.pydantic.dev/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Agentskills.io Standard](https://agentskills.io)
- [OpenCode Go](https://opencode.ai/docs/go/)
