
## 17. Implementation Phases

### 17.1 Phase 1: Telegram-OpenCode Bridge (MVP - Week 1)

**Goal**: Working Telegram bot that forwards messages to OpenCode and returns responses.

| Task | Description | Deliverable | Estimate |
|------|-------------|-------------|----------|
| 1.1 | Project scaffold | pyproject.toml, Dockerfile, docker-compose.yml | 2h |
| 1.2 | Configuration | `config.py` with pydantic-settings | 1h |
| 1.3 | OpenCode client | `opencode_client.py` - HTTP client for Server API | 2h |
| 1.4 | Telegram bot | `bot.py` - webhook/polling, allowlist, routing | 3h |
| 1.5 | Response formatter | `formatter.py` - chunking, markdown for Telegram | 1h |
| 1.6 | Integration test | Test /command and message flow end-to-end | 2h |

**Exit Criteria**: 
- Bot responds to allowed user
- `/undo`, `/new`, `/share` work via Telegram
- Regular messages forwarded to OpenCode
- Responses formatted and returned

### 17.2 Phase 2: Voice Messages (Week 2)

**Goal**: Add voice message transcription.

| Task | Description | Deliverable | Estimate |
|------|-------------|-------------|----------|
| 2.1 | Whisper setup | Add faster-whisper dependency, model download | 1h |
| 2.2 | Voice handler | Download voice, transcribe, forward text | 2h |
| 2.3 | Voice tests | Test voice message flow | 1h |

**Exit Criteria**: Voice messages transcribed and processed.

### 17.3 Phase 3: URL Summarization (Week 2-3)

**Goal**: Add X thread and Substack summarization.

| Task | Description | Deliverable | Estimate |
|------|-------------|-------------|----------|
| 3.1 | URL detection | Detect URLs in messages | 1h |
| 3.2 | X extractor | `extractors/x.py` - GraphQL API extraction | 4h |
| 3.3 | Substack extractor | `extractors/substack.py` | 2h |
| 3.4 | Summarizer | Send extracted content to OpenCode for summary | 2h |
| 3.5 | Storage | Save articles to data/ directory | 2h |
| 3.6 | `/summarize` | Command to trigger summarization | 1h |

**Exit Criteria**: `/summarize https://x.com/...` works end-to-end.

### 17.4 Phase 4: Polish & Infrastructure (Week 3-4)

| Task | Description | Deliverable | Estimate |
|------|-------------|-------------|----------|
| 4.1 | Error handling | User-friendly error messages | 2h |
| 4.2 | Rate limiting | Implement request throttling | 1h |
| 4.3 | Syncthing setup | Docker Compose configuration | 2h |
| 4.4 | Deployment docs | `docs/deployment.md` | 2h |
| 4.5 | Testing | Unit and integration tests | 3h |
| 6.2 | Tailscale webhook setup | Funnel configuration, documentation | 1h |
| 6.3 | Monitoring | Health checks, restart policies | 1h |
| 6.4 | X cookie helper | `scripts/setup-x-cookies.py` | 2h |
| 6.5 | Final testing | Real-world usage on iPhone | 2h |

**Exit Criteria**: Production-ready deployment on Mac Mini.

### 17.7 Timeline Summary

```
Week 1: ++++++++++++++++++++++++ Foundation + Telegram
Week 2: ++++++++++++++++++++++++ Extraction + Core Logic  
Week 3: ++++++++++++++++++++++++ Voice + Polish + Infrastructure
Week 4: ++++++++++++            Buffer + Real-world testing
```

**Total Estimated Effort**: ~60 hours

---
