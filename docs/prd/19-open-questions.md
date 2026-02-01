
## 19. Open Questions

### 19.1 Resolved

| Question | Resolution |
|----------|------------|
| Telegram or Discord? | Telegram (user preference) |
| Where to deploy? | Mac Mini with Tailscale |
| OpenCode working directory? | `/projects` (mounting `~/projects`), sessions in `/root/.opencode` |
| VPS vs Mac Mini? | Mac Mini primary (direct file access critical for coding) |
| Which Whisper model? | `small` (balance of speed/accuracy) |
| Syncthing in Docker? | Yes, included |
| Logging approach? | File-based, FluentBit-ready |
| Article naming? | `{source}-{date}-{slug}.md` |
| X scraping approach? | GraphQL API primary, Playwright fallback |

### 19.2 Open (Deferred)

| Question | Notes | Phase |
|----------|-------|-------|
| How to handle X rate limits long-term? | May need proxy rotation | Post-MVP |
| Memory/learning architecture? | Research Clawdbot, Agent Builder approaches | Phase 6 |
| Private mode encryption? | Currently just skips logging | Phase 2 |
| Email summarization integration? | Requires Gmail API setup | Phase 4+ |
| Calendar/Weather alerts? | Requires Google Calendar API | Phase 4+ |

---
