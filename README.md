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

See [Deployment Guide](docs/reference/deployment.md) for detailed setup instructions.

## Features

- 📱 Chat with OpenCode AI via Telegram
- 🔄 All OpenCode commands: `/compact`, `/undo`, `/redo`, `/share`, etc.
- 📁 File references: `explain @src/config.py`
- 💻 Bash commands: `!ls -la`
- 📚 X bookmarks sync with natural language queries
- 🧠 Curated memory stored in local `vault/`
- 📎 Attachment ingestion and indexing
- 🔎 Source-grounded answers with citations
- 🔒 Single-user security
- 🚀 Polling mode - runs locally, no public URLs

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

### Memory and Attachments
```
You: remember I prefer concise summaries
Jarvis: Saved to memory.

You: [attach notes.txt] what does this say?
Jarvis: [grounded answer with citations]
```

## Commands

**Local Commands:** `/models`, `/new`, `/sessions`

**Jarvis Commands:** `/save <url>`, `/recall <query>`

**OpenCode:** `!compact`, `!undo`, `!share`, etc.

See [Command Reference](docs/reference/commands.md) for complete documentation.

## Documentation

- [Quick Start](#quick-start) - Get running in minutes
- [Deployment Guide](docs/reference/deployment.md) - Production and development setup
- [Configuration](docs/reference/configuration.md) - Environment variables and settings
- [Technical Context](docs/tech-context.md) - Architecture and design decisions
- [Roadmap](docs/ROADMAP.md) - Implementation phases and future plans
- [Database Schema](docs/reference/database-schema.md) - SQLite table reference
- [Security](docs/reference/security.md) - Security model

## Development

```bash
# Install dependencies
pdm install

# Run locally
pdm run python -m jarvis

# Run tests
pdm run pytest

# Lint
pdm run ruff check .
```

See [Deployment Guide](docs/reference/deployment.md) for full development setup.

## License

MIT License - see [LICENSE](LICENSE)

## Acknowledgments

- [OpenCode](https://opencode.ai) - The AI coding assistant that powers Jarvis
- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram bot framework
