
## 11. Observability Design

### 11.1 Logging Strategy

Following the anti-pattern guidance: **No verbose transaction logs**. Only log:
- Request completion (with metrics)
- Errors and warnings
- Security events

```python
# GOOD: Structured, minimal, actionable
logger.info("summarize_complete",
    correlation_id=ctx.correlation_id,
    url=url,
    source="x",
    duration_ms=2500,
    tokens_used=1200,
    article_saved="x-2026-01-31-karpathy.md")

# BAD: Verbose, not actionable
logger.info("Starting summarization...")
logger.info("Fetching URL...")
logger.info("Calling OpenCode API...")
logger.info("Parsing response...")
```

### 11.2 Log Levels

| Level | Usage | Example |
|-------|-------|---------|
| DEBUG | Development only, disabled in prod | Internal state, variable values |
| INFO | Normal operations completion | `summarize_complete`, `chat_response_sent` |
| WARNING | Recoverable issues | `x_api_rate_limited`, `opencode_slow_response` |
| ERROR | Failures requiring attention | `extraction_failed`, `opencode_unreachable` |

### 11.3 Correlation ID Flow

```
Telegram Request
       |
       v
   +---------------------------------------+
   | Gateway: Generate correlation_id      |
   | correlation_id = "req-abc-123-def"    |
   +---------------------------------------+
       |
       | Pass in context
       v
   +---------------------------------------+
   | All downstream calls include:         |
   | - Log entries                         |
   | - OpenCode requests (X-Correlation-ID)|
   | - Storage metadata                    |
   | - Error reports                       |
   +---------------------------------------+
       |
       v
   +---------------------------------------+
   | Response includes correlation_id      |
   | for debugging                         |
   +---------------------------------------+
```

### 11.4 Metrics (Future FluentBit Integration)

| Metric | Type | Description |
|--------|------|-------------|
| `jarvis_requests_total` | Counter | Total requests by command |
| `jarvis_request_duration_ms` | Histogram | Request latency distribution |
| `jarvis_extraction_errors_total` | Counter | Content extraction failures |
| `jarvis_opencode_latency_ms` | Histogram | OpenCode API latency |
| `jarvis_whisper_transcriptions_total` | Counter | Voice transcriptions |

---
