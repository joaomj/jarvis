# Technical Context

> Source of truth for Jarvis architecture and decisions.
> Update this when architecture changes.

## Current Status

**Phase**: 1 (MVP) - Telegram-OpenCode Bridge
**Status**: Implementation complete, model selection and response logging added
**Last Updated**: 2026-02-14

## Migration Complete

The codebase has been migrated from a monolithic structure to a modular architecture:
- **Command Router**: Central routing for all commands (`command_router.py`)
- **Handlers Package**: Modular command handlers (`handlers/commands.py`)
- **Structured Logging**: JSON logging with correlation IDs (`logging_config.py`)
- **Models & Exceptions**: Type-safe data structures and error handling
- **51 Tests**: Comprehensive test coverage including integration tests

## Architecture Overview

Jarvis is a **thin passthrough bridge** between Telegram and OpenCode Server with a **modular command routing system**.

```
Telegram <-> Jarvis Bot (Python) <-> OpenCode Server
                 |                        |
            - Command Router         - LLM calls
            - Handler Package        - File ops
            - Allowlist              - Git ops
            - Formatting             - Sessions
```

### Command Routing Architecture

The bot uses a centralized command router that categorizes commands:

1. **Blocked Commands** (`exit`, `quit`, `editor`, `themes`) - Not available in Telegram
2. **Bridge-Native** (`switch`, `agent`, `model`) - Handled by Jarvis
3. **Intercept Commands** (`models`, `new`, `sessions`) - Bridge processes before OpenCode
4. **Pass-Through** (`compact`, `undo`, `share`, etc.) - Forwarded directly to OpenCode

### Key Decision: Modular Handler Pattern

We migrated from a monolithic bot.py to a modular architecture:
- **Benefits**: Better testability, clearer separation of concerns, easier maintenance
- **Tradeoff**: Slightly more files, but each under 300 lines (pre-commit enforced)
- **Migration Date**: 2026-02-08

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

### Model Format

OpenCode requires model parameter as an object:
```json
{
  "model": {
    "providerID": "opencode",
    "modelID": "glm-5"
  }
}
```

Jarvis parses `provider/model` strings and converts to this format. Model and agent info are extracted from response `info` object.

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
├── src/jarvis/                   # Application source code
│   ├── __init__.py
│   ├── __main__.py               # Entry point (webhook server)
│   ├── bot.py                    # Telegram bot implementation (webhook mode)
│   ├── command_router.py         # Central command routing logic
│   ├── config.py                 # Configuration (pydantic-settings)
│   ├── database.py               # SQLite database for responses and audit
│   ├── exceptions.py             # Custom exception classes
│   ├── formatter.py              # Response formatting (markdown, chunking)
│   ├── logging_config.py           # Structured logging (structlog)
│   ├── models.py                 # Pydantic data models
│   ├── opencode_client.py        # HTTP client for OpenCode Server
│   ├── utils.py                  # Utility functions
│   └── handlers/                 # Modular command handlers
│       ├── __init__.py
│       └── commands.py           # Bridge-native command implementations
├── tests/                        # Test suite (51 tests)
│   ├── test_bot.py              # Bot functionality tests
│   ├── test_config.py           # Configuration tests
│   ├── test_formatter.py        # Response formatting tests
│   ├── test_logging.py          # Structured logging tests
│   ├── test_migration.py        # Migration verification tests
│   └── test_opencode_client.py  # OpenCode API client tests
├── docs/                         # Documentation
│   ├── prd/                     # Product Requirements Document (20 sections)
│   ├── tech-context.md          # This file - architecture decisions
│   ├── docker-best-practices.md # Docker security & optimization
│   └── what-i-want.md           # Original vision document
├── Dockerfile                    # Multi-stage, non-root, minimal
├── docker-compose.yml           # Production orchestration
├── pyproject.toml               # PDM, ruff, pytest configuration
├── .env.example                 # Environment template
├── .pre-commit-config.yaml      # gitleaks, ruff, mypy hooks
└── README.md                    # Quick start guide
```

### Migration Changes

**Files Added** (from opencode-mobile migration):
- `command_router.py` - Central command routing
- `handlers/commands.py` - Bridge-native command implementations
- `logging_config.py` - Structured JSON logging
- `models.py` - Type-safe data models
- `exceptions.py` - Custom error classes
- `utils.py` - Utility functions
- `tests/test_migration.py` - Migration verification tests

**Files Modified**:
- `bot.py` - Adapted to use new command router, model/agent from response
- `database.py` - Added responses table with 30-day cleanup
- `opencode_client.py` - Fixed model format, extract agent from response
- `tests/` - All tests updated for new architecture (51 tests total)

## Testing Strategy

### Test Organization

| Test File | Purpose | Count |
|-----------|---------|-------|
| `test_bot.py` | Bot authorization, sessions, message handling | 10 |
| `test_config.py` | Settings validation, environment loading | 6 |
| `test_formatter.py` | Response formatting, markdown, chunking | 12 |
| `test_logging.py` | Structured logging, JSON output | 5 |
| `test_migration.py` | Migration verification, command routing | 4 |
| `test_opencode_client.py` | OpenCode API client, health checks | 14 |

### Running Tests

```bash
# All tests
pdm run pytest

# Specific test file
pdm run pytest tests/test_migration.py -v

# With coverage
pdm run pytest --cov=src/jarvis --cov-report=term-missing

# Integration test (requires OpenCode server)
pdm run pytest tests/test_opencode_client.py -v
```

### Pre-Commit Hooks

All commits are checked for:
- Security leaks (gitleaks)
- Code formatting (ruff)
- Type checking (mypy)
- File length (< 300 lines)

## Related Documents

- [Product Requirements Document](prd/) - Full specification (20 sections)
- [README.md](../README.md) - Project overview and quick start
- [Docker Best Practices](docker-best-practices.md) - Security hardening guide
- [OpenCode Server API](https://opencode.ai/docs/server) - External API reference

## Lessons Learned

- **2026-02-08**: Migration to modular architecture improved testability significantly
- **2026-02-08**: Command router pattern simplifies adding new commands
- **2026-02-08**: Structured logging with correlation IDs essential for debugging
- **2026-02-14**: OpenCode API requires model as object {providerID, modelID}, not string
- **2026-02-14**: Model and agent info available in response info, no separate API calls needed
- **2026-02-14**: httpx INFO logs expose bot tokens, must be suppressed in production
