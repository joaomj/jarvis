# Jarvis

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-supported-2496ED?logo=docker)](https://www.docker.com/)

Personal AI assistant accessible via Telegram. Chat with OpenCode AI from your phone, query X bookmarks naturally, no public URLs required.

> **Disclaimer**: This project uses OpenCode but is not built by the OpenCode team
> and is not affiliated with [OpenCode](https://opencode.ai) in any way.

## Quick Start

```bash
# Clone and configure
git clone https://github.com/yourusername/jarvis.git
cd jarvis
cp .env.example .env
# Edit .env with your tokens (see Configuration below)

# Start services
./scripts/start-opencode.sh          # Terminal A: OpenCode server
docker compose up -d jarvis          # Terminal B: Jarvis bot

# Done! Message your bot on Telegram
```

## Features

- Chat with OpenCode AI via Telegram
- All OpenCode commands: `/compact`, `/undo`, `/redo`, `/share`, etc.
- File references: `explain @src/config.py`
- Bash commands: `!ls -la`
- X bookmarks sync with natural language queries
- Auto-retrieval with hybrid search (FTS5 + sqlite-vec + RRF fusion)
- Attachment ingestion and indexing
- Source-grounded answers with citations
- Single-user security
- Polling mode -- runs locally, no public URLs

## Usage Examples

### Chat with AI
```
You: Explain the bug in src/auth.py
Jarvis: [AI analyzes code]

You: /compact
Jarvis: [Conversation compacted]
```

### Query X Bookmarks
```
You: What did I save last week?
Jarvis: Bookmarks from last week (12 total)...

You: What did I bookmark about AI?
Jarvis: Bookmarks matching "AI" (8 total)...
```

### Save and Retrieve URLs
```
You: /save https://example.com/article
Jarvis: Saved and indexed.

You: Find that article about Rust async
Jarvis: [grounded answer from saved content with citations]
```

### Private Mode
```
You: private: what do you think about this idea?
Jarvis: [replies without logging or retrieving context]
```

### Attachments
```
You: [attach notes.txt] what does this say?
Jarvis: [grounded answer from attachment content]
```

## Commands

**Local Commands:** `/models`, `/new`, `/sessions`, `/save <url>`, `/model <provider/model>`

**OpenCode Commands:** `!compact`, `!undo`, `!share`, etc. (forwarded to OpenCode)

**Blocked (TUI-only):** `/exit`, `/editor`, `/themes`

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Required
TELEGRAM_BOT_ID=your_bot_token_here          # from @BotFather
TELEGRAM_USER_ID=123456789                   # from @userinfobot
OPENCODE_URL=http://localhost:4096
OPENCODE_SERVER_PASSWORD=secure_password_here

# Optional: X Bookmarks (OAuth 2.0)
X_CLIENT_ID=your_x_client_id_here
X_CLIENT_SECRET=your_x_client_secret_here
```

See [Technical Context](docs/tech-context.md#configuration) for all environment variables.

## Deployment

### Docker (Recommended)

```bash
# 1. Start OpenCode server on host
./scripts/start-opencode.sh

# 2. Start Jarvis in Docker
docker compose up -d jarvis

# 3. Follow logs
docker compose logs -f jarvis
```

To stop: `docker compose stop jarvis`

### Development

```bash
# Install dependencies
pdm install

# Run locally
pdm run python -m jarvis

# Run tests
pdm run pytest

# Run tests with coverage
pdm run pytest --cov=src/jarvis --cov-report=term-missing

# Lint
pdm run ruff check .
pdm run ruff format .
```

### Backups

- **Database:** `vault/index/jarvis.db`
- **Vault:** `vault/` directory (raw content and indexes)
- **Config:** `.env` file (contains secrets)

### Monitoring

- Container health status
- Structured JSON logs with correlation IDs
- Key metrics: sync status, query performance, error rates

## Documentation

- [Technical Context](docs/tech-context.md) -- Architecture, state machines, design decisions, security
- [Database Schema](docs/database-schema.md) -- SQLite table and index reference
- [Roadmap](docs/roadmap.md) -- Implementation phases and future plans

## License

MIT License -- see [LICENSE](LICENSE)

## Acknowledgments

- [OpenCode](https://opencode.ai) -- The AI coding assistant that powers Jarvis
- [python-telegram-bot](https://python-telegram-bot.org/) -- Telegram bot framework
