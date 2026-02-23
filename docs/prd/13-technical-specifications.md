
## 13. Technical Specifications

### 13.1 Technology Stack

| Component | Technology | Version | Rationale |
|-----------|------------|---------|-----------|
| Language | Python | 3.11+ | Type hints, async, ecosystem |
| Package Manager | PDM | Latest | Modern, lockfile, PEP 621 |
| HTTP Server | AIOHTTP | 3.9+ | Async, lightweight, mature |
| Telegram SDK | python-telegram-bot | 21+ | Async, well-maintained |
| HTTP Client | httpx | 0.27+ | Async, HTTP/2, modern |
| Config | pydantic-settings | 2.0+ | Validation, .env support |
| Logging | structlog | 24.0+ | JSON, correlation ID native |
| X Extraction | httpx + custom | - | Port of baoyu-skills GraphQL |
| Web Extraction | trafilatura | 1.12+ | Best for articles/blogs |
| Browser Fallback | playwright | 1.40+ | Stealth mode for X |
| STT | faster-whisper | 1.0+ | CTranslate2, M4 optimized |
| Markdown | python-frontmatter | 1.1+ | YAML frontmatter parsing |
| Testing | pytest + pytest-asyncio | 8.0+ | Async test support |
| Linting | ruff | 0.5+ | Fast, replaces flake8+isort+black |
| Type Checking | mypy | 1.10+ | Strict mode |
| Container | Docker + Compose | 24+ | Isolation, reproducibility |
| Sync | Syncthing | 1.27+ | P2P, encrypted, no cloud |

### 13.2 Python Dependencies

```toml
[project]
name = "jarvis"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    # Core
    "aiohttp>=3.9",
    "python-telegram-bot>=21",
    "httpx>=0.27",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    
    # Logging
    "structlog>=24.0",
    
    # Content extraction
    "trafilatura>=1.12",
    "playwright>=1.40",
    
    # Voice
    "faster-whisper>=1.0",
    
    # Storage
    "python-frontmatter>=1.1",
    "aiofiles>=24.0",
    
    # Utils
    "python-slugify>=8.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "ruff>=0.5",
    "mypy>=1.10",
    "pre-commit>=3.7",
]
```

### 13.3 File Structure (Phase 1 - Simplified)

```
jarvis/
|-- src/
|   |-- jarvis/
|   |   |-- __init__.py
|   |   |-- __main__.py              # Entry point: start bot
|   |   |-- config.py                # pydantic-settings (env vars)
|   |   |-- logging.py               # structlog setup
|   |   |-- bot.py                   # Telegram bot (python-telegram-bot)
|   |   |-- opencode_client.py       # HTTP client for OpenCode Server
|   |   `-- formatter.py             # Response formatting for Telegram
|
|   `-- py.typed                     # PEP 561 marker
|
|-- tests/
|   |-- __init__.py
|   |-- conftest.py                  # pytest fixtures
|   |-- test_jarvis_bot_polling.py   # Telegram bot tests
|   `-- test_opencode_client.py      # OpenCode API tests
|
|-- data/                            # Runtime data (Phase 2+)
|   `-- .gitkeep
|
|-- docs/
|   |-- what-i-want.md               # (existing)
|   |-- jarvis-ideal.md              # (existing)
|   |-- prd.md                       # This document
|   `-- deployment.md                # Deployment guide
|
|-- docker-compose.yml
|-- Dockerfile
|-- pyproject.toml
|-- .env.example
|-- .pre-commit-config.yaml
|-- .gitignore                       # (existing)
|-- LICENSE                          # (existing)
`-- AGENTS.md                        # OpenCode project config
```

**Phase 1 Files**:
- `bot.py`: ~200 lines, handles Telegram webhook/polling, user allowlist, message routing
- `opencode_client.py`: ~150 lines, HTTP client for OpenCode Server API
- `config.py`: ~50 lines, pydantic-settings for env vars
- `formatter.py`: ~100 lines, chunk responses, format markdown for Telegram

