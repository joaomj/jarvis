
## 16. Risks and Mitigations

### 16.1 Technical Risks

| Risk | Probability | Impact | Mitigation | Contingency |
|------|-------------|--------|------------|-------------|
| X API changes break extraction | High | Medium | Abstract extractor interface | Playwright fallback |
| X rate limits/bans | Medium | Medium | Respectful rate limiting, rotating IPs (future) | Manual paste mode |
| Whisper too slow on M4 | Low | Low | Use `small` model | Switch to `base` |
| OpenCode API changes | Low | High | Pin version, monitor releases | Direct LLM API calls |
| Telegram webhook unreliable | Low | Medium | Health checks, auto-reconnect | Polling fallback |
| Syncthing conflicts | Low | Low | JSONL append-only, write-once articles | Manual merge |

### 16.2 Operational Risks

| Risk | Probability | Impact | Mitigation | Contingency |
|------|-------------|--------|------------|-------------|
| Mac Mini offline | Medium | High | UPS, monitoring | VPS backup (future) |
| Secret leak via logs | Medium | High | structlog filtering, audit | Rotate secrets |
| Disk full | Low | Medium | Log rotation, article limits | Expand SSD |
| Tailscale down | Low | Medium | Multiple access methods | Direct Tailscale IP |

### 16.3 Security Risks

| Risk | Probability | Impact | Mitigation | Contingency |
|------|-------------|--------|------------|-------------|
| Bot token compromised | Low | High | Allowlist, rate limit | Revoke + regenerate |
| Unauthorized access | Medium | Medium | User ID allowlist, silent ignore | Review logs, block |
| X cookies stolen | Low | Medium | Encrypted storage | Re-authenticate |

---
