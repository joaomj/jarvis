
## 6. Functional Requirements

### 6.1 Message Processing

| ID | Requirement | Priority | Phase |
|----|-------------|----------|-------|
| FR-1 | Parse incoming Telegram messages (text only for MVP) | P0 | 1 |
| FR-2 | Route messages based on command prefix | P0 | 1 |
| FR-3 | Inject correlation ID at gateway entry | P0 | 1 |
| FR-4 | Support `/summarize <url>` command | P0 | 2 |
| FR-5 | Support `/help` command | P0 | 1 |
| FR-6 | Support `/private <message>` command | P1 | 2 |
| FR-7 | Support `/mode <fast|thinking>` command | P1 | 3 |
| FR-8 | Forward non-command text to OpenCode | P0 | 1 |
| FR-9 | Transcribe voice messages via Whisper | P0 | 2 |
| FR-10 | Format responses for Telegram markdown | P0 | 1 |

### 6.2 Content Extraction

| ID | Requirement | Priority | Phase |
|----|-------------|----------|-------|
| FR-11 | Extract X threads via GraphQL API | P0 | 2 |
| FR-12 | Fall back to Playwright if API fails | P1 | 2 |
| FR-13 | Extract Substack articles (public) | P0 | 2 |
| FR-14 | Extract generic articles via trafilatura | P0 | 2 |
| FR-15 | Handle extraction errors gracefully | P0 | 2 |
| FR-16 | Cache extracted content to avoid re-fetch | P2 | 3 |

### 6.3 Storage

| ID | Requirement | Priority | Phase |
|----|-------------|----------|-------|
| FR-17 | Save articles as markdown with YAML frontmatter | P0 | 2 |
| FR-18 | Save summaries as separate markdown files | P0 | 2 |
| FR-19 | Use naming convention: `{source}-{date}-{slug}.md` | P0 | 2 |
| FR-20 | Store conversation history as JSONL | P1 | 2 |
| FR-21 | Support Syncthing folder structure | P1 | 4 |

### 6.4 OpenCode Integration

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-22 | Create/manage OpenCode sessions via HTTP API | P0 |
| FR-23 | Send prompts to OpenCode session | P0 |
| FR-24 | Receive and parse OpenCode responses | P0 |
| FR-25 | Handle OpenCode SSE events (future) | P2 |

---
