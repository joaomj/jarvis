# Technical Context

> Source of truth for Jarvis architecture and decisions.
> Update this when architecture changes.

## Current Status

**Phase**: 1 (MVP) - Telegram-OpenCode Bridge  
**Status**: Development starting  
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
- **Telegram**: Long-polling (MVP) or webhook via Tailscale Funnel (Phase 2)

### Why Mac Mini (not VPS)?

1. **Direct file access**: OpenCode must read/write project files
2. **Lower latency**: No network hops to access code
3. **Simpler setup**: No NFS mounts, SSH tunnels, or sync complications
4. **Existing hardware**: Already paid for, sufficient resources (M4, 16GB)

### VPS Fallback (Phase 5+)

For 24/7 availability when Mac Mini is offline:
- Lightweight bot on VPS
- Chat only, no file access
- Phase 1 bot on Mac Mini handles coding tasks

## Security Model

1. **Network**: No public ports, Tailscale only
2. **Auth**: Telegram user ID allowlist
3. **Secrets**: `.env` file, never in code/logs
4. **Logging**: Structured JSON, correlation IDs

## File Structure (Phase 1)

```
jarvis/
|-- src/jarvis/
|   |-- __main__.py          # Entry point
|   |-- config.py            # pydantic-settings
|   |-- logging.py           # structlog setup
|   |-- bot.py               # Telegram bot
|   |-- opencode_client.py   # OpenCode HTTP client
|   `-- formatter.py         # Response formatting
|-- tests/
|-- docs/
|-- docker-compose.yml
|-- Dockerfile
`-- pyproject.toml
```

## Open Decisions

| Decision | Status | Notes |
|----------|--------|-------|
| Webhook vs Polling | Polling for MVP | Webhook requires Tailscale Funnel setup |
| VPS fallback | Deferred to Phase 5+ | Mac Mini primary for file access |

## Lessons Learned

(Update as we learn)

- TBD
