# Alfred

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/badge/package%20manager-uv-4f46e5)](https://github.com/astral-sh/uv)

Personal AI assistant accessible via Telegram. Chat with a PydanticAI-powered butler from your phone.

```
You: What's on my mind today?
Alfred: Based on your memory, you were researching agent architectures...
```

## Features

- **AI chat via Telegram** — poll-based, no public URLs required
- **Alfred persona** — fatherly, dry wit (Nolan's Alfred Pennyworth)
- **Skill system** — extend with plugins (`/deep-research`, `/summarize`, `/private`)
- **Model switching** — change LLM at runtime via `/model` menu
- **Persistent memory** — SOUL.md, MEMORY.md, USER.md stored locally in `soul/`
- **FTS5 conversation search** — full-text search across all past messages
- **Structured logging** — JSON logs with correlation IDs
- **Single-user** — Telegram user ID allowlist
- **Containerized** — Docker Compose ready

## Quick Start

```bash
git clone https://github.com/yourusername/alfred.git
cd alfred
cp .env.example .env
# Edit .env: add TELEGRAM_BOT_TOKEN, TELEGRAM_USER_ID, OPENCODE_GO_API_KEY

# Run locally
uv sync
uv run alfred

# Or with Docker
docker compose up -d
```

## Skills

| Command | Skill | Description |
|---------|-------|-------------|
| `/deep-research <topic>` | Deep Research | Detailed technical reports from trustworthy sources |
| `/summarize <content>` | Summarize | Summarize content, articles, text |
| `/private <message>` | Private | Ask without logging (content truncated in logs) |
| `/model` | — | Switch LLM via inline keyboard |

Alfred is the default persona — no command needed. Just chat.

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# With coverage
uv run pytest --cov=src --cov-report=term-missing

# Lint & type-check
uv run ruff check src/
uv run mypy src/
```

## Configuration

Copy `.env.example` to `.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | From [@BotFather](https://t.me/botfather) |
| `TELEGRAM_USER_ID` | Yes | From [@userinfobot](https://t.me/userinfobot) |
| `OPENCODE_GO_API_KEY` | Yes | From [opencode.ai/auth](https://opencode.ai/auth) |
| `MODEL` | No | Model identifier (default: `opencode-go:deepseek-v4-flash`) |

See [docs/tech-context.md](docs/tech-context.md) for full configuration reference.

## Documentation

- [Technical Context](docs/tech-context.md) — Architecture, design decisions, security
- [Database Schema](docs/database-schema.md) — SQLite schema reference
- [Roadmap](docs/roadmap.md) — Vision and future plans

## License

MIT License — see [LICENSE](LICENSE)
