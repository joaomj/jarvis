
## 15. Deployment Architecture

### 15.1 Docker Compose Configuration (Phase 1)

```yaml
version: "3.9"

services:
  # Jarvis Bot - thin Telegram bridge
  jarvis:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: jarvis-bot
    restart: unless-stopped
    environment:
      - JARVIS_ENV=production
      # Telegram
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_ALLOWED_USERS=${TELEGRAM_ALLOWED_USERS}
      - TELEGRAM_MODE=${TELEGRAM_MODE:-polling}  # polling or webhook
      # OpenCode Server
      - OPENCODE_URL=http://opencode:4096
      - OPENCODE_SERVER_PASSWORD=${OPENCODE_SERVER_PASSWORD}
      # Logging
      - LOG_LEVEL=INFO
    depends_on:
      opencode:
        condition: service_healthy

  # OpenCode Server - all intelligence lives here
  opencode:
    image: ghcr.io/anomalyco/opencode:latest
    container_name: jarvis-opencode
    restart: unless-stopped
    command: serve --hostname 0.0.0.0 --port 4096
    environment:
      - OPENCODE_ZEN_API_KEY=${OPENCODE_ZEN_API_KEY}
      - OPENCODE_SERVER_PASSWORD=${OPENCODE_SERVER_PASSWORD}
      # Session metadata storage (keep separate from projects)
      - OPENCODE_HOME=/root/.opencode
    volumes:
      # OpenCode config and session data
      - opencode-config:/root/.config/opencode
      - opencode-data:/root/.opencode
      # Projects directory (host projects mounted here)
      - ~/projects:/projects
    working_dir: /projects
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4096/global/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Syncthing - sync data to other devices (Phase 2+)
  # syncthing:
  #   image: syncthing/syncthing:latest
  #   container_name: jarvis-syncthing
  #   hostname: jarvis-sync
  #   restart: unless-stopped
  #   environment:
  #     - PUID=1000
  #     - PGID=1000
  #   volumes:
  #     - jarvis-data:/var/syncthing/data
  #     - syncthing-config:/var/syncthing/config
  #   ports:
  #     - "8384:8384"   # Web UI (local only)
  #     - "22000:22000" # Sync protocol

volumes:
  # jarvis-data:
  #   driver: local
  #   driver_opts:
  #     type: none
  #     o: bind
  #     device: ${PWD}/data
  opencode-config:
  opencode-data:
  # syncthing-config:

networks:
  default:
    name: jarvis-network
```

### 15.2 Dockerfile (Phase 1)

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

WORKDIR /app

# Install system dependencies (ffmpeg for Phase 2 voice support)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install PDM
RUN pip install --no-cache-dir pdm

# Copy dependency files
COPY pyproject.toml pdm.lock ./

# Install dependencies (production only)
RUN pdm install --prod --no-lock --no-editable

# Copy application
COPY src/ ./src/

# Create non-root user
RUN useradd -m -u 1000 jarvis && chown -R jarvis:jarvis /app
USER jarvis

# No ports exposed - bot uses long-polling or webhook callback
# No healthcheck - bot is a background worker, not a web service

# Run application
CMD ["pdm", "run", "python", "-m", "jarvis"]
```

### 15.3 Tailscale Webhook Setup

```bash
# 1. Install Tailscale on Mac Mini (if not already)
brew install tailscale

# 2. Enable Tailscale Funnel for HTTPS webhook
tailscale funnel --bg 8080

# 3. Get your Funnel URL
tailscale funnel status
# Output: https://jarvis.tailnet-name.ts.net -> http://127.0.0.1:8080

# 4. Set Telegram webhook
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
    -H "Content-Type: application/json" \
    -d '{"url": "https://jarvis.tailnet-name.ts.net/webhook"}'

# 5. Verify webhook
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
```

### 15.4 Environment Variables (Phase 1)

```bash
# .env.example

# Telegram (required)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_ALLOWED_USERS=12345678  # Your Telegram user ID

# Telegram mode: 'polling' (default, no public URL needed) or 'webhook' (requires public URL)
TELEGRAM_MODE=polling

# If using webhook mode, set this:
# TELEGRAM_WEBHOOK_URL=https://jarvis.tailnet-name.ts.net/webhook

# OpenCode Server (required)
OPENCODE_URL=http://opencode:4096
OPENCODE_SERVER_PASSWORD=your-secure-password

# Note on OpenCode Server configuration:
# - OPENCODE_ZEN_API_KEY is configured in the OpenCode container
# - working_dir is set to /projects (mounting ~/projects from host)
# - Session metadata stored in /root/.opencode (OPENCODE_HOME)
# - This gives OpenCode direct access to all your projects via @file references

# Logging (optional)
LOG_LEVEL=INFO
JARVIS_ENV=production

# Phase 2+ Variables (not needed for MVP)
# WHISPER_MODEL=small
# X_AUTH_TOKEN=your-auth-token
# X_CT0=your-ct0-token
```

**Getting Your Telegram User ID**:
1. Message @userinfobot on Telegram
2. Or start the bot and check logs: `docker logs jarvis-bot | grep user_id`

---

### 15.5 Polling vs Webhook Mode

Jarvis supports two modes for receiving Telegram messages:

#### Polling Mode (Default - Recommended for MVP)

**How it works**: Bot constantly asks Telegram servers "any new messages?" 

**Pros**:
- No public URL needed
- Works behind firewalls, NAT, Tailscale
- Simpler setup
- Automatic reconnection on network issues

**Cons**:
- ~1-2 second latency
- Constant network connection
- Slightly higher CPU usage (from polling)

**Best for**: MVP, home networks, testing

#### Webhook Mode (Phase 4)

**How it works**: Telegram pushes messages to your bot when they arrive

**Pros**:
- Near-instant delivery (low latency)
- Lower CPU usage (no polling loop)
- More scalable

**Cons**:
- Requires public HTTPS URL
- More complex setup (Tailscale Funnel)
- Network must be reachable from internet

**Best for**: Production, when low latency matters

#### Switching Between Modes

1. Stop the bot: `docker compose down`
2. Edit `.env` and change `TELEGRAM_MODE`
3. For webhook: set `TELEGRAM_WEBHOOK_URL` to your Tailscale Funnel URL
4. Start: `docker compose up -d`

#### Tailscale Funnel Setup (Webhook)

```bash
# 1. Install Tailscale (if not already)
brew install tailscale

# 2. Enable Funnel for HTTPS webhook
tailscale funnel --bg 8080

# 3. Get your Funnel URL
tailscale funnel status
# Output: https://jarvis.tailnet-name.ts.net -> http://127.0.0.1:8080

# 4. Update .env
TELEGRAM_MODE=webhook
TELEGRAM_WEBHOOK_URL=https://jarvis.tailnet-name.ts.net/webhook

# 5. Restart bot
docker compose up -d
```

**Note**: The bot automatically configures the webhook URL on startup when in webhook mode.

---
