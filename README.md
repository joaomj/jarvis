# Jarvis

Personal AI assistant accessible via Telegram, powered by OpenCode.

> **Disclaimer**: This project uses OpenCode but is not built by the OpenCode team 
> and is not affiliated with [OpenCode](https://opencode.ai) in any way.

## What is Jarvis?

Jarvis is a thin Telegram bridge that lets you interact with OpenCode from your 
iPhone. Instead of using the terminal TUI, you chat with a Telegram bot that 
forwards your messages to OpenCode Server.

## Features

**Phase 1 (Current - MVP)**:
- Chat with OpenCode AI via Telegram
- All OpenCode commands work: `/undo`, `/share`, `/compact`, `/new`, etc.
- File references work: `explain @jarvis/src/config.py`
- Bash commands work: `!ls -la`
- Single user security (Telegram ID allowlist)
- Webhook mode via Tailscale Funnel (fast, low latency)

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

4. Start:
   ```bash
   docker compose up -d
   ```

5. Setup Tailscale Funnel for webhook:
   ```bash
   tailscale funnel --bg 8080
   # Get your URL from: tailscale funnel status
   # Update TELEGRAM_WEBHOOK_URL in .env
   docker compose restart jarvis
   ```

6. Message your bot on Telegram!

## Architecture

```
iPhone -> Telegram -> [Jarvis Bot] -> [OpenCode Server] -> LLM
                           |                  |
                           v                  v
                      User allowlist     Your ~/projects
```

Jarvis is a **pure passthrough** - no command interpretation, no custom logic.
All intelligence lives in OpenCode Server.

### How It Works

1. **You type a message in Telegram** on your iPhone
2. **Telegram servers** send it to your Mac Mini (via Tailscale)
3. **Jarvis Bot** receives it, checks if you're allowed
4. **Jarvis forwards** to OpenCode: "hey, user said X"
5. **OpenCode** processes it (calls LLM, reads files, etc.)
6. **OpenCode returns** the response to Jarvis
7. **Jarvis formats** it for Telegram and sends it back
8. **You see the response** on your iPhone

## Configuration

See `.env.example` for all configuration options.

### Telegram Mode: Webhook (Default)

**Webhook (Default - Fast, Low Latency)**
- Pros: Lower latency, instant delivery
- Setup: Requires Tailscale Funnel for HTTPS URL
- Best for: All deployments - fast and responsive

**Polling (Alternative)**
- Pros: No public URL needed, works behind firewalls
- Cons: Higher latency (~1-2s), constant connection
- Best for: Initial testing only

## Development

```bash
# Install dependencies
pdm install

# Run locally (without Docker)
TELEGRAM_BOT_ID=xxx TELEGRAM_USER_ID=123 TELEGRAM_WEBHOOK_URL=https://... pdm run python -m jarvis

# Run tests
pdm run pytest

# Lint
pdm run ruff check .
```

## Documentation

- [Product Requirements Document](docs/prd/) - Full specification (20 sections)
- [Technical Context](docs/tech-context.md) - Architecture decisions

## Security

- **Network**: No public ports, Tailscale mesh VPN only
- **Authentication**: Telegram user ID allowlist (silent ignore for unauthorized)
- **Secrets**: `.env` file, never committed to git
- **Logging**: Structured JSON with correlation IDs, secrets filtered

## License

MIT License - see [LICENSE](LICENSE)

## Acknowledgments

- [OpenCode](https://opencode.ai) - The AI coding assistant that powers Jarvis
- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram bot framework
- [Orbstack](https://orbstack.dev) - Fast, lightweight Docker alternative for Mac
