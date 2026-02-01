# Technical Context

> Source of truth for Jarvis architecture and decisions.
> Update this when architecture changes.

## Current Status

**Phase**: 1 (MVP) - Telegram-OpenCode Bridge  
**Status**: Implementation complete, ready for deployment  
**Last Updated**: 2026-02-01

## Architecture Overview

Jarvis is a **thin passthrough bridge** between Telegram and OpenCode Server.

```
Telegram <-> Jarvis Bot (Python) <-> OpenCode Server
                 |                        |
            - Allowlist              - LLM calls
            - Formatting             - File ops
            - Routing                - Git ops
                                     - Sessions
```

### Key Decision: No Gateway Abstraction

We explicitly chose NOT to build a Gateway/Router pattern. Rationale:
- OpenCode already handles command parsing, LLM routing, tool execution
- Adding abstraction would duplicate logic and add maintenance burden
- Simpler = fewer bugs, faster development

### Data Flow

1. User sends Telegram message
2. Jarvis checks allowlist (silent ignore if unauthorized)
3. Jarvis detects `/command` vs regular text
4. Routes to appropriate OpenCode endpoint:
   - `/command` -> `POST /session/{id}/command`
   - Regular text -> `POST /session/{id}/message`
5. OpenCode processes (LLM, tools, files)
6. Jarvis formats response for Telegram (chunking, markdown)
7. Response sent to user

## Technology Stack

| Layer | Technology | Why |
|-------|------------|-----|
| Language | Python 3.11+ | Async, type hints, ecosystem |
| Package Manager | PDM | Modern, PEP 621, lockfile |
| Telegram | python-telegram-bot 21+ | Async, well-maintained |
| HTTP Client | httpx | Async, HTTP/2 |
| Config | pydantic-settings | Validation, .env |
| Logging | structlog | JSON, correlation ID |
| Container | Docker + Orbstack | Isolation, easy deployment |

## OpenCode Integration

### Working Directory Strategy

OpenCode Server runs with:
- `working_dir: /projects` (container)
- Mounted from `~/projects` (host)
- Session data in `/root/.opencode` (via `OPENCODE_HOME`)
- Config in `/root/.config/opencode` (Docker volume)

This allows:
- `@jarvis/src/config.py` resolves correctly
- Each project can have its own `AGENTS.md`
- Git operations work naturally
- Session metadata persists across container restarts

### API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /global/health` | Health check |
| `POST /session` | Create session |
| `POST /session/{id}/message` | Send regular text |
| `POST /session/{id}/command` | Execute slash commands |

## Deployment

- **Host**: Mac Mini M4 (16GB)
- **Container Runtime**: Orbstack
- **Network**: Tailscale mesh (no public ports)
- **Telegram**: Webhook via Tailscale Funnel (default - fast, low latency)

### Why Mac Mini (not VPS)?

1. **Direct file access**: OpenCode must read/write project files
2. **Lower latency**: No network hops to access code
3. **Simpler setup**: No NFS mounts, SSH tunnels, or sync complications
4. **Existing hardware**: Already paid for, sufficient resources (M4, 16GB)

## Security Model

1. **Network**: No public ports, Tailscale only
2. **Auth**: Telegram user ID allowlist
3. **Secrets**: `.env` file, never in code/logs
4. **Logging**: Structured JSON, correlation IDs

## Open Decisions

| Decision | Status | Notes |
|----------|--------|-------|
| Webhook vs Polling | **Webhook implemented** | Fast delivery via Tailscale Funnel |
| VPS fallback | **Never** | Mac Mini only - direct file access required |

## References

### OpenCode Server API
- **Documentation**: https://opencode.ai/docs/server
- **Local Spec**: `http://localhost:4096/doc` (when server running)
- **Authentication**: HTTP Basic Auth (username: `opencode`, password from env)

## File Structure

```
jarvis/
├── src/jarvis/              # Application source code
│   ├── __init__.py
│   ├── __main__.py          # Entry point (webhook server)
│   ├── bot.py               # Telegram bot implementation
│   ├── config.py            # Configuration (pydantic-settings)
│   ├── formatter.py         # Response formatting (markdown, chunking)
│   ├── logging.py           # Structured logging (structlog)
│   └── opencode_client.py   # HTTP client for OpenCode Server
├── tests/                   # Test suite
│   ├── test_bot.py
│   ├── test_config.py
│   ├── test_formatter.py
│   ├── test_logging.py
│   └── test_opencode_client.py
├── docs/                    # Documentation
│   ├── prd/                 # Product Requirements Document (20 sections)
│   ├── tech-context.md      # This file - architecture decisions
│   ├── docker-best-practices.md  # Docker security & optimization
│   └── what-i-want.md       # Original vision document
├── Dockerfile               # Multi-stage, non-root, minimal
├── docker-compose.yml       # Production orchestration
├── pyproject.toml           # PDM, ruff, pytest configuration
├── .env.example            # Environment template
├── .pre-commit-config.yaml  # gitleaks, ruff, mypy hooks
└── README.md               # Quick start guide
```

## Related Documents

- [Product Requirements Document](prd/) - Full specification (20 sections)
- [README.md](../README.md) - Project overview and quick start
- [Docker Best Practices](docker-best-practices.md) - Security hardening guide
- [OpenCode Server API](https://opencode.ai/docs/server) - External API reference

## Lessons Learned

(Update as we learn)

- TBD
