# PRD: Personal AI System ("Jarvis") v2.1

**Version:** 2.1  
**Status:** Draft  
**Host Infrastructure:** Local Mac Mini (M4/M2) via Cloudflare Tunnel  
**Core Philosophy:** "Filesystem as Database" — Portable, Queryable, Sovereign Memories

**v2.1 Changes:**
- Added async task persistence (SQLite-based job queue)
- Added comprehensive error handling & resilience strategy
- Added observability & monitoring (logging, metrics, tracing, health checks)
- Added cost management (tracking, alerts, no enforcement)
- Added file handling validation and limits
- Added fallback mechanisms for various failure scenarios
- Enhanced memory data quality (versioning, conflict resolution, archival)
- Added context window management notes
- Updated testing strategy (comprehensive: unit + integration + E2E + performance + security)
- Added CI/CD strategy (GitHub Actions, free plan)
- Added Docker configuration (Dockerfile, docker-compose.yml)
- Updated backup strategy (Google Drive API with automated verification)
- Updated tech stack (new dependencies: structlog, loguru, prometheus_client, tenacity, slowapi, Google Drive API)
- Added operational runbook (startup, shutdown, troubleshooting, maintenance)
- Enhanced environment variables (comprehensive .env template)
- Added Phase 6 to implementation roadmap (Docker & CI/CD)
- Enhanced success criteria (added 8 new criteria)
- Enhanced performance targets (added 5 new metrics)

---

## 1. Executive Summary

**Jarvis** is a self-hosted, sovereign personal AI assistant designed to run on a residential Mac Mini. It serves as a "Second Brain," capable of:

- **Retrieving personal memories** from a local filesystem that you control and can move anywhere
- **Grounding answers** in real-time web data with academic-style source citations
- **Processing user-attached documents** (PDF, DOCX, text, code)
- **Generating comprehensive research reports** (8-15 pages) with deep academic sources

The system leverages **Cloudflare Tunnel** for secure exposure to **Telegram** without opening local network ports, combining the privacy of local storage with the power of Google's Gemini models.

**Key Design Principles:**
- **Multi-agent architecture** from day 1 (extensible)
- **LLM-agnostic design** (Gemini default, swappable)
- **Filesystem-based memory** — Markdown files that are portable and queryable
- **Source-cited responses** — All answers include footnotes with academic conventions
- **Security-first** (4-layer defense)
- **Single-user simplicity** — No multi-user complexity

---

## 2. Core Philosophy: "Filesystem as Database"

### 2.1 The Insight

Traditional AI systems treat user memories as opaque databases controlled by third parties. Jarvis takes a different approach:

> "Everything is a file" — Your memories, context, and knowledge are stored as plain Markdown files that you control.

