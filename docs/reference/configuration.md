# Configuration Reference

Environment variables and configuration files for Jarvis.

## Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `TELEGRAM_BOT_ID` | Telegram bot token from @BotFather | `123456:ABC-xyz123` |
| `TELEGRAM_USER_ID` | Your Telegram user ID from @userinfobot | `123456789` |
| `OPENCODE_URL` | OpenCode Server URL | `http://localhost:4096` |
| `OPENCODE_SERVER_PASSWORD` | OpenCode Server password | `secure_password` |

## Optional Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `X_CLIENT_ID` | X OAuth 2.0 Client ID from Developer Console | `None` (bookmarks disabled) |
| `X_CLIENT_SECRET` | X OAuth 2.0 Client Secret from Developer Console | `None` (bookmarks disabled) |
| `X_BEARER_TOKEN` | X API Bearer token (DEPRECATED, use OAuth 2.0) | `None` |
| `TELEGRAM_POLLING_INTERVAL` | Seconds between polling requests | `2.0` |
| `TELEGRAM_POLLING_TIMEOUT` | Timeout for getUpdates in seconds | `30` |
| `LOG_LEVEL` | Python logging level | `INFO` |
| `DATABASE_PATH` | SQLite database file path | `vault/index/jarvis.db` |
| `ENABLE_MESSAGE_AUDIT` | Enable message audit trail | `true` |
| `FAVORITE_MODELS_PATH` | Path to favorite models JSON | `vault/index/favorite_models.json` |

## Configuration Files

### Favorite Models

Create `vault/index/favorite_models.json`:

```json
[
  "openai/gpt-5.2",
  "zai/glm-4.7",
  "openai/gpt-5.3-codex"
]
```

The first model in the list is used as the default for new sessions.

### Environment File

Copy `.env.example` to `.env` and configure:

```bash
# Telegram Bot Configuration
TELEGRAM_BOT_ID=your_bot_token_here
TELEGRAM_USER_ID=123456789

# OpenCode Server Configuration
OPENCODE_URL=http://localhost:4096
OPENCODE_SERVER_PASSWORD=secure_password_here

# X Bookmarks (Optional)
X_CLIENT_ID=your_x_client_id_here
X_CLIENT_SECRET=your_x_client_secret_here
```
