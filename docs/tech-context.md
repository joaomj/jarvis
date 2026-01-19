# Technical Context: Jarvis Architecture

**Purpose:** Architecture source of truth for Jarvis Personal AI System
**Last Updated:** 2026-01-18
**Maintainer:** Development Team

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture Principles](#2-architecture-principelines)
3. [System Components](#3-system-components)
4. [Data Flow](#4-data-flow)
5. [Key Design Decisions](#5-key-design-decisions)
6. [Technology Stack](#6-technology-stack)
7. [Deployment Architecture](#7-deployment-architecture)
8. [Security Architecture](#8-security-architecture)
9. [Observability Strategy](#9-observability-strategy)
10. [Development Workflow](#10-development-workflow)

---

## 1. Overview

Jarvis is a self-hosted, sovereign personal AI assistant running on a local Mac Mini, accessible via Telegram through Cloudflare Tunnel. The system uses a multi-agent architecture with three conversation modes: Fast, Thinking, and Deep Research.

**Core Philosophy:** "Filesystem as Database" - User memories are stored as plain Markdown files, ensuring portability, transparency, and sovereignty.

**Key Characteristics:**
- Single-user system (no multi-user complexity)
- Local-first with cloud backup (Google Drive API)
- LLM-agnostic design (Gemini default, swappable)
- Comprehensive observability (logs, metrics, health checks)
- Resilient error handling with fallback mechanisms

---

## 2. Architecture Principles

### 2.1 Core Principles

1. **Simplicity over complexity:** Prefer the fewest moving parts that satisfy requirements
2. **Consistency over novelty:** Follow existing patterns; don't add tools/frameworks unless approved
3. **No assumptions:** Verify dependencies, versions, and APIs against codebase or docs
4. **Security by default:** Never expose or persist secrets
5. **Transparency:** All user data is human-readable (Markdown files)
6. **Fail gracefully:** System should continue operating even when components fail

### 2.2 Design Patterns

**Agent Pattern:**
- Each conversation mode is a separate agent with specialized tools
- Router Agent determines which agent to use based on user intent
- Agents are stateless; state is managed in SessionContext

**Repository Pattern:**
- Memory operations abstracted through `MemoryRepository`
- Database operations abstracted through `DatabaseRepository`
- Allows easy testing and future migration

**Observer Pattern:**
- Job queue observers for monitoring job lifecycle
- Metric collectors observe API calls and system events

---

## 3. System Components

### 3.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL INTERFACES                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│  │  Telegram    │    │  Cloudflare  │    │  Google      │                │
│  │  Bot API     │◄───┤  Tunnel      │◄───┤  Drive API   │                │
│  └──────────────┘    └──────────────┘    └──────────────┘                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            JARVIS APPLICATION                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         WEB LAYER                                  │    │
│  │  ┌─────────────────────────────────────────────────────────────┐   │    │
│  │  │  FastAPI Gateway                                         │   │    │
│  │  │  • /webhook/telegram (POST)                              │   │    │
│  │  │  • /health (GET)                                         │   │    │
│  │  │  • /metrics (GET)                                        │   │    │
│  │  └──────────────────┬──────────────────────────────────────┘   │    │
│  └─────────────────────┼───────────────────────────────────────────────┘    │
│                        │                                                   │
│  ┌─────────────────────┼───────────────────────────────────────────────┐    │
│  │                     ▼                                              │    │
│  │          ┌──────────────────────────┐                               │    │
│  │          │   SECURITY MIDDLEWARE    │                               │    │
│  │          │ • Token validation       │                               │    │
│  │          │ • Input sanitization     │                               │    │
│  │          │ • Rate limiting         │                               │    │
│  │          └──────────┬───────────────┘                               │    │
│  └─────────────────────┼───────────────────────────────────────────────┘    │
│                        │                                                   │
│  ┌─────────────────────┼───────────────────────────────────────────────┐    │
│  │                     ▼                                              │    │
│  │          ┌──────────────────────────┐                               │    │
│  │          │    ROUTER AGENT         │                               │    │
│  │          │ • Intent classification  │                               │    │
│  │          │ • Mode routing          │                               │    │
│  │          └───────┬────┬────┬───────┘                               │    │
│  └──────────────────┼────┼────┼───────────────────────────────────────┘    │
│                     │    │    │                                            │
│  ┌──────────────────┼────┼────┼───────────────────────────────────────┐    │
│  │                  │    │    │                                          │    │
│  │     ┌────────────▼─┐ ┌▼────────────┐ ┌─────────────────┐          │    │
│  │     │ CHAT FAST    │ │ CHAT THINK  │ │ DEEP RESEARCH    │          │    │
│  │     │ Agent        │ │ Agent       │ │ Orchestrator     │          │    │
│  │     │              │ │             │ │                  │          │    │
│  │     │ • 700 chars  │ │ • Deep      │ │ • Multi-source   │          │    │
│  │     │ • Fast LLM   │ │ • Pro LLM   │ │   coordination   │          │    │
│  │     └──────┬───────┘ └─────┬──────┘ └──────┬──────────┘          │    │
│  │            │                 │               │                       │    │
│  └────────────┼─────────────────┼───────────────┼─────────────────────┘    │
│               │                 │               │                             │
│  ┌────────────┴─────────────────┴───────────────┴─────────────────────────┐    │
│  │                        TOOLS LAYER                                     │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │    │
│  │  │ Memory   │  │ Web      │  │ Files    │  │ Citation │            │    │
│  │  │ Tools    │  │ Search   │  │ Parser   │  │ Tracker  │            │    │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │    │
│  └───────┼──────────────┼──────────────┼──────────────┼──────────────────┘    │
│          │              │              │              │                        │
│  ┌───────┼──────────────┼──────────────┼──────────────┼──────────────────┐    │
│  │       │              │              │              │                  │    │
│  │  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐         │    │
│  │  │ Memories/ │  │  arXiv   │  │  Gemini  │  │ Semantic │         │    │
│  │  │ Files    │  │  API     │  │  API     │  │ Scholar  │         │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘         │    │
│  │                                                                │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       DATA LAYER                                   │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │    │
│  │  │ SQLite DB    │  │ Filesystem   │  │ Job Queue    │          │    │
│  │  │ (chat logs, │  │ (memories,   │  │ (async jobs) │          │    │
│  │  │  jobs)      │  │  reports)    │  │              │          │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Layer Responsibilities

**Web Layer:**
- HTTP request/response handling
- Webhook processing
- Health checks and metrics endpoint
- API validation

**Security Layer:**
- Token validation (Telegram webhook secret)
- Input sanitization
- Rate limiting
- Prompt injection detection

**Agent Layer:**
- Intent classification (Router)
- Response generation (Fast, Thinking, Research)
- Tool orchestration
- Citation tracking

**Tools Layer:**
- Memory operations (search, read, save)
- Web search (Gemini + Google)
- File parsing (PDF, DOCX)
- Citation formatting

**Data Layer:**
- SQLite database (chat logs, job queue, costs)
- Filesystem (memories, reports)
- External APIs (Gemini, arXiv, Semantic Scholar)

---

## 4. Data Flow

### 4.1 Fast/Thinking Mode Flow

```
User Message (Telegram)
       │
       ▼
Webhook (FastAPI)
       │
       ▼
Security Middleware
• Validate token
• Sanitize input
• Check rate limit
       │
       ▼
Router Agent (Gemini Flash)
• Classify intent
• Route to mode
       │
       ▼
Chat Agent (Flash/Pro)
• Search memories
• Web search (if needed)
• Process attachments
• Generate response
• Track citations
       │
       ▼
Response Formatting
• Add citations
• Format for Telegram
• Truncate if needed (Fast mode)
       │
       ▼
Send to Telegram
       │
       ▼
Log to SQLite
       │
       ▼
Memory Extraction (async)
• Analyze conversation
• User confirmation
• Save to memories/
```

### 4.2 Deep Research Flow

```
User Request (Telegram)
       │
       ▼
Webhook → Security → Router → Research Orchestrator
       │
       ▼
Create Job (SQLite)
• Status: pending
• Save query and metadata
       │
       ▼
Background Task (asyncio)
┌─────────────────────────────────────────┐
│  1. Parse research question             │
│  2. Generate search queries            │
│  3. Collect sources (parallel):         │
│     • arXiv API                        │
│     • Semantic Scholar API              │
│     • Web search                       │
│  4. Rank sources by quality             │
│  5. Generate report sections (IMRaD)    │
│  6. Format citations (APA)              │
│  7. Generate PDF (WeasyPrint)          │
└─────────────────────────────────────────┘
       │
       ▼
Update Job: completed
       │
       ▼
Notify User (Telegram)
• "Your research report is ready"
• Attach PDF
       │
       ▼
Backup PDF to Google Drive
```

---

## 5. Key Design Decisions

### 5.1 Why "Filesystem as Database"?

**Decision:** Store user memories as plain Markdown files on the filesystem.

**Rationale:**
- **Portability:** Can move memories between devices by copying files
- **Queryability:** Use standard tools (`grep`, `find`, `ripgrep`) without special APIs
- **Transparency:** User can read exactly what the AI knows about them
- **Sovereignty:** No vendor lock-in, data remains under user control
- **Version Control:** Can use Git to track changes over time

**Trade-offs:**
- Slower search than dedicated databases (mitigated by grep/ripgrep performance)
- Manual organization required (simplified by folder structure)

### 5.2 Why SQLite for Job Queue?

**Decision:** Use SQLite instead of Redis/Celery for async job persistence.

**Rationale:**
- **Simplicity:** No additional infrastructure (no Redis server)
- **Sufficient:** Single-user system doesn't need distributed queue
- **Reliable:** ACID guarantees, no data loss on restart
- **Portable:** Single file, easy to backup

**Trade-offs:**
- Limited to single machine (acceptable for MVP)
- No distributed processing (not needed for single-user)

### 5.3 Why Google Drive API for Backup?

**Decision:** Use Google Drive API instead of Google Drive Desktop.

**Rationale:**
- **Programmatic control:** Automated backups, verification scripts
- **Cost-effective:** $0.002/GB/month, likely within free tier
- **Reliable:** API-based, no desktop app dependencies
- **Backup verification:** Automated checksums, integrity checks

**Trade-offs:**
- Requires OAuth setup (one-time)
- More complex than folder sync

### 5.4 Why Dockerize from Day 1?

**Decision:** Containerize entire application using Docker.

**Rationale:**
- **Cloud migration ready:** Easy to deploy to any cloud provider
- **Consistent environments:** Dev, staging, production identical
- **Isolation:** Dependencies isolated from host system
- **Reproducibility:** Same behavior across different machines

**Trade-offs:**
- Slight learning curve
- Larger deployment artifacts

### 5.5 Why GitHub Actions (Free Plan)?

**Decision:** Use GitHub Actions for CI/CD on free tier.

**Rationale:**
- **Free:** No cost for open-source or small private repos
- **Integrated:** Works seamlessly with GitHub PR workflow
- **Simple:** YAML configuration, no setup needed
- **Sufficient:** Lint, test, security scan all supported

**Trade-offs:**
- Limited compute time (6500 minutes/month)
- No custom runners (not needed for MVP)

---

## 6. Technology Stack

### 6.1 Core Technologies

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Runtime** | Python | 3.12+ | Application runtime |
| **Web Framework** | FastAPI | Latest | Async web server |
| **Agent Framework** | PydanticAI | Latest | Multi-agent orchestration |
| **Database** | SQLite + aiosqlite | Latest | Async database operations |
| **LLM** | Gemini (google-generativeai) | Latest | LLM + Google Search |
| **Messaging** | python-telegram-bot | Latest | Telegram integration |

### 6.2 Supporting Technologies

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Configuration** | pydantic-settings | Type-safe environment variables |
| **Logging** | structlog + loguru | Structured logging with rotation |
| **Metrics** | prometheus_client | Metrics for monitoring |
| **Retry Logic** | tenacity | Exponential backoff retries |
| **Rate Limiting** | slowapi | Telegram rate limiting |
| **File Parsing** | PyMuPDF, python-docx | PDF/DOCX extraction |
| **Report Gen** | WeasyPrint + Jinja2 | PDF generation |
| **Backup** | Google Drive API Python | Automated backups |
| **HTTP Client** | httpx | Async HTTP requests |

### 6.3 Development Tools

| Tool | Purpose |
|------|---------|
| **PDM** | Package management and dependency resolution |
| **pytest** | Testing framework |
| **ruff** | Linting and formatting |
| **Docker** | Containerization |
| **GitHub Actions** | CI/CD |

---

## 7. Deployment Architecture

### 7.1 Local Deployment (Mac Mini)

```
┌─────────────────────────────────────────────────────────────┐
│                     Mac Mini Host                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Cloudflare Tunnel (cloudflared)                      │  │
│  │  • Outbound-only connection to Cloudflare             │  │
│  │  • Exposes localhost:8000 to public URL              │  │
│  └────────────────────┬────────────────────────────────────┘  │
│                       │                                       │
│  ┌────────────────────┴────────────────────────────────────┐  │
│  │  Docker Container (jarvis)                             │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  FastAPI Application (uvicorn)                 │  │  │
│  │  │  Port: 8000                                     │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  │                                                       │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  SQLite Database (jarvis.db)                   │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  │                                                       │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  Memories (/app/memories)                      │  │  │
│  │  │  Facts, entities, conversations                 │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  │                                                       │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  Logs (jarvis.log)                            │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Google Drive Desktop (backup)                        │  │
│  │  • Syncs memories/ to personal Google Drive           │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
         │
         │ Outbound connection
         ▼
┌─────────────────────────────────────────────────────────────┐
│                 Cloudflare Network                          │
├─────────────────────────────────────────────────────────────┤
│  • WAF Rules (Telegram IPs only, POST only)               │
│  • DDoS Protection                                        │
│  • TLS Termination                                         │
│  • Public URL: https://your-domain.com                    │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                 Telegram Servers                           │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Cloud Deployment (Future)

**Target Providers:** AWS, GCP, Azure, DigitalOcean

**Migration Steps:**
1. Deploy Docker container to cloud (ECS, Cloud Run, App Service)
2. Use managed database (PostgreSQL, Cloud SQL) if needed
3. Use cloud storage (S3, GCS) for backups
4. Use Cloudflare Tunnel or direct HTTP access
5. Scale horizontally with load balancer (if needed)

---

## 8. Security Architecture

### 8.1 4-Layer Defense Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                          LAYER 1: NETWORK                         │
│  Cloudflare WAF                                                     │
│  • Allow only Telegram IPs (149.154.160.0/20, 91.108.4.0/22)      │
│  • Block non-POST to /webhook/telegram                             │
│  • Require application/json content-type                             │
│  • Rate limit 100 req/min/IP                                       │
│  • DDoS protection                                                 │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       LAYER 2: TRANSPORT                          │
│  Cloudflare Tunnel (TLS 1.3)                                       │
│  • Outbound-only connection (no incoming ports)                     │
│  • Named tunnel with secured credentials                            │
│  • Automatic HTTPS                                                 │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      LAYER 3: APPLICATION                          │
│  FastAPI Security Middleware                                       │
│  • X-Telegram-Bot-Api-Secret-Token validation (timing-safe)        │
│  • Input sanitization (unicode normalization, length limits)        │
│  • Rate limiting per user (30 msg/min)                             │
│  • Prompt injection detection + logging                             │
│  • Error message sanitization (no stack traces)                     │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         LAYER 4: HOST                             │
│  Mac Mini Security                                                 │
│  • macOS Firewall (stealth mode)                                   │
│  • FileVault full-disk encryption                                  │
│  • File permissions: .env (600), memories/ (750), db (600)         │
│  • Unnecessary services disabled                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 Threat Model

**Trusted:**
- Telegram user (owner, single user)
- Local Mac Mini host
- Cloudflare infrastructure

**Untrusted:**
- Internet traffic
- Telegram bot API (rate limited, validated)
- External APIs (validated responses)

**Attack Mitigations:**
- **Prompt Injection:** Detection + logging, input sanitization
- **DoS/DDoS:** Cloudflare WAF, rate limiting
- **Data Exfiltration:** No inbound ports, secrets never logged
- **Malicious Files:** Magic byte validation, size limits

---

## 9. Observability Strategy

### 9.1 Observability Stack

**Logs:** Structured JSON logs to `jarvis.log` (rotation: 100MB, keep 10 files)

**Metrics:** Prometheus metrics exposed at `/metrics` endpoint

**Health:** Health check endpoint `/health` with dependency status

**Tracing:** Request tracing with `request_id` through all components

**Alerting:** Log-based alerts (ERROR, CRITICAL levels), metric thresholds

### 9.2 Key Metrics

| Metric | Type | Alert Threshold |
|--------|------|----------------|
| `jarvis_api_errors_total` | Counter | Error rate >10% |
| `jarvis_jobs_failed_total` | Counter | Failure rate >20% |
| `jarvis_disk_space_percent` | Gauge | <10% free |
| `jarvis_llm_cost_usd` | Gauge | >75% of budget |

### 9.3 Monitoring Dashboard

**Endpoints:**
- `/health` - System health (JSON)
- `/metrics` - Prometheus metrics (text format)
- `/metrics/cost` - Cost tracking (JSON)

**Tools:**
- Logs: `tail -f jarvis.log` or log viewer
- Metrics: Prometheus + Grafana (future)
- Health: Simple HTTP check

---

## 10. Development Workflow

### 10.1 Branch Strategy

```
main (production)
  │
  ├── feature/<name> (new features)
  ├── bugfix/<name> (bug fixes)
  ├── hotfix/<name> (urgent fixes)
  ├── docs/<name> (documentation)
  └── refactor/<name> (code refactoring)
```

### 10.2 Commit Convention

**Format:** `<type>(<scope>): <subject>`

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting (no logic change)
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**
- `feat(agents): add deep research orchestrator`
- `fix(webhook): handle missing user_id gracefully`
- `docs(readme): update installation instructions`

### 10.3 Testing Strategy

**Unit Tests:** Test individual functions and classes in isolation

**Integration Tests:** Test interactions between components (no external mocks)

**E2E Tests:** Test complete user flows against real APIs

**Coverage Target:** 80%+ on critical paths (agents, memory, API)

### 10.4 Code Quality

**Linting:** `pdm run ruff check`

**Formatting:** `pdm run ruff format`

**Type Checking:** Optional `mypy` (future)

**Security:** `pdm audit` + manual review

---

## Appendix

### A. Environment Variables Reference

See `.env.example` for complete list of configuration variables.

### B. Directory Structure

See PRDv2.md, Section 7 for complete directory structure.

### C. API Endpoints

See `src/jarvis/main.py` for endpoint definitions.

### D. External Dependencies

**Required Accounts:**
- Telegram Bot Account (via @BotFather)
- Google Cloud Account (Gemini API)
- Cloudflare Account (Tunnel)

**Required APIs:**
- Telegram Bot API (free)
- Gemini API (free tier or paid)
- arXiv API (free, no auth)
- Semantic Scholar API (free with API key)
- Google Drive API (free tier)

---

**Document Status:** Active
**Next Review:** 2026-02-18
**Change History:**
- 2026-01-18: Initial creation (v1.0)