Inspired by:
- [agentfs](https://github.com/tursodatabase/agentfs) — Filesystem as agent context
- [Everything is a file](https://turso.tech/blog/nothing-new-under-the-sun) — Unix philosophy for AI
- [How to build agents with filesystems and bash](https://vercel.com/blog/how-to-build-agents-with-filesystems-and-bash)

### 2.2 Benefits

| Benefit | Description |
|---------|-------------|
| **Portability** | Move memories between devices, back up anywhere |
| **Queryability** | Use standard tools: `grep`, `find`, `ripgrep` |
| **Transparency** | See exactly what the AI knows about you |
| **Sovereignty** | No vendor lock-in, your data is yours |
| **Version Control** | Use Git to track memory changes |

### 2.3 Memory File Structure

```
~/jarvis/memories/
├── conversations/
│   └── 2026/01/18/
│       ├── session-001.md           # Full transcript + summary
│       └── session-002.md
├── facts/
│   ├── personal.md                  # "I live in Tokyo"
│   ├── preferences.md               # "I prefer concise answers"
│   └── contacts.md                  # "John's email is..."
├── entities/
│   ├── people/
│   │   └── john-doe.md              # Entity-specific memory
│   ├── projects/
│   │   └── jarvis.md
│   └── locations/
│       └── favorite-restaurants.md
└── index.md                         # Memory overview (optional)
```

---

## 3. Conversation Modes

### 3.1 Mode Overview

| Mode | Model | Response Length | Use Case | Features |
|------|-------|-----------------|----------|----------|
| **Fast** | Gemini 3 Flash | <700 chars | Quick questions, speed-optimized | Sources as footnotes, PDF attachments |
| **Thinking** | Gemini 3 Pro | Unlimited | Complex reasoning, multi-step answers | Deep reasoning, sources, PDF attachments |
| **Deep Research** | Gemini 3 Pro | 8-15 pages (PDF) | Academic research, reports | IMRaD format, async, PDF attachments |

### 3.2 Source Citation System

**All modes** include source citations using academic footnote conventions:

```
Pedro Álvares Cabral discovered Brazil in 1500[1]. This marked the beginning
of Portuguese colonization in South America[2].

References:
[1] Wikipedia: Discovery of Brazil. https://en.wikipedia.org/wiki/Discovery_of_Brazil
[2] Cambridge History: Portuguese Empire. https://www.cambridge.org/...
```

**Citation Management:**
- Automatic source tracking during LLM generation
- Deduplication (same source → same number)
- Proper academic formatting (APA/MLA style options)

### 3.3 Mode Selection

The Router Agent classifies intent and routes to the appropriate mode:

```python
class RouteDecision(BaseModel):
    mode: Literal["fast", "thinking", "research"]
    reasoning: str
```

**Heuristics:**
- Simple factual queries → Fast
- "Tell me about X", "Explain X", "Analyze X" → Thinking
- "Research X", "Write a report on X", "Deep dive into X" → Deep Research
- User can explicitly specify: `/fast`, `/thinking`, `/research`

### 3.4 User-Attached Sources

**All modes** support user-attached PDF files as additional sources for grounding answers:

```
┌─────────────────────────────────────────────────────────────────┐
│                  USER-ATTACHED SOURCE FLOW                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User: "Summarize this paper" + [attached.pdf]                  │
│          │                                                       │
│          ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  ATTACHMENT PROCESSOR                                   │     │
│  │  • PDF → text extraction (PyMuPDF)                      │     │
│  │  • Chunk into sections                                  │     │
│  │  • Add to session context                               │     │
│  └────────────────────────┬────────────────────────────────┘     │
│                           │                                        │
│                           ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  HYBRID GROUNDING                                       │     │
│  │  • User-attached sources (highest priority)             │     │
│  │  • LLM internal search (web, academic APIs)             │     │
│  │  • Combined citation in response                        │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Use Cases:**
- Summarizing research papers the user provides
- Answering questions grounded in specific documents
- Comparing user-provided sources with web search results
- Deep Research using user's own reference materials alongside academic APIs

### 3.5 File Handling

**File Limits:**
- Maximum file size: 50MB
- Processing timeout: 5 minutes per file
- Supported formats: PDF, DOCX, TXT, code files (.py, .js, .ts, .go, etc.)

**File Validation:**
- Check file extension against allowlist
- Verify magic bytes for binary files:
  - PDF: `%PDF`
  - DOCX: `PK` (ZIP signature)
- Reject files that don't match extension + magic bytes
- No virus scanning or sandboxing (basic validation only for MVP)

**File Processing:**
```
File Upload → Magic Byte Check → Extension Check → Extract Text
                                                   │
                                                   ▼
                                          Temporary Directory
                                                   │
                                                   ▼
                                        Chunk Large Documents
                                        (~10k tokens per chunk)
                                                   │
                                                   ▼
                                    Add to Session Context with Metadata
                                    (filename, page numbers, chunk_index)
                                                   │
                                                   ▼
                                          Cleanup Temp Files
```

**File Storage:**
- Temporary directory: `/tmp/jarvis_uploads/`
- Cleanup: Delete after processing + 10 minutes
- No persistent storage of original files (only extracted text in session)

---

## 4. Deep Research Pipeline

### 4.1 Overview

Deep Research is an **asynchronous, multi-agent pipeline** that generates 8-15 page academic-style PDF reports.

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEEP RESEARCH PIPELINE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Request: "Research quantum computing advances in 2025"     │
│          │                                                       │
│          ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  RESEARCH ORCHESTRATOR AGENT                            │     │
│  │  • Parses research question                            │     │
│  │  • Generates search queries for each source tier        │     │
│  │  • Coordinates data collection                          │     │
│  └────────────────────────┬────────────────────────────────┘     │
│                           │                                        │
│        ┌──────────────────┼──────────────────┐                    │
│        ▼                  ▼                  ▼                    │
│  ┌───────────┐     ┌───────────┐     ┌───────────────┐          │
│  │  arXiv    │     │ Semantic  │     │ Web Search    │          │
│  │  Agent    │     │ Scholar   │     │ Agent         │          │
│  │  (Core)   │     │ (Core)    │     │ (General)     │          │
│  └───────────┘     └───────────┘     └───────────────┘          │
│        │                  │                  │                   │
│        └──────────────────┴──────────────────┘                   │
│                           ▼                                      │
│              ┌──────────────────────────────┐                    │
│              │    SOURCE RANKING ENGINE     │                    │
│              │  1. Academic papers (top)    │                    │
│              │  2. Books                    │                    │
│              │  3. High-traffic websites    │                    │
│              │  4. Social/blogs (bottom)    │                    │
│              └──────────────────────────────┘                    │
│                           ▼                                      │
│              ┌──────────────────────────────┐                    │
│              │   REPORT WRITER AGENT        │                    │
│              │   • Introduction             │                    │
│              │   • Literature Review        │                    │
│              │   • Methodology              │                    │
│              │   • Results                  │                    │
│              │   • Discussion               │                    │
│              │   • Conclusion               │                    │
│              │   • References (APA format)  │                    │
│              └──────────────────────────────┘                    │
│                           ▼                                      │
│              ┌──────────────────────────────┐                    │
│              │   PDF GENERATION (WeasyPrint) │                    │
│              └──────────────────────────────┘                    │
│                           ▼                                      │
│  User notified via Telegram with PDF attachment                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Source Hierarchy

| Priority | Source Type | Access Method | Quality Signals |
|----------|-------------|---------------|-----------------|
| 1 | Academic papers | arXiv API, Semantic Scholar API | Citations, venue, p-value, effect size |
| 2 | Books | Google Books API (via web search) | Publisher, edition, reviews |
| 3 | High-traffic sites | Gemini + Google Search | Wikipedia, news portals, archives |
| 4 | Social/blogs | Web search | Reddit, X, small blogs (lower weight) |

### 4.3 Research APIs (Free & Core)

| API | Purpose | Rate Limits | Status |
|-----|---------|-------------|--------|
| **arXiv API** | CS, physics, math, bio preprints | No auth, reasonable limits | Core |
| **Semantic Scholar API** | Broad academic coverage, citations | With API key: 1 req/sec | Core |
| **Gemini + Google Search** | General web info, current events | Gemini API quota | Core |
| **Anna's Archive API** | Books, scientific papers (free) | Members: fast download API | Post-MVP |

#### 4.3.1 Note on Anna's Archive
While powerful, Anna's Archive integration is deferred to Post-MVP to minimize initial complexity and dependencies. It can be accessed via members-only download URLs or raw Torrent/DB files.

### 4.4 Report Format (IMRaD)

All research reports follow the **IMRaD** (Introduction, Methods, Results, and Discussion) academic convention:

1. **Introduction**
   - Background context
   - Knowledge gap identification
   - Research question/thesis

2. **Literature Review**
   - Summary of existing research
   - How this report builds on/challenges existing knowledge

3. **Methodology**
   - Search strategy used
   - Sources accessed (arXiv, Semantic Scholar, web)
   - Selection criteria

4. **Results**
   - Findings presented objectively
   - Data, tables, figures
   - No interpretation

5. **Discussion**
   - Interpretation of findings
   - Relation to research question
   - Comparison with previous studies
   - Limitations

6. **Conclusion**
   - Summary of main points
   - Broader implications
   - Future research directions

7. **References**
   - APA-formatted bibliography
   - All sources cited in-line

### 4.5 Asynchronous Execution

Deep research tasks are handled as background processes using Python's `asyncio.create_task()`.

```
1. User: "Research quantum computing in 2025"
2. Jarvis: "Starting deep research. This may take 10-20 minutes.
             I'll notify you when the report is ready."
3. [Background research executes via asyncio]
4. Jarvis: "Your research report is ready. [PDF attached]"
```

*Note: For a single-user system, an in-memory task queue is sufficient. Redis/Celery are skipped to avoid operational complexity.*

### 4.6 Async Task Persistence

To handle system restarts and ensure no research jobs are lost, deep research tasks use a **SQLite-based job queue**:

**Job Queue Table Structure:**
```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL CHECK(status IN ('pending', 'in_progress', 'completed', 'failed')),
    query TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'research',
    result TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

**Job Lifecycle:**
```
pending → in_progress → completed
                      ↘ failed
```

**Startup Recovery:**
- On system startup, check for `in_progress` jobs
- Reset to `pending` with timestamp update
- Auto-resume jobs based on queue priority (FIFO)

**Job Query API:**
- `GET /jobs` - List all jobs with filtering
- `GET /jobs/{id}` - Get job details and status
- `POST /jobs/{id}/retry` - Retry failed jobs

---

## 5. Memory System

### 5.1 Hybrid Extraction Model

Memory extraction balances automation with user control:

```
┌─────────────────────────────────────────────────────────────────┐
│                    MEMORY EXTRACTION FLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Conversation ends                                               │
│          │                                                       │
│          ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  AGENT ANALYSIS                                         │     │
│  │  "I identified 3 potentially memorable facts:"          │     │
│  │  1. You're planning a trip to Japan in March 2026       │     │
│  │  2. You prefer functional programming over OOP          │     │
│  │  3. Your brother's name is Carlos                       │     │
│  └────────────────────────┬────────────────────────────────┘     │
│                           │                                        │
│                           ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  USER CONFIRMATION (Telegram)                           │     │
│  │                                                         │     │
│  │  Should I remember:                                     │     │
│  │  ☑ Japan trip in March 2026                            │     │
│  │  ☑ Functional programming preference                   │     │
│  │  ☐ Brother's name (Carlos)                             │     │
│  │                                                         │     │
│  │  [Remember Selected] [Edit] [Skip All]                   │     │
│  └────────────────────────┬────────────────────────────────┘     │
│                           │                                        │
│                  User confirms selected facts                      │
│                           ▼                                       │
│  Save to memories/ as structured Markdown files                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Memory Retrieval

Memories are retrieved using standard filesystem tools:

| Tool | Command | Purpose |
|------|---------|---------|
| `search_memories(query)` | `grep -ri "Japan"` ~/jarvis/memories | Find relevant memories |
| `read_memory(path)` | `cat memories/facts/japan-trip.md` | Read specific file |
| `find_recent(days)` | `find -mtime -7` ~/jarvis/memories | Recent memories |

### 5.3 Memory Storage

```python
save_memory(
    category="facts/personal",
    content="User is planning a trip to Japan in March 2026."
)
# Creates: memories/facts/personal/japan-trip-2026.md
```

### 5.4 Memory Data Quality

**Timestamp-Based Versioning:**
- Keep all versions of facts with timestamps
- Newest version = current truth
- Historical versions preserved for reference

**Example Memory File:**
```markdown
# Japan Trip 2026

## 2026-01-18 (Current)
User is planning a trip to Japan in March 2026.
- Duration: 2 weeks
- Cities: Tokyo, Kyoto, Osaka

## 2026-01-10 (Previous)
User considering trip to Japan in spring 2026.
```

**Conflict Resolution:**
- When user provides contradictory information, create new entry
- Mark newest as `[Current]`, older as `[Previous]`
- On retrieval, return newest entry as primary
- Include historical context: "Previously: [old value]"

**Usage-Based Decay:**
- Track `last_accessed` timestamp per memory (metadata in file)
- Memories not accessed in 3+ months: add `stale: true` metadata
- Stale memories still searchable, but deprioritized
- Manual refresh command: `/refresh_memory <path>`

**Memory Review & Archival:**
- Quarterly review of stale memories
- User can archive to `memories/archive/` via `/archive_memory <path>`
- Archived memories not returned by default (use `/include_archived` flag)

**Duplicate Detection:**
- Basic similarity check on save (exact match → skip)
- Similar facts (e.g., "lives in Tokyo" vs "lives in Japan") → create new entry
- User can manually merge: `/merge_memories <path1> <path2>`

---

## 6. System Architecture

### 6.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              JARVIS LOCAL                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [Telegram User] ──webhook──▶ [Cloudflare Tunnel] ──▶ [FastAPI Gateway]     │
│                                                              │              │
│                    ┌─────────────────────────────────────────┘              │
│                    ▼                                                        │
│             ┌──────────────────────────────────────┐                        │
│             │          ROUTER AGENT                │                        │
│             │       (Gemini 2.5 Flash)             │                        │
│             │                                      │                        │
│             │   Routes to: Fast | Thinking | Research                     │
│             └──────────────┬───────────────────────┘                        │
│                            │                                                │
│        ┌───────────────────┼───────────────────────┐                        │
│        ▼                   ▼                       ▼                        │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────────────┐              │
│  │  CHAT FAST    │  │ CHAT THINKING │  │   DEEP RESEARCH     │              │
│  │  (700 chars)  │  │   (Deep)      │  │   (Async, PDF)      │              │
│  │  + Footnotes  │  │  + Footnotes  │  │   + IMRaD format    │              │
│  └───────────────┘  └───────────────┘  └─────────────────────┘              │
│            │                                                                │
│            ▼                                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    SHARED SESSION CONTEXT                           │    │
│  │  • user_id, session_id, message_history                             │    │
│  │  • attachments (parsed text from files)                             │    │
│  │  • memories_dir path                                                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│            │                                                                │
│  ┌─────────┴─────────┬────────────────┬────────────────┐                    │
│  ▼                   ▼                ▼                ▼                    │
│  [memories/]     [SQLite DB]    [Gemini API]    [Google Drive]              │
│  (Markdown)      (Chat Logs)    (LLM + Search)  (Backup)                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Component Breakdown

| Layer | Component | Implementation | Location |
|-------|-----------|----------------|----------|
| **Interface** | UI Client | Telegram App | User Device |
| **Network** | Secure Tunnel | Cloudflare Tunnel (`cloudflared`) | Background Service (Mac) |
| **Gateway** | Web Server | FastAPI + Uvicorn | Local Process (Mac) |
| **Logic** | Agent Orchestrator | PydanticAI | Local Process (Mac) |
| **Memory** | Personal Knowledge | Filesystem (Markdown) | Local SSD (Mac) |
| **Memory** | Chat Logs | SQLite (`jarvis.db`) | Local SSD (Mac) |
| **Cognition** | LLM & Search | Gemini API (default) | Google Cloud |
| **Research** | Academic Sources | arXiv + Semantic Scholar APIs | Public APIs |
| **Reports** | PDF Generation | WeasyPrint (Python-native) | Local Process (Mac) |
| **Backup** | Cloud Sync | Google Drive Desktop | Real-time sync |

### 6.3 Context Window Management

**Current Approach (MVP):**
- No explicit limits on conversation length
- Let LLM handle context window naturally
- Monitor context usage via metrics (`jarvis_context_tokens` gauge)
- Add explicit management only if it becomes an issue

**Future Enhancements (Post-MVP):**
- Auto-summarize old messages when approaching limit
- Session rollover after N messages
- Sliding window retention (last N messages only)
- Selective memory: Keep only key facts from long conversations

---

### 7.1 API Failure Handling

**Retry Strategy:**
- All external API calls: 3-5 retries with exponential backoff
- Backoff delays: 1s, 2s, 4s, 8s, 16s
- Use `tenacity` or custom retry logic with jitter

**API-Specific Handling:**

| API | Failure Mode | Fallback |
|-----|--------------|----------|
| **arXiv** | 5xx errors, timeouts | Continue without arXiv sources, log ERROR |
| **Semantic Scholar** | 429 rate limit, 5xx | Continue without SS sources, log WARN |
| **Gemini** | 429 quota, 500+ errors | Return graceful error message, user retry |
| **Telegram** | 429 rate limit (30 msg/sec) | Queue messages, retry with backoff |
| **Google Search** | Any failure | Use cached results or skip search |

**Error Response Format:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Gemini API quota exceeded. Please try again later.",
    "retry_after": 3600,
    "request_id": "req_abc123"
  }
}
```

### 7.2 File Parsing Failures

**Exception Handling:**
- Catch all parsing exceptions (PyMuPDF, python-docx)
- Return user-friendly error: "Unable to parse file. Please check the file format."
- Log ERROR with stack traces (internal only)
- Never expose file paths or system details

**Timeout Handling:**
- File processing timeout: 5 minutes per file
- On timeout: Abort processing, notify user, clean up temp files
- Log timeout with file metadata (size, type)

### 7.3 Database Errors

**SQLite Error Handling:**
- Catch `sqlite3.OperationalError`, `sqlite3.IntegrityError`
- Log ERROR with query context (sanitized)
- Return generic error: "Database error. Please try again."
- Auto-retry on `database is locked` (max 3 attempts)

**Connection Pool:**
- Use connection pooling (5-10 connections)
- Health check: Query on startup, fail fast if unavailable

### 7.4 Network Configuration

**HTTP Client Settings:**
```python
# httpx configuration
TIMEOUT = 30.0  # seconds
MAX_RETRIES = 5
RETRY_BACKOFF_FACTOR = 1.0
```

**Configurable via `.env`:**
```
HTTP_TIMEOUT=30
HTTP_MAX_RETRIES=5
```

### 7.5 Error Message Sanitization

**Sanitization Rules:**
- Never expose stack traces to users
- Never expose file paths, API keys, or secrets
- Use generic error codes for internal errors
- Include request_id for debugging

**Error Codes:**
- `INTERNAL_ERROR`: Generic server error
- `RATE_LIMIT_EXCEEDED`: API quota exceeded
- `INVALID_REQUEST`: Bad user input
- `FILE_PARSE_ERROR`: Unable to process file
- `DATABASE_ERROR`: Storage failure

---

## 7. Directory Structure

```
~/jarvis/
├── .env                         # Secrets (chmod 600, git-ignored)
├── .gitignore
├── pyproject.toml               # PDM configuration
├── jarvis.db                    # SQLite (chat logs)
├── README.md
│
├── src/jarvis/
│   ├── __init__.py
│   ├── main.py                  # FastAPI entrypoint
│   ├── config.py                # Pydantic Settings
│   │
│   ├── agents/                  # PydanticAI agents
│   │   ├── __init__.py
│   │   ├── router.py            # Intent router
│   │   ├── chat_fast.py         # Fast mode (~700 chars)
│   │   ├── chat_thinking.py     # Thinking mode (deep)
│   │   └── research/            # Deep research package
│   │       ├── __init__.py
│   │       ├── orchestrator.py  # Multi-step coordination
│   │       ├── sources.py       # Source ranking logic
│   │       ├── arxiv.py         # arXiv API client
│   │       └── semantic_scholar.py  # Semantic Scholar client
│   │
│   ├── tools/                   # Agent tools
│   │   ├── __init__.py
│   │   ├── memory.py            # Memory operations (grep, cat, save)
│   │   ├── web.py               # Web search (Gemini)
│   │   └── files.py             # File reading, attachment parsing
│   │
│   ├── citation/                # Citation management
│   │   ├── __init__.py
│   │   ├── formatter.py         # Footnote formatting
│   │   └── tracker.py           # Source tracking during generation
│   │
│   ├── reports/                 # Report generation
│   │   ├── __init__.py
│   │   ├── imrad.py             # IMRaD template & structure
│   │   └── pdf.py               # WeasyPrint rendering
│   │
│   ├── context/                 # Session management
│   │   ├── __init__.py
│   │   ├── session.py           # SessionContext
│   │   └── attachments.py       # File processing (PDF, DOCX)
│   │
│   ├── security/                # Security middleware
│   │   ├── __init__.py
│   │   ├── validation.py        # Token validation
│   │   ├── sanitization.py      # Input cleaning
│   │   └── injection.py         # Injection detection
│   │
│   └── telegram/                # Telegram integration
│       ├── __init__.py
│       ├── webhook.py           # Webhook handler
│       └── helpers.py           # Message formatting
│
├── memories/                    # Memory storage (backed up)
│   ├── conversations/
│   ├── facts/
│   └── entities/
│
├── reports/                     # Generated research reports
│   └── 2026/
│       ├── quantum-computing-2025.pdf
│       └── machine-learning-future.pdf
│
├── tests/                       # E2E tests
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
└── docs/                        # Documentation
    ├── tech-context.md          # Architecture source of truth
    ├── issues/                  # Issue tracking
    └── PRDv2.md                 # This document
```

---

## 8. Tech Stack

| Component | Library | Version | Rationale |
|-----------|---------|---------|-----------|
| **Runtime** | Python | 3.12+ | Modern type hints, performance |
| **Package Manager** | PDM | Latest | Per AGENTS.md guidelines |
| **Web Framework** | FastAPI | Latest | Async, type-safe, OpenAPI |
| **ASGI Server** | Uvicorn | Latest | FastAPI default |
| **Agent Framework** | PydanticAI | Latest | Multi-agent, type-safe deps |
| **LLM SDK** | google-generativeai | Latest | Gemini 2.5 Flash/Pro |
| **Telegram** | python-telegram-bot | Latest | Async, mature |
| **Database** | aiosqlite | Latest | Async SQLite |
| **Config** | pydantic-settings | Latest | Type-safe env loading |
| **PDF Parser** | PyMuPDF | Latest | Binary format parsing |
| **DOCX Parser** | python-docx | Latest | Binary format parsing |
| **Reports** | PDF Generation | WeasyPrint | Python-native (HTML → PDF) |
| **Templates** | Jinja2 | Latest | Report templating |
| **HTTP Client** | httpx | Latest | Async, modern (for APIs) |
| **Logging** | structlog + loguru | Latest | Structured logging, rotation |
| **Metrics** | prometheus_client | Latest | Metrics for monitoring |
| **Retry Logic** | tenacity | Latest | Exponential backoff retries |
| **Rate Limiting** | slowapi | Latest | Telegram rate limiting |
| **Backup** | Google Drive API Python | Latest | Automated backups |

### 8.1 Dependencies

```toml
[project]
name = "jarvis"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "pydantic-ai>=0.2.0",
    "google-generativeai>=0.8.0",
    "python-telegram-bot>=21.0",
    "aiosqlite>=0.21.0",
    "pydantic-settings>=2.7.0",
    "pymupdf>=1.25.0",
    "python-docx>=1.1.0",
    "httpx>=0.28.0",
    "weasyprint>=63.0",
    "markdown>=3.7.0",
    "jinja2>=3.1.0",
]

[tool.pdm.dev-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.8.0",
    "httpx>=0.28.0",  # For mocking API calls
]
```

### 8.2 CI/CD Strategy

**GitHub Actions Workflow (Free Plan):**

**Triggers:**
- Pull requests to `main`
- Pushes to `main`

**Jobs:**
```yaml
# .github/workflows/ci.yml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - uses: pdm-project/setup-pdm@v4
      - run: pdm install
      - run: pdm run ruff check

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - uses: pdm-project/setup-pdm@v4
      - run: pdm install
      - run: pdm run pytest --cov=src

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - uses: pdm-project/setup-pdm@v4
      - run: pdm install
      - run: pdm audit
```

**Deployment Process (Manual):**
```bash
# Deploy to Mac Mini
cd ~/jarvis
git pull
pdm install
pdm run pytest
pdm run uvicorn src.jarvis.main:app --host 0.0.0.0 --port 8000
```

**Rollback:**
```bash
git revert HEAD
git push
# Redeploy manually
```

### 8.3 Docker Configuration

**Dockerfile:**
```dockerfile
# Multi-stage build
FROM python:3.12-slim AS builder

WORKDIR /app

# Install PDM
RUN pip install pdm

# Copy PDM files
COPY pyproject.toml pdm.lock ./

# Install dependencies
RUN pdm install --prod

# Final stage
FROM python:3.12-slim

WORKDIR /app

# Copy from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /root/.local/share/pdm/venvs /root/.local/share/pdm/venvs

# Copy application code
COPY src/ src/
COPY reports/ reports/

# Create directories
RUN mkdir -p memories logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/health')"

# Run application
CMD ["pdm", "run", "uvicorn", "src.jarvis.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  jarvis:
    build: .
    container_name: jarvis
    restart: on-failure
    ports:
      - "8000:8000"
    volumes:
      - ./memories:/app/memories
      - ./jarvis.db:/app/jarvis.db
      - ./reports:/app/reports
      - ./logs:/app/logs
    env_file:
      - .env
    environment:
      - PYTHONUNBUFFERED=1
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

**Docker Benefits for Cloud Migration:**
- Portable deployment to any cloud provider (AWS, GCP, Azure, DigitalOcean)
- Consistent environments across dev/staging/prod
- Easy scaling: Docker Swarm, Kubernetes, ECS
- Development: Quick local testing with `docker-compose up`

---

## 9. Security Specification

### 9.1 Security Architecture (4 Layers)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SECURITY LAYERS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LAYER 1: NETWORK (Cloudflare)                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ • WAF: Allow only Telegram IPs (149.154.160.0/20, 91.108.4.0/22)    │    │
│  │ • WAF: Block non-POST to /webhook/telegram                          │    │
│  │ • WAF: Require application/json content-type                        │    │
│  │ • WAF: Rate limit 100 req/min/IP                                    │    │
│  │ • DDoS protection (automatic)                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  LAYER 2: TRANSPORT (Cloudflare Tunnel)                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ • TLS 1.3 encryption                                                │    │
│  │ • Outbound-only connection (no incoming ports open)                 │    │
│  │ • NO VPN REQUIRED (Cloudflare Tunnel handles secure access)         │    │
│  │ • Named tunnel with secured credentials (chmod 600)                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  LAYER 3: APPLICATION (FastAPI)                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ • X-Telegram-Bot-Api-Secret-Token validation (hmac.compare_digest)  │    │
│  │ • Input sanitization (unicode normalization, length limits)          │    │
│  │ • Rate limiting per user (30 msg/min)                               │    │
│  │ • Prompt injection detection + logging                              │    │
│  │ • Error message sanitization (no stack traces)                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  LAYER 4: HOST (Mac Mini)                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ • macOS Firewall enabled (stealth mode, block all incoming)         │    │
│  │ • FileVault full-disk encryption                                    │    │
│  │ • File permissions: .env (600), memories/ (750), db (600)           │    │
│  │ • Unnecessary services disabled                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Security Checklist

**Pre-Deployment (Critical)**
- [ ] macOS FileVault enabled
- [ ] macOS Firewall enabled (stealth mode)
- [ ] All unnecessary macOS services disabled
- [ ] `.env` file has `chmod 600` permissions
- [ ] `.env` is in `.gitignore`
- [ ] Telegram webhook secret is 32+ random alphanumeric chars
- [ ] Cloudflare tunnel credentials secured (`chmod 600 ~/.cloudflared/`)

**Cloudflare Configuration (Critical)**
- [ ] Named tunnel configured (not quick tunnel)
- [ ] No incoming ports open on local network (VPN unnecessary)
- [ ] WAF Rule: Telegram IPs only on `/webhook/telegram`
- [ ] WAF Rule: POST method only
- [ ] WAF Rule: JSON content-type required
- [ ] WAF Rule: Rate limit 100/min/IP

**Application Security (Critical)**
- [ ] `X-Telegram-Bot-Api-Secret-Token` validation implemented
- [ ] Using `hmac.compare_digest` for timing-safe comparison
- [ ] Input sanitization (unicode, length, control chars)
- [ ] Prompt injection detection with logging
- [ ] No secrets logged
- [ ] Rate limiting per user (30 msg/min)

**Backup Security (High)**
- [ ] Google Drive Desktop syncing `memories/`
- [ ] `.env` excluded from sync
- [ ] Backup verification tested

### 9.3 Single-User Security Model

**Simplification (vs. multi-user):**
- No user authentication required
- Telegram user_id allowlist (single owner)
- No session management complexity
- Simplified rate limiting

---

## 10. Observability & Monitoring

### 10.1 Logging

**Logging Setup:**
- Library: `structlog` + `loguru`
- Output: `jarvis.log` (JSON format)
- Log rotation: 100MB max per file, keep 10 files
- Configurable via `.env`: `LOG_LEVEL=INFO|DEBUG|WARN|ERROR`

**Log Levels:**
- `DEBUG`: Detailed execution flow (development only)
- `INFO`: Normal operation, request/response logging
- `WARN`: Recoverable issues (retries, fallbacks)
- `ERROR`: Errors requiring investigation
- `CRITICAL`: System failures, service unavailable

**Log Structure (JSON):**
```json
{
  "timestamp": "2026-01-18T10:30:00Z",
  "level": "INFO",
  "request_id": "req_abc123",
  "user_id": "123456789",
  "message": "Research job completed",
  "duration_ms": 45000,
  "job_id": 42,
  "mode": "research",
  "sources_count": 15
}
```

**Logging Rules:**
- NEVER log secrets (API keys, tokens, personal data)
- Use structured logging with context
- Include correlation IDs through all async operations
- Sanitize error messages before logging

### 10.2 Metrics

**Metrics Collection:**
- Library: `prometheus_client` (Python)
- Expose metrics at `/metrics` endpoint (Prometheus format)

**Key Metrics:**

| Metric | Type | Description |
|--------|------|-------------|
| `jarvis_api_requests_total` | Counter | API calls per endpoint |
| `jarvis_api_response_time_seconds` | Histogram | Response time distribution |
| `jarvis_api_errors_total` | Counter | Errors per endpoint |
| `jarvis_llm_tokens_total` | Counter | LLM token usage |
| `jarvis_llm_cost_usd` | Gauge | Estimated LLM cost |
| `jarvis_memory_count` | Gauge | Total memories |
| `jarvis_memory_stale_count` | Gauge | Stale memories |
| `jarvis_jobs_pending` | Gauge | Pending jobs |
| `jarvis_jobs_in_progress` | Gauge | Active jobs |
| `jarvis_jobs_failed_total` | Counter | Failed jobs |

**Monitoring Dashboard:**
- API error rate >10%: Alert
- Job failure rate >20%: Alert
- Disk space <10%: Alert
- LLM cost >75% of budget: Alert

### 10.3 Tracing

**Request Tracing:**
- Generate `request_id` on incoming request
- Pass through all async operations
- Log at entry/exit of each component
- Track job lifecycle end-to-end

**Future Integration:**
- Open-source LLM observability tool (post-MVP)
- Distributed tracing with OpenTelemetry

### 10.4 Health Checks

**Health Check Endpoint: `/health`**

```json
{
  "status": "healthy",
  "timestamp": "2026-01-18T10:30:00Z",
  "version": "0.1.0",
  "dependencies": {
    "gemini_api": "healthy",
    "arxiv_api": "healthy",
    "semantic_scholar_api": "healthy",
    "telegram_webhook": "healthy",
    "database": "healthy",
    "disk_space": "80% free"
  },
  "job_queue": {
    "pending": 2,
    "in_progress": 1,
    "completed_today": 15
  }
}
```

**Health Check Script:**
```bash
# Check system health
curl http://localhost:8000/health | jq .

# Exit code 0 if healthy, 1 if degraded
```

---

## 11. Cost Management

### 11.1 Cost Tracking (Monitoring Only)

**No enforcement:** Track costs, alert when approaching budget, but don't block operations.

**Cost Estimation per Mode:**

| Mode | Tokens (approx) | Cost (Flash) | Cost (Pro) |
|------|-----------------|--------------|------------|
| **Fast** | ~500 tokens | ~$0.000001 | ~$0.000004 |
| **Thinking** | ~5,000 tokens | ~$0.00001 | ~$0.00004 |
| **Deep Research** | ~100,000 tokens | ~$0.0002 | ~$0.0008 |

**Monthly Cost Tracking:**
- Track tokens per mode per day
- Calculate estimated cost using current pricing
- Store in `costs` table in SQLite

**Cost Dashboard:**
- `/metrics/cost` endpoint returns:
```json
{
  "month": "2026-01",
  "total_estimated_cost_usd": 5.23,
  "budget_usd": 20.00,
  "budget_used_percent": 26.15,
  "by_mode": {
    "fast": 0.50,
    "thinking": 1.50,
    "research": 3.23
  },
  "daily_breakdown": [...]
}
```

**Cost Alerts:**
- 50% of budget: Info-level log
- 75% of budget: WARN-level log + notification
- 90% of budget: ERROR-level log + critical notification

### 11.2 Gemini Authentication

**Status:** Decision pending research

**Options Under Consideration:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **OpenAI-compatible endpoint** | OpenRouter, DeepSeek, etc. | Standard API, multiple LLMs | Requires API subscription |
| **Official API key (AI Studio)** | Create personal API key | Reliable, well-documented | Still uses API billing |
| **Web scraping** | Automate browser interactions | No API cost | Unreliable, ToS violation |
| **Other** | TBD | TBD | TBD |

**Implementation Notes:**
- Design LLM client to be swappable
- Abstract behind `LLMProvider` interface
- Configuration via `.env`: `LLM_PROVIDER=gemini|openrouter|...`

---

## 12. Fallback Mechanisms

### 12.1 Web Search Unavailable

**Fallback Strategy:**
```
Web Search Failed
       │
       ▼
┌──────────────────────────────────┐
│ Check Cache: Previous Searches? │
└──────────────────────────────────┘
       │           │
    Yes            No
       │           │
       ▼           ▼
 Use Cached   Use LLM Internal Knowledge
 Cached      + User-Attached Sources
 Search      + Stored Memories
       │           │
       └─────┬─────┘
             ▼
  Inform User: "Unable to access live search.
                 Answering from internal knowledge,
                 your attachments, and stored memories."
```

### 12.2 API Quota Exceeded

**Gemini Quota:**
- Continue with reduced functionality (no web search)
- Use cached results when available
- Notify user: "API quota exceeded. Please try again in {retry_after} seconds."
- Log ERROR with quota details

**Academic APIs (arXiv, Semantic Scholar):**
- Continue without that source
- Log WARN about missing source
- Inform user if source quality is degraded

### 12.3 Memory Search Failures

**Memory Unavailable:**
- Continue answering without memory context
- Log ERROR with search query and error details
- Don't block responses

**Partial Memory Failure:**
- Some memory files unreadable (permissions, corruption)
- Skip unreadable files, continue with rest
- Log WARN about skipped files

### 12.4 Deep Research Failures

**Partial Success:**
- If 50%+ sources retrieved: Generate partial report
- Note missing sources in "Limitations" section
- Inform user of partial completion

**Complete Failure:**
- Mark job as `failed` with error_message
- Notify user via Telegram with error details
- User can retry via `/research_retry <job_id>`

### 12.5 Attachment Processing Failures

**File Parse Failed:**
- Return user-friendly error
- Suggest: "Check file format, ensure file is not corrupted"
- Allow user to re-attach file

**Timeout During Processing:**
- Abort processing, clean up temp files
- Notify user: "File processing timed out. Try a smaller file."
- Log timeout with file size, type, processing time

---

## 10. Data & Storage Strategy

### 10.1 Directory Permissions

| Directory | Permission | Rationale |
|-----------|------------|-----------|
| `.env` | `600` | Secrets readable only by owner |
| `memories/` | `750` | Owner full, group read/write |
| `jarvis.db` | `600` | Chat logs contain private data |
| `reports/` | `750` | Generated research reports |
| `src/` | `755` | Application code |

### 13.2 Backup Strategy

**Primary Backup: Google Drive API**

**Setup:**
- Cost: $0.002/GB/month (free tier may cover your usage)
- Automated backup via Python Google Drive API client
- OAuth2 authentication with personal Google account

**Backup Schedule:**
- Daily incremental: Changed files only
- Weekly full: Complete backup of all data
- Retention: Keep 30 daily backups, 12 weekly backups

**Backed Up:**
- `memories/` - All user memories (Markdown files)
- `jarvis.db` - Chat logs, job queue, metadata
- `jarvis.log` - System logs (last 7 days)
- `reports/` - Generated research reports

**Excluded from Backup:**
- `.env` - Contains secrets (never backup!)
- `__pycache__/` - Python bytecode
- `.venv/` - Virtual environment
- `reports/tmp/` - Temporary PDF files

**Backup Verification:**
- Automated checksum script: Compare local vs remote hashes
- Daily verification: Alert on mismatches
- Monthly backup integrity report
- Test restore quarterly: Verify data consistency

**Cost Estimate:**
- Assuming 1GB total data: $0.002/month
- Well under $20/month total budget

**Alternative Backup Options:**
- `rsync` to external drive (manual)
- Git version control for `memories/` (manual)
- Time Machine snapshots (macOS only, local)
- Cloudflare R2: $0.015/GB/month (cheaper than S3)

---

## 14. Environment Variables

```ini
# .env (chmod 600, never commit)

# ============================================================
# Core Configuration
# ============================================================

# Application
APP_NAME=jarvis
APP_VERSION=0.1.0
DEBUG=false
LOG_LEVEL=INFO

# ============================================================
# Telegram
# ============================================================
TELEGRAM_BOT_TOKEN=xxxx:yyyyyyyyyyyyyyyyyyyyyyyy
TELEGRAM_WEBHOOK_SECRET=<random 32+ alphanumeric chars>
TELEGRAM_USER_ID=<your_telegram_user_id>
TELEGRAM_RATE_LIMIT=25  # Messages per second (max 30)

# ============================================================
# LLM Configuration
# ============================================================
LLM_PROVIDER=gemini  # gemini, openrouter, etc.
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL_FLASH=gemini-2.5-flash
GEMINI_MODEL_PRO=gemini-2.5-pro

# ============================================================
# HTTP Client
# ============================================================
HTTP_TIMEOUT=30  # Seconds
HTTP_MAX_RETRIES=5
HTTP_RETRY_BACKOFF=1.0

# ============================================================
# File Handling
# ============================================================
MAX_FILE_SIZE_MB=50
FILE_PROCESSING_TIMEOUT_SEC=300  # 5 minutes
TEMP_DIR=/tmp/jarvis_uploads

# ============================================================
# Job Queue
# ============================================================
JOB_MAX_RETRIES=3
JOB_TIMEOUT_SEC=1800  # 30 minutes

# ============================================================
# Cost Management
# ============================================================
COST_BUDGET_USD=20.00
COST_ALERT_THRESHOLD=0.75  # Alert at 75% of budget

# ============================================================
# Backup (Google Drive API)
# ============================================================
GOOGLE_DRIVE_ENABLED=true
GOOGLE_DRIVE_BACKUP_SCHEDULE=daily
GOOGLE_DRIVE_RETENTION_DAYS=30

# ============================================================
# Monitoring
# ============================================================
METRICS_ENABLED=true
HEALTH_CHECK_ENABLED=true
TRACING_ENABLED=false  # Future: OpenTelemetry

# ============================================================
# Database
# ============================================================
DATABASE_URL=sqlite+aiosqlite:///jarvis.db
DATABASE_POOL_SIZE=10

# ============================================================
# Cloudflare (managed by cloudflared, not in .env)
# ============================================================
# Tunnel credentials stored in ~/.cloudflared/
```

**Security Notes:**
- File permissions: `chmod 600 .env`
- Never commit `.env` to git
- Use `.env.example` for template (safe to commit)
- Rotate secrets periodically

---

## 12. Implementation Roadmap

### Phase 1: Foundation & Security (Week 1)

| Step | Task | Deliverable |
|------|------|-------------|
| 1.1 | Environment setup | PDM project, Python 3.12, dependencies |
| 1.2 | Host security | FileVault, Firewall, file permissions |
| 1.3 | Cloudflare Tunnel | Named tunnel, WAF rules |
| 1.4 | FastAPI skeleton | `/webhook/telegram` endpoint |
| 1.5 | Application security | Token validation, input sanitization |
| 1.6 | Google Drive | Desktop app, memories/ syncing |

**Checkpoint:** Secure webhook receives Telegram messages

### Phase 2: Core Agents & Memory (Week 2)

| Step | Task | Deliverable |
|------|------|-------------|
| 2.1 | SessionContext | Dataclass with deps, attachments |
| 2.2 | AttachmentProcessor | PDF/DOCX extraction |
| 2.3 | Memory tools | search, read, save, find_recent |
| 2.4 | Router agent | Intent classification (Fast/Thinking/Research) |
| 2.5 | Chat Fast agent | Gemini Flash, ~700 char limit, tools wired |
| 2.6 | Chat Thinking agent | Gemini Pro, deep reasoning, tools wired |
| 2.7 | Citation system | Footnote tracking, formatting |
| 2.8 | Web search tool | Gemini + Google Search |
| 2.9 | SQLite logging | Chat history storage |

**Checkpoint:** Both chat modes operational with citations and memory

### Phase 3: Hybrid Memory Extraction (Week 3)

| Step | Task | Deliverable |
|------|------|-------------|
| 3.1 | Memory analyzer | Identifies memorable facts post-conversation |
| 3.2 | Confirmation UI | Telegram inline buttons for memory approval |
| 3.3 | Memory storage | Saves structured Markdown files |
| 3.4 | Memory categories | facts/, entities/, conversations/ |

**Checkpoint:** User controls what gets remembered

### Phase 4: Deep Research Pipeline (Week 4-5)

| Step | Task | Deliverable |
|------|------|-------------|
| 4.1 | arXiv API client | Search and fetch academic preprints |
| 4.2 | Semantic Scholar client | Broad academic search, citations |
| 4.3 | Source ranking engine | Tier-based filtering (academic > web) |
| 4.4 | Research orchestrator | Multi-step coordination |
| 4.5 | Report writer agent | IMRaD format generation |
| 4.6 | PDF Integration | Markdown → HTML → PDF (WeasyPrint) |
| 4.7 | Async job queue | Background research execution |
| 4.8 | Notification system | Telegram message with PDF attachment |

**Checkpoint:** Full deep research pipeline operational

### Phase 5: Testing & Polish (Week 6)

| Step | Task | Deliverable |
|------|------|-------------|
| 5.1 | Error handling | Graceful failures, user-friendly messages |
| 5.2 | Prompt injection | Detection + logging |
| 5.3 | Rate limiting | Per-user limits |
| 5.4 | E2E tests | Integration tests (no mocks) |
| 5.5 | Lint & typecheck | `pdm run ruff check` passes |
| 5.6 | Unit tests | 80%+ coverage on critical paths |
| 5.7 | Documentation | tech-context.md, README.md |

**Checkpoint:** Production-ready MVP

### Phase 6: Docker & CI/CD (Week 7)

| Step | Task | Deliverable |
|------|------|-------------|
| 6.1 | Dockerfile | Multi-stage build for production |
| 6.2 | docker-compose.yml | Local development and deployment |
| 6.3 | GitHub Actions workflow | Lint + test + security scan |
| 6.4 | Backup script | Automated Google Drive API backup |
| 6.5 | Ops documentation | Full operational runbook (docs/ops.md) |
| 6.6 | Docker deployment | Run in Docker on Mac Mini |
| 6.7 | Cloud migration plan | Document steps for future cloud deployment |

**Checkpoint:** Production-ready with CI/CD, Docker, and automated backups

---

## 16. Success Criteria

### 16.1 MVP Success Criteria

| Criterion | Measurement |
|-----------|-------------|
| **Security** | All security checklist items completed |
| **Memory** | Agent recalls facts from previous conversations |
| **Memory control** | User approves/disapproves memory extraction |
| **Fast mode** | Responses <700 chars with footnoted sources |
| **Thinking mode** | Deep reasoning with comprehensive sources |
| **Web search** | Grounded answers with current information |
| **Attachments** | Processes PDF, DOCX, text/code files |
| **Citations** | All responses include academic-style footnotes |
| **Deep research** | Generates 8-15 page IMRaD PDF reports |
| **Source quality** | Prioritizes academic sources over social/blogs |
| **Async notifications** | User receives Telegram message with PDF |
| **Reliability** | System recovers from errors gracefully |
| **Backup** | Memories synced to Google Drive API |
| **Error handling** | Graceful failures, user-friendly error messages |
| **Monitoring** | Structured logs, metrics available at `/metrics` |
| **Cost tracking** | Estimated costs tracked, alerts at 50%/75%/90% |
| **Job persistence** | Jobs resume after system restart |
| **Testing** | Unit + integration + E2E tests pass, 80%+ coverage |
| **Docker** | Application runs in Docker container |
| **CI/CD** | GitHub Actions runs on PR, lint + test + security |

### 16.2 Performance Targets

| Metric | Target |
|--------|--------|
| Fast mode response time | <5 seconds |
| Thinking mode response time | <30 seconds |
| Deep research completion time | 10-20 minutes |
| Memory search latency | <1 second |
| File processing time | <5 minutes (50MB max) |
| Job resume time | <30 seconds on startup |
| Health check response | <1 second |
| Metrics scrape time | <5 seconds |
| System uptime | 99%+ |
| API error rate | <5% (excluding quota) |
| Backup success rate | 100% (alert on failure) |

---

## 17. Future Enhancements (Post-MVP)

| Feature | Description | Priority |
|---------|-------------|----------|
| **Voice input** | Whisper or Gemini audio transcription | Medium |
| **Anna's Archive** | Direct full-text book retrieval | High |
| **Feedback system** | 👍/👎 buttons, quality tracking | Medium |
| **Multi-user support** | Family/team with separate memories | Low |
| **Advanced citation** | BibTeX export, citation styles | Medium |
| **Research templates** | Custom report formats | Low |
| **Memory graphs** | Visual connections between memories | Low |
| **Calendar integration** | Schedule-based memory prompts | Low |

---

## 18. Operational Runbook

### 18.1 Startup Procedures

**Start Services:**
```bash
cd ~/jarvis
pdm run uvicorn src.jarvis.main:app --host 0.0.0.0 --port 8000
```

**Verify Health:**
```bash
# Check health endpoint
curl http://localhost:8000/health | jq .

# Expected output:
{
  "status": "healthy",
  "dependencies": {
    "gemini_api": "healthy",
    "database": "healthy",
    ...
  }
}
```

**Check Logs:**
```bash
# Tail logs in real-time
tail -f jarvis.log

# Filter by error level
grep -i "ERROR" jarvis.log
```

**Resume Jobs:**
- Auto-check for pending/in_progress jobs on startup
- Jobs marked as `in_progress` → Reset to `pending`
- Job queue processes pending jobs in FIFO order

### 18.2 Shutdown Procedures

**Graceful Shutdown:**
```bash
# Send SIGTERM (graceful)
pkill -TERM -f uvicorn

# Or use uvicorn directly (if running in foreground)
# Press Ctrl+C
```

**Shutdown Process:**
1. Stop accepting new requests
2. Complete current in-flight requests (30s timeout)
3. Save job queue state (in_progress jobs)
4. Close database connections
5. Stop service

**Verify Clean Shutdown:**
```bash
# Check no processes running
ps aux | grep uvicorn

# Check database for in_progress jobs
sqlite3 jarvis.db "SELECT COUNT(*) FROM jobs WHERE status='in_progress';"
```

### 18.3 Common Issues & Troubleshooting

**Issue: API Failures**

Symptoms:
- "Unable to connect to Gemini API" errors
- High error rate in logs

Troubleshooting:
1. Check API key: `grep GEMINI_API_KEY .env` (mask output!)
2. Check API quota: Visit Gemini AI Studio
3. Verify network connectivity: `ping google.com`
4. Check logs: `grep "gemini_api" jarvis.log | grep ERROR`

Solution:
- Rotate API key if compromised
- Wait for quota reset if exceeded
- Check network/firewall settings

---

**Issue: Memory Search Slow**

Symptoms:
- Memory retrieval >1 second
- High CPU usage during search

Troubleshooting:
1. Check disk space: `df -h`
2. Check memory count: `find memories/ -type f | wc -l`
3. Check for corrupted files: `grep -r "NULL" memories/`

Solution:
- Consider indexing (post-MVP)
- Archive old memories
- Check disk I/O performance

---

**Issue: Jobs Stuck**

Symptoms:
- Job status remains `in_progress` for >30 minutes
- No progress in logs

Troubleshooting:
1. Check job status: `sqlite3 jarvis.db "SELECT * FROM jobs WHERE status='in_progress';"`
2. Check for errors: `grep "job_id=<id>" jarvis.log | tail -20`

Solutions:
- Manual retry: `POST /jobs/<id>/retry`
- Manual cancel: `UPDATE jobs SET status='failed' WHERE id=<id>;`
- Restart service to reset stuck jobs

---

**Issue: Telegram Webhook Not Receiving Messages**

Symptoms:
- No new messages in logs
- Telegram bot unresponsive

Troubleshooting:
1. Check Cloudflare Tunnel status: `cloudflared tunnel info`
2. Check WAF rules: Cloudflare Dashboard → Firewall
3. Verify webhook secret: `grep TELEGRAM_WEBHOOK_SECRET .env`

Solutions:
- Restart Cloudflare Tunnel
- Check WAF rules are allowing Telegram IPs
- Verify webhook URL: `curl https://your-domain.com/health`

---

### 18.4 Maintenance

**Daily:**
- Check logs for errors: `grep -i "ERROR" jarvis.log`
- Monitor disk space: `df -h`
- Check job queue: `sqlite3 jarvis.db "SELECT status, COUNT(*) FROM jobs GROUP BY status;"`

**Weekly:**
- Review cost report: `curl http://localhost:8000/metrics/cost`
- Check API quota: Visit provider dashboards
- Verify backups running: Check Google Drive

**Monthly:**
- Review stale memories: `grep -r "stale: true" memories/`
- Archive old reports: Move reports >6 months to `reports/archive/`
- Dependency updates: `pdm update` (test before deploying)

**Quarterly:**
- Test backup restore: Restore from latest backup, verify data
- Review and archive stale memories
- Security audit: `pdm audit`, check for vulnerabilities

### 18.5 Dependency Updates

**Update Dependencies:**
```bash
cd ~/jarvis
pdm update
pdm run pytest
pdm run ruff check
```

**Before Deploying:**
1. Review changelog of updated packages
2. Run tests: `pdm run pytest`
3. Check for breaking changes
4. Test in staging/development first
5. Deploy during low-traffic period

**Rollback if Issues:**
```bash
git revert HEAD
pdm install
pdm run pytest
# Redeploy
```

---

## 19. Key References

### Inspiration

- [agentfs](https://github.com/tursodatabase/agentfs) — Filesystem as agent context
- [Everything is a file](https://turso.tech/blog/nothing-new-under-the-sun) — Unix philosophy for AI
- [How to build agents with filesystems and bash](https://vercel.com/blog/how-to-build-agents-with-filesystems-and-bash)
- [gpt-researcher](https://github.com/assafelovic/gpt-researcher) — Open source research agent
- [Elicit Reports](https://elicit.com/blog/introducing-elicit-reports) — Gold standard for deep research

### APIs

- [arXiv API](https://info.arxiv.org/help/api/index.html) — Free academic preprints
- [Semantic Scholar API](https://www.semanticscholar.org/product/api) — Free academic search
- [Gemini API](https://ai.google.dev/gemini-api) — LLM + Google Search

### Documentation

- [PydanticAI](https://ai.pydantic.dev/) — Agent framework
- [FastAPI](https://fastapi.tiangolo.com/) — Web framework
- [WeasyPrint](https://weasyprint.org/) — PDF generation from HTML

---

**End of PRD v2.0**
