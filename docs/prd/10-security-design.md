
## 10. Security Design

### 10.1 Threat Model

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| Telegram bot token leaked | Medium | High | Allowlist, rate limit, monitoring |
| Unauthorized user access | Medium | Medium | User ID allowlist (silent ignore) |
| X account restricted | Medium | Low | Fallback to Playwright, cookie rotation |
| Mac Mini compromised via bot | Low | Critical | No public ports, Tailscale only |
| Secrets in logs | Medium | High | structlog filtering, no secrets logged |
| Data exfiltration | Low | Medium | Syncthing encryption, local storage |

### 10.2 Security Controls

```
+-----------------------------------------------------------------------------+
|                              SECURITY LAYERS                                 |
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  | LAYER 1: NETWORK                                                        | |
|  |                                                                         | |
|  |  [x] No public ports exposed                                           | |
|  |  [x] Tailscale mesh VPN (100.x.x.x addresses only)                     | |
|  |  [x] Telegram webhook via Tailscale Funnel (HTTPS)                     | |
|  |  [x] Internal services communicate via Docker network                   | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  | LAYER 2: AUTHENTICATION                                                 | |
|  |                                                                         | |
|  |  [x] Telegram user ID allowlist (env: TELEGRAM_ALLOWED_USERS)          | |
|  |  [x] Unauthorized requests silently ignored (no response)               | |
|  |  [x] All auth failures logged with user info                           | |
|  |  [x] OpenCode server password (env: OPENCODE_SERVER_PASSWORD)          | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  | LAYER 3: AUTHORIZATION                                                  | |
|  |                                                                         | |
|  |  [x] Rate limiting: 10 requests/minute per user                        | |
|  |  [x] Command allowlist (no arbitrary shell execution)                   | |
|  |  [x] File write restricted to data/ directory                          | |
|  |  [x] No email/X write operations (read-only external access)           | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  | LAYER 4: DATA PROTECTION                                                | |
|  |                                                                         | |
|  |  [x] Secrets in .env only (never in code, configs, or logs)            | |
|  |  [x] X cookies encrypted at rest                                       | |
|  |  [x] Private mode: /private messages not logged                        | |
|  |  [x] Log sanitization (filter sensitive patterns)                      | |
|  |  [x] Syncthing encryption for sync (optional)                          | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  | LAYER 5: AUDIT                                                          | |
|  |                                                                         | |
|  |  [x] All requests logged with correlation ID                           | |
|  |  [x] All LLM API calls logged (tokens, duration, model)                | |
|  |  [x] All file writes logged                                            | |
|  |  [x] Failed auth attempts logged with context                          | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
+------------------------------------------------------------------------------+
```

### 10.3 Secret Management

| Secret | Storage | Rotation |
|--------|---------|----------|
| `TELEGRAM_BOT_TOKEN` | .env | On compromise |
| `OPENCODE_ZEN_API_KEY` | .env | Monthly |
| `OPENCODE_SERVER_PASSWORD` | .env | On compromise |
| `X_AUTH_TOKEN` | data/config/x-cookies.json (encrypted) | On expiry |
| `X_CT0` | data/config/x-cookies.json (encrypted) | On expiry |

---
