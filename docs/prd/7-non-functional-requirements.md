
## 7. Non-Functional Requirements

### 7.1 Performance

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | URL summarization latency | <30 seconds |
| NFR-2 | Voice transcription latency | <10 seconds |
| NFR-3 | Chat response latency | <15 seconds |
| NFR-4 | Concurrent request handling | 3 simultaneous |
| NFR-5 | Memory usage (idle) | <500 MB |
| NFR-6 | Memory usage (Whisper active) | <2 GB |

### 7.2 Reliability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-7 | Uptime (Mac Mini powered on) | 99% |
| NFR-8 | Graceful degradation if OpenCode unavailable | Yes |
| NFR-9 | Auto-restart on crash | Docker restart policy |
| NFR-10 | Data durability | Syncthing replication |

### 7.3 Security

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-11 | Authentication | Telegram user ID allowlist |
| NFR-12 | Network exposure | Tailscale only, no public ports |
| NFR-13 | Secrets management | .env file, never in code/logs |
| NFR-14 | Rate limiting | 10 req/min per user |
| NFR-15 | Audit logging | All actions logged with correlation ID |

### 7.4 Observability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-16 | Structured logging format | JSON |
| NFR-17 | Log level control | DEBUG/INFO/WARN/ERROR |
| NFR-18 | Correlation ID propagation | All log entries |
| NFR-19 | Log destination | stdout, file rotation |
| NFR-20 | Future extensibility | FluentBit-ready |

### 7.5 Maintainability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-21 | Code style | Ruff (format + lint) |
| NFR-22 | Type checking | MyPy strict |
| NFR-23 | Test coverage | >70% for core modules |
| NFR-24 | Documentation | Docstrings + deployment guide |
| NFR-25 | Max file length | 300 lines |

---
