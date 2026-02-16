
## 14. Dependencies and Third-Party Integrations

### 14.1 External Services

| Service | Purpose | Auth Method | Rate Limits |
|---------|---------|-------------|-------------|
| Telegram Bot API | User interface | Bot token | 30 msg/sec |
| OpenCode Zen | LLM provider | API key | Per plan |
| X (Twitter) | Content extraction | Cookies | ~300 req/15min |
| Syncthing | Data sync | Device ID | N/A |

### 14.2 X Authentication Flow

```
+-----------------------------------------------------------------------------+
|                          X COOKIE AUTHENTICATION                             |
|                                                                              |
|  OPTION 1: Environment Variables (Recommended)                              |
|  ---------------------------------------------------------------------------  |
|                                                                              |
|  1. Log into x.com in browser                                               |
|  2. Open DevTools -> Application -> Cookies -> x.com                           |
|  3. Copy values:                                                             |
|     - auth_token -> X_AUTH_TOKEN                                             |
|     - ct0 -> X_CT0                                                           |
|  4. Add to .env file                                                        |
|                                                                              |
|  OPTION 2: Browser Login (Fallback)                                         |
|  ---------------------------------------------------------------------------  |
|                                                                              |
|  1. Run: python scripts/setup-x-cookies.py                                  |
|  2. Browser opens, log into X                                               |
|  3. Cookies automatically extracted and saved                               |
|                                                                              |
|  Cookie Storage: data/config/x-cookies.json (encrypted)                     |
|  Refresh: When 401 received, prompt for re-auth                             |
|                                                                              |
+------------------------------------------------------------------------------+
```

---
