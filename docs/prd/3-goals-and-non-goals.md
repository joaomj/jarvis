
## 3. Goals and Non-Goals

### 3.1 Goals (MVP - Phase 1)

| ID | Goal | Success Criteria |
|----|------|------------------|
| G1 | **Telegram-OpenCode bridge** | Text in -> OpenCode response out in <15s |
| G2 | OpenCode command support | /undo, /share, /compact, /new work via Telegram |
| G3 | Single user security | Only allowed Telegram user ID can interact |
| G4 | Session persistence | One session per user, continuous context |
| G5 | Mobile-friendly responses | Chunked if >4096 chars, markdown formatted |

### 3.2 Goals (Phase 2)

| ID | Goal | Success Criteria |
|----|------|------------------|
| G6 | Summarize X threads via Telegram | URL in -> summary out in <30s |
| G7 | Summarize Substack articles | URL in -> summary out in <30s |
| G8 | Archive original content as markdown | Syncthing-synced, grep-able |
| G9 | Voice message support | Whisper transcription, text response |
| G10 | Private mode (unlogged conversations) | Toggle via command |

### 3.3 Goals (Phase 3+)

| ID | Goal | Phase |
|----|------|-------|
| G11 | Conversation modes (Fast/Thinking) | Phase 3 |
| G12 | PDF/file upload and discussion | Phase 3 |
| G13 | Remote OpenCode project control | Phase 4 |
| G14 | Google Calendar alerts | Phase 5 |
| G15 | Weather notifications | Phase 5 |
| G16 | Deep Research reports | Phase 6 |
| G17 | Memory/learning system | Phase 6 |

### 3.4 Non-Goals (Explicit Exclusions)

| Non-Goal | Rationale |
|----------|-----------|
| Multi-user support | Personal assistant, not SaaS |
| Image/video generation | User stated not needed |
| Email writing/deletion | Security constraint |
| X account modifications | Security constraint |
| Public API exposure | Security constraint |
| Mobile app development | Telegram is the UI |
| Real-time streaming responses | Telegram limitations |

---
