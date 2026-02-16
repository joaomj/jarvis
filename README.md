# Jarvis

Personal AI assistant accessible via Telegram, powered by OpenCode.

> **Disclaimer**: This project uses OpenCode but is not built by the OpenCode team
> and is not affiliated with [OpenCode](https://opencode.ai) in any way.

## What is Jarvis?

Jarvis is a Telegram bot that forwards messages to OpenCode Server. It runs in polling
mode (no public URLs needed) and provides a seamless chat experience from your phone.

## Features

**Phase 1 (Current - MVP)**:
- Chat with OpenCode AI via Telegram
- All OpenCode commands work: `/compact`, `/undo`, `/redo`, `/share`, `/thinking`, etc.
- File references work: `explain @src/config.py`
- Bash commands work: `!ls -la`
- Single user security (Telegram ID allowlist via SQLite)
- Model selection from favorites: `/models` or `!models`
- Response logging with model and agent info (SQLite database)
- Bot token security (httpx logs filtered)
- **Polling mode** - runs entirely locally, no Tailscale required
- Modular architecture with command routing
- Message audit trail
- Auto-cleanup of old responses (30 days)
- Comprehensive error handling with detailed diagnostics
- **X bookmarks sync and query**: Automatic daily sync, natural language queries

**Phase 2 (Planned)**:
- URL summarization (X threads, Substack articles)
- Voice message transcription

## Quick Start

### Prerequisites

- Mac with [Orbstack](https://orbstack.dev) or Docker
- Telegram account
- OpenCode Zen API key

### Setup

1. Clone and configure:
   ```bash
   git clone https://github.com/yourusername/jarvis.git
   cd jarvis
   cp .env.example .env
   # Edit .env with your tokens
   ```

2. Create Telegram bot:
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Run `/newbot` and follow prompts
   - Copy the token to `.env`

3. Get your Telegram user ID:
   - Message [@userinfobot](https://t.me/userinfobot) on Telegram
   - Copy your ID to `.env`

4. Configure favorite models:
   ```bash
   mkdir -p .jarvis
   # Edit .jarvis/favorite_models.json with your preferred models
   ```

5. Start:
   ```bash
   docker compose up -d
   ```

6. Message your bot on Telegram!

## X Bookmarks Feature

Jarvis automatically syncs your X (Twitter) bookmarks and lets you query them naturally.

### Setup X Bookmarks

1. Get X API Bearer token:
   - Go to [developer.twitter.com](https://developer.twitter.com)
   - Create a free developer account
   - Create a project and app
   - Copy the "Bearer Token" (read-only scope)

2. Add token to `.env`:
   ```bash
   X_BEARER_TOKEN=your_bearer_token_here
   ```

3. Restart Jarvis:
   ```bash
   docker compose restart
   ```

### How It Works

- **Auto-sync**: Syncs automatically on first message of each day
- **Incremental**: Only fetches new bookmarks since last sync
- **Local storage**: All bookmarks stored in SQLite database
- **Natural language queries**: Ask in plain English

### Query Examples

Query your bookmarks with natural language:

```
What did I save last week?
Show me my recent bookmarks
My bookmarks from yesterday
What did I bookmark about AI?
Saved posts from last month
```

### What You Can Ask

- **Time ranges**: last week, yesterday, today, last month, recent
- **Keywords**: saved, bookmarked, my tweets, my bookmarks, saved posts
- **Topics**: "What did I save about Python?" (simple text search for now)

### Limitations

- Sync happens once per day (not real-time)
- Query results show max 10 bookmarks at a time
- Topic search is text-based (semantic search coming soon)
- Bookmarks stored indefinitely (no automatic cleanup)

## Architecture

```
iPhone -> Telegram -> [Jarvis Bot] -> [OpenCode Server] -> LLM
                           |                  |
                           v                  v
                      SQLite DB           Your ~/projects
```

Jarvis is a **pure passthrough** - minimal interpretation, all intelligence in OpenCode.

### Error Handling Strategy

Jarvis implements comprehensive error handling with three severity levels:

| Severity | Behavior | Examples |
|----------|----------|----------|
| **FATAL** | Logs critical error, raises exception, bot exits | Database initialization, user authorization check |
| **WARNING** | Logs warning with context, continues operation | Message audit logging, response logging, user state management |
| **USER ERROR** | Returns user-friendly error message, logs details | Invalid commands, malformed input |

All errors are logged with structured context (user_id, session_id, operation) for debugging.

### How It Works

1. **You type a message in Telegram** on your iPhone
2. **Jarvis Bot** receives it via polling, checks if you're allowed
3. **Jarvis forwards** to OpenCode: "hey, user said X"
4. **OpenCode** processes it (calls LLM, reads files, etc.)
5. **OpenCode returns** the response to Jarvis
6. **Jarvis formats** it for Telegram and sends it back
7. **You see the response** on your iPhone

## Configuration

See `.env.example` for all configuration options.

### X Bookmarks Configuration

| Variable | Description | Example |
|----------|-------------|----------|
| `X_BEARER_TOKEN` | X API read-only bearer token (optional) | `AAAAAAAA...` |

**Get your token:**
1. Go to [developer.twitter.com](https://developer.twitter.com)
2. Create a free developer account
3. Create a project and app
4. Copy the "Bearer Token" (read-only scope)

**Why read-only?**
- Bookmarks are public to you anyway
- No write access means no accidental tweets/deletes
- Safer than full OAuth with write permissions

### Polling Configuration

Jarvis uses long polling - it continuously checks Telegram for new messages:

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_POLLING_INTERVAL` | 2.0 | Seconds between polling requests |
| `TELEGRAM_POLLING_TIMEOUT` | 30 | Timeout for getUpdates in seconds |

Lower interval = faster response but more API calls.

### Model Selection

Jarvis uses favorite models configured in `.jarvis/favorite_models.json`:

```json
[
  "anthropic/claude-sonnet-4-20250514",
  "openai/gpt-4o",
  "google/gemini-2.5-pro"
]
```

Use `/models` or `!models` to select a model for your session. The preference is stored
per-user in SQLite and used for all subsequent messages.

### Database

SQLite database at `.jarvis/jarvis.db` stores:
- Authorized users
- Message audit trail
- Response logs with model info
- User states (e.g., awaiting model selection)
- X bookmarks (tweets, authors, metrics, URLs)
- X sync status (last sync date, total count, last tweet ID)

## Commands

### OpenCode Commands (pass-through)

These are forwarded to OpenCode Server:

| Command | Description |
|---------|-------------|
| `/compact` | Compact conversation |
| `/summarize` | Summarize conversation |
| `/details` | Show task details |
| `/export` | Export conversation |
| `/undo` | Undo last change |
| `/redo` | Redo last change |
| `/share` | Share session |
| `/unshare` | Unshare session |
| `/thinking` | Toggle thinking display |
| `/connect` | Connect to repository |
| `/help` | Show help |

### Bridge Commands (handled locally)

These are processed by Jarvis:

| Command | Description |
|---------|-------------|
| `/models` | Show and select favorite models |
| `/new [title]` | Create new session |
| `/sessions` | List your sessions |
| `/switch <id>` | Switch to session |
| `/agent [get/set]` | Show/set agent info |
| `/model [provider/model]` | Show or set model |

### Native Shortcuts

| Command | Description |
|---------|-------------|
| `!models` | Same as `/models` |
| `!favmodels` | Same as `/models` |
| `!<cmd>` | Forward any command to OpenCode |

### X Bookmarks Queries (Natural Language)

No commands needed - just ask naturally:

| Query | Description |
|--------|-------------|
| "What did I save last week?" | Bookmarks from past 7 days |
| "Show me my recent bookmarks" | Recent bookmarks |
| "My bookmarks from yesterday" | Bookmarks from yesterday |
| "What did I bookmark about AI?" | Bookmarks mentioning AI |
| "Saved posts from last month" | Bookmarks from past 30 days |

## Development

```bash
# Install dependencies
pdm install

# Run locally (without Docker)
pdm run python -m jarvis

# Run tests
pdm run pytest

# Lint
pdm run ruff check .
```

## Testing

### 1. Run All Tests
```bash
pdm run pytest -v
```

### 2. Run Specific Tests
```bash
# Test OpenCode client error handling
pdm run pytest tests/test_opencode_client.py -v

# Test bot functionality
pdm run pytest tests/test_bot.py -v

# Test response formatting
pdm run pytest tests/test_formatter.py -v

# Test bookmarks functionality
pdm run pytest tests/test_bookmarks.py -v
```

### 3. Test with Live OpenCode Server
```bash
# Ensure OpenCode server is running
curl http://localhost:4096/global/health

# Run bot in test mode
TELEGRAM_BOT_ID=test TELEGRAM_USER_ID=12345 \
  OPENCODE_URL=http://localhost:4096 \
  OPENCODE_SERVER_PASSWORD=test \
  pdm run python -c "
from jarvis.bot import JarvisBot
from jarvis.config import Settings
import asyncio

settings = Settings(
    telegram_bot_id='test',
    telegram_user_id=12345,
    opencode_url='http://localhost:4096',
    opencode_server_password='test'
)
bot = JarvisBot(settings)

async def test():
    healthy, reason = await bot.opencode.health_check()
    print(f'OpenCode health: {healthy}, reason: {reason}')
    if healthy:
        session = await bot.opencode.create_session('Test Session')
        print(f'Created session: {session}')

asyncio.run(test())
"
```

### 4. Manual Telegram Testing
After starting with `docker compose up -d`:

1. Message your bot with `/models` or `!models` - shows favorite models
2. Reply with model number to set your preference
3. Send a regular message - uses your selected model
4. Try `/compact` - compacts conversation
5. Test bookmarks (if configured): "What did I save last week?"

## Documentation

- [Product Requirements Document](docs/prd/) - Full specification (20 sections)
- [Technical Context](docs/tech-context.md) - Architecture decisions, data flows, system patterns
- [CHANGELOG.md](CHANGELOG.md) - History of changes and new features

## Security

- **Network**: No public ports, polling only (no webhook)
- **Authentication**: Telegram user ID allowlist (silent ignore for unauthorized)
- **Secrets**: `.env` file, never committed to git
- **Logging**: Structured JSON with correlation IDs, secrets filtered
- **Container**: Read-only filesystem, resource limits, no new privileges
- **Database**: SQLite stored in `.jarvis/` directory

## License

MIT License - see [LICENSE](LICENSE)

## Acknowledgments

- [OpenCode](https://opencode.ai) - The AI coding assistant that powers Jarvis
- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram bot framework
- [Orbstack](https://orbstack.dev) - Fast, lightweight Docker alternative for Mac
