# Security Model

Security architecture and practices for Jarvis.

## Authentication

**Method:** Telegram user ID allowlist in SQLite database

- Simple, no OAuth complexity
- Works with Telegram's existing auth
- Single user (can be extended to multi-user allowlist)

**Implementation:** `database/users.py::UserManager.is_user_allowed()`

## Network Security

**Method:** Polling only, no public ports, no webhooks

- No attack surface
- No need for Tailscale
- Runs entirely locally
- Bot makes outbound connections only (Telegram API, OpenCode, X API)

**Implementation:** `polling_engine.py`

## Secrets Management

**Method:** `.env` file, never committed to git

- Prevents accidental exposure in commits/logs/GitHub
- All secrets (bot tokens, API keys, passwords) in `.env`
- Filtered from logs

**Implementation:** `config.py` reads from `.env` using pydantic-settings

## Logging Security

**Method:** Structured JSON with secrets filtering

- httpx INFO logs suppressed (documented issue: exposes tokens)
- All logs filtered for known secret patterns before output

**Implementation:** `logging_config.py`

## Container Security

**Method:** Docker multi-stage build with hardening

- Non-root user
- Read-only filesystem (`/app`)
- No new privileges
- Resource limits

## Database Security

**Method:** SQLite file in `vault/index/` directory

- File is gitignored
- No network exposure
- Parameterized queries prevent SQL injection
- Contains user data, bookmarks, responses

**Location:** `vault/index/jarvis.db`

## X OAuth Security

**Method:** OAuth 2.0 PKCE

- Client secret never exposed to browser
- Tokens stored in database (not .env)
- Callback server runs on localhost only (127.0.0.1:8080)
- Auto-refresh before expiration

## Security Checklist

- [ ] `.env` file is in `.gitignore`
- [ ] No secrets in code or logs
- [ ] Database file is backed up
- [ ] Container runs as non-root
- [ ] No public ports exposed
- [ ] OAuth tokens are rotated
