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
# Edit .env with your tokens

# Create Telegram bot
# Message @BotFather on Telegram, run /newbot
# Copy token to .env as TELEGRAM_BOT_ID

# Get your Telegram user ID
# Message @userinfobot on Telegram
# Copy ID to .env as TELEGRAM_USER_ID

# Terminal A: start local OpenCode server (as used in this repo)
chmod +x scripts/start-opencode.sh
./scripts/start-opencode.sh

# Terminal B: start Jarvis container
docker compose up -d jarvis

# Done! Message your bot on Telegram
```

## Local Run (OpenCode local + Jarvis Docker)

This is the setup used on this machine:

```bash
# 1) Start OpenCode server on host
./scripts/start-opencode.sh

# 2) Start Jarvis in Docker
docker compose up -d jarvis

# 3) Follow Jarvis logs
docker logs -f jarvis
```

To stop:

```bash
docker compose stop jarvis
```

Note: `scripts/start-opencode.sh` currently contains local absolute paths. If your workspace path differs, update that script first.

## Features

**Current:**
- 📱 Chat with OpenCode AI via Telegram from anywhere
- 🔄 All OpenCode commands work: `/compact`, `/undo`, `/redo`, `/share`, `/thinking`, etc.
- 📁 File references work: `explain @src/config.py`
- 💻 Bash commands work: `!ls -la`
- 🎛️ Model selection: `/models` or `!models` to pick favorites
- 📚 X bookmarks sync: Automatic daily sync, natural language queries
- 🧠 Curated memory: remember/forget/recall flows stored in local `vault/`
- 📎 Attachment ingestion: text attachments are saved to `vault/` and indexed for retrieval
- 🔎 Source-grounded fallback: when local evidence is insufficient, Jarvis can synthesize with cited web sources
- 📄 Deep research orchestration: explicit confirmation + staged OpenCode subagent pipeline with local report artifacts
- 🔒 Single-user security (Telegram ID allowlist)
- 📊 Response logging with model info
- 🧹 Auto-cleanup (30 days)
- 🚀 Polling mode - runs locally, no Tailscale needed

**Next:**
- Rich extraction for non-text attachments (PDF-focused ingestion)
- Better retrieval quality tuning (hybrid/rerank if needed)

## Usage

### Chat with AI

```
You: Explain the bug in src/auth.py
Jarvis: [AI analyzes code, provides explanation]

You: /compact
Jarvis: [Conversation compacted]

You: !ls -la
Jarvis: [Shows directory listing]
```

### Query X Bookmarks

Jarvis automatically syncs your X bookmarks and lets you query them naturally.

```
You: What did I save last week?
Jarvis: 📚 Bookmarks from last week (12 total)
   1. @author1
      Preview of first tweet...
   2. @author2
      Preview of second tweet...

You: Show me my recent bookmarks
Jarvis: 📚 Bookmarks from recent (5 total)
   [...]

You: What did I bookmark about AI?
Jarvis: 📚 Bookmarks matching "AI" (8 total)
   [...]
```

### Memory and Attachments

```
You: remember I prefer concise summaries with references
Jarvis: Saved to memory.

You: what do you remember about summaries?
Jarvis: Here is what I remember: ...

You: [attach notes.txt] what does this say about Tocqueville?
Jarvis: [grounded answer with citations; attachment evidence prioritized]
```

### Deep Research

```
You: Write a deep research report (10 pages) about X and cite sources.
Jarvis: [asks for confirmation]
You: [tap Run deep research]
Jarvis: [runs staged job and returns vault report path]
```

### Commands

**Local Commands** (handled by Jarvis):
| Command | Description |
|---------|-------------|
| `/models` | Show and select favorite models |
| `/new [title]` | Create new session |
| `/sessions` | List your sessions |
| `/model <provider/model>` | Set model directly |

**OpenCode Commands:**
- `!models` - Same as `/models`
- `!favmodels` - Same as `/models`
- `!<cmd>` - Forward any OpenCode command (for example `!undo`, `!compact`, `!share`)

## Requirements

- Python 3.11+
- Docker or Orbstack
- Telegram account
- OpenCode Server running
- OpenCode Zen API key

## Configuration

### Required Environment Variables

```bash
# Telegram Bot Configuration
TELEGRAM_BOT_ID=your_bot_token_here          # From @BotFather
TELEGRAM_USER_ID=123456789                  # From @userinfobot

# OpenCode Server Configuration
OPENCODE_URL=http://localhost:4096              # Your OpenCode Server URL
OPENCODE_SERVER_PASSWORD=secure_password_here      # Your server password
```

### Optional Configuration

```bash
# Polling Configuration
TELEGRAM_POLLING_INTERVAL=1.0                 # Seconds between polls (default)
TELEGRAM_POLLING_TIMEOUT=30                   # Timeout in seconds

# Database & Logging
DATABASE_PATH=.jarvis/jarvis.db
ENABLE_MESSAGE_AUDIT=true
LOG_LEVEL=INFO

# X Bookmarks (Optional, OAuth 2.0)
X_CLIENT_ID=your_x_client_id_here
X_CLIENT_SECRET=your_x_client_secret_here

# Local vault root
VAULT_ROOT=vault

# Enable OpenCode websearch tool when needed
# OPENCODE_ENABLE_EXA=1
```

See `.env.example` for complete configuration options.

### Favorite Models

Create `.jarvis/favorite_models.json`:

```json
[
  "openai/gpt-5.2",
  "zai/glm-4.7",
  "openai/gpt-5.3-codex"
]
```

The first model in the list is used as the default for new sessions.

## Documentation

- **[Technical Context](docs/tech-context.md)** - Architecture, data flows, design decisions
- **[SQL Query Examples](docs/sql-query-examples.md)** - Ready-to-run SQLite queries for local inspection
- **[Product Requirements](docs/prd/)** - Full specification (20 sections)
- **[Changelog](CHANGELOG.md)** - Version history and changes

## Development

```bash
# Install dependencies
pdm install

# Run locally (without Docker)
pdm run python -m jarvis

# Run tests
pdm run pytest

# Run PR gate tiers
pdm run pytest -m "fast or integration"

# Run optional real OpenCode smoke tests
JARVIS_ENABLE_E2E_OPENCODE=1 \
JARVIS_E2E_OPENCODE_URL=http://localhost:4096 \
JARVIS_E2E_OPENCODE_PASSWORD=your_password \
pdm run pytest -m e2e_opencode

# Lint
pdm run ruff check .
```

Shared integration harnesses live under `tests/harness/`:
- `fake_telegram.py` for deterministic Telegram API behavior
- `update_factory.py` for typed message/callback/document update builders
- `fake_opencode_server.py` for in-process JSON/SSE OpenCode contract testing

See [docs/tech-context.md#deployment](docs/tech-context.md#deployment) for detailed development setup.

## Security

- **Network**: No public ports, polling only (no webhook)
- **Authentication**: Telegram user ID allowlist (silent ignore for unauthorized)
- **Secrets**: `.env` file, never committed to git
- **Logging**: Structured JSON with correlation IDs, secrets filtered
- **Container**: Read-only filesystem, resource limits, no new privileges

## License

MIT License - see [LICENSE](LICENSE)

## Acknowledgments

- [OpenCode](https://opencode.ai) - The AI coding assistant that powers Jarvis
- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram bot framework
- [Orbstack](https://orbstack.dev) - Fast, lightweight Docker alternative for Mac
