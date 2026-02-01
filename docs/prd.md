# Product Requirements Document (PRD)
## Jarvis: Personal AI Assistant with Telegram Interface

**Version**: 1.0.0  
**Author**: Jarvis Development Team  
**Last Updated**: 2026-01-31  
**Status**: Draft - Pending Approval

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals and Non-Goals](#3-goals-and-non-goals)
4. [User Personas](#4-user-personas)
5. [User Stories and Use Cases](#5-user-stories-and-use-cases)
6. [Functional Requirements](#6-functional-requirements)
7. [Non-Functional Requirements](#7-non-functional-requirements)
8. [System Architecture](#8-system-architecture)
9. [Data Architecture](#9-data-architecture)
10. [Security Design](#10-security-design)
11. [Observability Design](#11-observability-design)
12. [API Specifications](#12-api-specifications)
13. [Technical Specifications](#13-technical-specifications)
14. [Dependencies and Third-Party Integrations](#14-dependencies-and-third-party-integrations)
15. [Deployment Architecture](#15-deployment-architecture)
16. [Risks and Mitigations](#16-risks-and-mitigations)
17. [Implementation Phases](#17-implementation-phases)
18. [Success Metrics](#18-success-metrics)
19. [Open Questions](#19-open-questions)
20. [Appendices](#20-appendices)

---

## 1. Executive Summary

### 1.1 Vision

Jarvis is a personal AI assistant accessible via Telegram that provides a unified, continuous chat experience. Unlike traditional chatbots with fragmented thread-based UIs, Jarvis presents a single conversation stream where context management, memory organization, and tool selection happen transparently in the background.

### 1.2 Core Value Proposition

- **Single continuous chat**: No thread management, no chat history navigation
- **Mobile-first**: Full functionality via Telegram on iPhone
- **Privacy-respecting**: User owns all data (Syncthing-portable)
- **Provider-agnostic**: Switch LLM providers without lock-in
- **Security-constrained**: Limited write permissions, user allowlist

### 1.3 MVP Scope

The first release focuses on the highest-pain use case: **summarizing saved X (Twitter) threads and Substack articles**. Users send a URL via Telegram, receive a summary, and the original content is archived as markdown.

---

## 2. Problem Statement

### 2.1 Current Pain Points

| Pain Point | Severity | Current Workaround |
|------------|----------|-------------------|
| Hundreds of saved X threads, no time to read | **Critical** | Ignore them, lose knowledge |
| Substack newsletters pile up unread | **High** | Skim headlines only |
| ChatGPT/Claude thread UI is overwhelming | **Medium** | Create new chat each time, lose context |
| Cannot access AI assistant on mobile easily | **High** | Wait until at computer |
| AI assistants have too much system access | **Medium** | Use sandboxed web versions only |
| Chat history not portable | **Medium** | Manual exports, lock-in |

### 2.2 Root Causes

1. **Information overload**: More content saved than time to consume
2. **Fragmented interfaces**: Each AI tool has its own UI paradigm
3. **Context switching cost**: Moving between tools breaks flow
4. **Trust deficit**: Giving AI agents full system access feels risky

### 2.3 Opportunity

Create a **personal consigliere** that:
- Lives where the user already is (Telegram on phone)
- Handles information triage and summarization
- Maintains continuous context without user management
- Operates within strict security boundaries

---

## 3. Goals and Non-Goals

### 3.1 Goals (MVP)

| ID | Goal | Success Criteria |
|----|------|------------------|
| G1 | Summarize X threads via Telegram | URL in -> summary out in <30s |
| G2 | Summarize Substack articles | URL in -> summary out in <30s |
| G3 | Archive original content as markdown | Syncthing-synced, grep-able |
| G4 | Voice message support | Whisper transcription, text response |
| G5 | General chat via OpenCode | Passthrough to OpenCode server |
| G6 | Single user security | Only owner can interact |
| G7 | Portable data | All data in filesystem, Syncthing-ready |

### 3.2 Goals (Post-MVP)

| ID | Goal | Phase |
|----|------|-------|
| G8 | Conversation modes (Fast/Thinking) | Phase 2 |
| G9 | PDF/file upload and discussion | Phase 2 |
| G10 | Private mode (unlogged conversations) | Phase 2 |
| G11 | Remote OpenCode project control | Phase 3 |
| G12 | Google Calendar alerts | Phase 4 |
| G13 | Weather notifications | Phase 4 |
| G14 | Deep Research reports | Phase 5 |
| G15 | Memory/learning system | Phase 6 |

### 3.3 Non-Goals (Explicit Exclusions)

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

## 4. User Personas

### 4.1 Primary Persona: The Knowledge Worker

**Name**: Joao  
**Role**: Software Engineer / Researcher  
**Devices**: Mac Mini M4 (home), iPhone 16 (mobile)

**Behaviors**:
- Saves 10-20 X threads per week, reads <5%
- Subscribes to 15+ Substack newsletters
- Works on personal coding projects
- Values privacy and data ownership
- Prefers terminal/CLI over GUI applications

**Frustrations**:
- "I save everything but read nothing"
- "ChatGPT threads are a mess after 3 months"
- "I can't access my AI tools easily on mobile"
- "I don't trust AI agents with full system access"

**Goals**:
- Triage information faster
- Maintain context across conversations
- Access AI assistant anywhere
- Own and control all conversation data

---

## 5. User Stories and Use Cases

### 5.1 Epic 1: URL Summarization (MVP)

#### US-1.1: Summarize X Thread
```
AS A user
I WANT TO send an X thread URL to Telegram
SO THAT I can get a summary without reading the full thread
```

**Acceptance Criteria**:
- [ ] Accepts URLs: `x.com/*/status/*`, `twitter.com/*/status/*`
- [ ] Extracts full thread (all posts in conversation)
- [ ] Saves original content as `data/articles/x-{date}-{slug}.md`
- [ ] Returns summary via Telegram (<4096 chars)
- [ ] Includes author, date, tweet count in response
- [ ] Completes in <30 seconds

**Flow**:
```
User: /summarize https://x.com/karpathy/status/1234567890
Bot: Fetching thread...
Bot: [Summary]
     Author: @karpathy
     Thread: 12 tweets
     Saved to: x-2026-01-31-karpathy-on-ai.md
```

#### US-1.2: Summarize Substack Article
```
AS A user
I WANT TO send a Substack URL to Telegram
SO THAT I can get the key points without reading 20 minutes
```

**Acceptance Criteria**:
- [ ] Accepts URLs: `*.substack.com/*`
- [ ] Extracts article title, author, content
- [ ] Saves original as `data/articles/substack-{date}-{slug}.md`
- [ ] Returns summary with key takeaways
- [ ] Handles paywalled content gracefully (error message)

#### US-1.3: Summarize Generic URL
```
AS A user
I WANT TO send any article URL
SO THAT I can get a quick summary of blog posts, news, etc.
```

**Acceptance Criteria**:
- [ ] Falls back to trafilatura extraction
- [ ] Handles most news sites, blogs, documentation
- [ ] Saves original content with source metadata

### 5.2 Epic 2: Voice Interaction (MVP)

#### US-2.1: Voice Message Transcription
```
AS A user
I WANT TO send voice messages to the bot
SO THAT I can interact hands-free
```

**Acceptance Criteria**:
- [ ] Accepts Telegram voice messages (OGG format)
- [ ] Transcribes using local Whisper (small model)
- [ ] Processes transcribed text as regular message
- [ ] Responds with text only (no audio)
- [ ] Max voice duration: 60 seconds
- [ ] Transcription completes in <10 seconds

### 5.3 Epic 3: General Chat (MVP)

#### US-3.1: Chat Passthrough
```
AS A user
I WANT TO chat with the AI about any topic
SO THAT I can get answers without switching tools
```

**Acceptance Criteria**:
- [ ] Messages without commands forwarded to OpenCode
- [ ] OpenCode session persists across messages
- [ ] Responses formatted for Telegram markdown
- [ ] Long responses split at natural boundaries

### 5.4 Epic 4: Security (MVP)

#### US-4.1: User Allowlist
```
AS the system owner
I WANT TO restrict access to my Telegram user ID
SO THAT no one else can interact with my assistant
```

**Acceptance Criteria**:
- [ ] `TELEGRAM_ALLOWED_USERS` env var (comma-separated IDs)
- [ ] Unauthorized users receive no response (silent ignore)
- [ ] All unauthorized attempts logged with user info

---

## 6. Functional Requirements

### 6.1 Message Processing

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Parse incoming Telegram messages (text, voice, files) | P0 |
| FR-2 | Route messages based on command prefix | P0 |
| FR-3 | Inject correlation ID at gateway entry | P0 |
| FR-4 | Support `/summarize <url>` command | P0 |
| FR-5 | Support `/help` command | P0 |
| FR-6 | Support `/private <message>` command | P1 |
| FR-7 | Support `/mode <fast|thinking>` command | P1 |
| FR-8 | Forward non-command text to OpenCode | P0 |
| FR-9 | Transcribe voice messages via Whisper | P0 |
| FR-10 | Format responses for Telegram markdown | P0 |

### 6.2 Content Extraction

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-11 | Extract X threads via GraphQL API | P0 |
| FR-12 | Fall back to Playwright if API fails | P1 |
| FR-13 | Extract Substack articles (public) | P0 |
| FR-14 | Extract generic articles via trafilatura | P0 |
| FR-15 | Handle extraction errors gracefully | P0 |
| FR-16 | Cache extracted content to avoid re-fetch | P2 |

### 6.3 Storage

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-17 | Save articles as markdown with YAML frontmatter | P0 |
| FR-18 | Save summaries as separate markdown files | P0 |
| FR-19 | Use naming convention: `{source}-{date}-{slug}.md` | P0 |
| FR-20 | Store conversation history as JSONL | P0 |
| FR-21 | Support Syncthing folder structure | P0 |

### 6.4 OpenCode Integration

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-22 | Create/manage OpenCode sessions via HTTP API | P0 |
| FR-23 | Send prompts to OpenCode session | P0 |
| FR-24 | Receive and parse OpenCode responses | P0 |
| FR-25 | Handle OpenCode SSE events (future) | P2 |

---

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

## 8. System Architecture

### 8.1 High-Level Architecture

```
+---------------------------------------------------------------------------------+
|                                   INTERNET                                       |
|                                                                                  |
|    +--------------+                                    +--------------+         |
|    |   Telegram   |                                    |   OpenCode   |         |
|    |   Servers    |                                    |     Zen      |         |
|    +------+-------+                                    +------+-------+         |
|           |                                                   |                  |
|           | HTTPS (webhook)                                   | HTTPS (API)     |
|           v                                                   |                  |
+-----------------------------------+---------------|---------------+---------------+
|                              TAILSCALE MESH                   |                  |
|                                                               |                  |
|    +--------------------------------------------------------------------------+ |
|    |                         MAC MINI (M4, 16GB)              |               | |
|    |                                                          |               | |
|    |    +-------------------------------------------------------------------+ | |
|    |    |                    DOCKER COMPOSE                   |              | | |
|    |    |                                                     |              | | |
|    |    |   +-------------+    +-------------+    +-----------+----+         | | |
|    |    |   |   Jarvis    |--->|   OpenCode  |<---|               |         | | |
|    |    |   |   Gateway   |    |   Server    |    |   LLM APIs    |         | | |
|    |    |   |   :8080     |    |   :4096     |    |               |         | | |
|    |    |   +------+------+    +-------------+    +---------------+         | | |
|    |    |          |                                                        | | |
|    |    |          |           +-------------+                             | | |
|    |    |          |           |   Whisper   |                             | | |
|    |    |          +---------->|   (small)   |                             | | |
|    |    |                      +-------------+                             | | |
|    |    |                                                                   | | |
|    |    |   +-------------------------------------------------------------------+ | |
|    |    |   |                      SHARED VOLUME                        |  | | |
|    |    |   |                                                           |  | | |
|    |    |   |   data/                                                   |  | | |
|    |    |   |   |-- articles/     (original content)                    |  | | |
|    |    |   |   |-- summaries/    (generated summaries)                 |  | | |
|    |    |   |   |-- conversations/(chat history JSONL)                  |  | | |
|    |    |   |   |-- memories/     (agent learnings)                     |  | | |
|    |    |   |   `-- logs/         (structured JSON logs)                |  | | |
|    |    |   |                                                           |  | | |
|    |    |   +-----------------------------------------------------------+  | | |
|    |    |                              |                                   | | |
|    |    |   +-------------+           |                                   | | |
|    |    |   |  Syncthing  |<----------+                                   | | |
|    |    |   |   :8384     |                                               | | |
|    |    |   +------+------+                                               | | |
|    |    |          |                                                       | | |
|    +----+----------|-------------------------------------------------------+ | |
|                    |                                                          | |
|                    | Syncthing Protocol                                       | |
|                    v                                                          | |
|    +-----------------------------------+                                        |
|    |          OTHER DEVICES            |                                        |
|    |   (iPhone, MacBook, NAS, etc.)    |                                        |
|    +-----------------------------------+                                        |
|                                                                                  |
+----------------------------------------------------------------------------------+
```

### 8.2 Component Diagram

```
+-----------------------------------------------------------------------------+
|                              JARVIS APPLICATION                              |
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  |                           GATEWAY LAYER                                 | |
|  |                                                                         | |
|  |  +---------------+  +---------------+  +---------------+               | |
|  |  |    Webhook    |  |    Message    |  |   Correlation |               | |
|  |  |    Handler    |->|    Router     |->|   ID Injector |               | |
|  |  +---------------+  +---------------+  +---------------+               | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                    |                                         |
|                                    v                                         |
|  +------------------------------------------------------------------------+ |
|  |                           TELEGRAM LAYER                                | |
|  |                                                                         | |
|  |  +---------------+  +---------------+  +---------------+               | |
|  |  |    Message    |  |    Security   |  |   Response    |               | |
|  |  |    Parser     |  |   (Allowlist) |  |   Formatter   |               | |
|  |  +---------------+  +---------------+  +---------------+               | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                    |                                         |
|                                    v                                         |
|  +------------------------------------------------------------------------+ |
|  |                             CORE LAYER                                  | |
|  |                                                                         | |
|  |  +---------------+  +---------------+  +---------------+               | |
|  |  |   Summarizer  |  |     Chat      |  |    Storage    |               | |
|  |  |               |  |   Handler     |  |    Manager    |               | |
|  |  +-------+-------+  +-------+-------+  +---------------+               | |
|  |          |                  |                                           | |
|  |          v                  v                                           | |
|  |  +---------------+  +---------------+                                  | |
|  |  |   Extractor   |  |   OpenCode    |                                  | |
|  |  |   (X, Web)    |  |    Client     |                                  | |
|  |  +---------------+  +---------------+                                  | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                    |                                         |
|                                    v                                         |
|  +------------------------------------------------------------------------+ |
|  |                            VOICE LAYER                                  | |
|  |                                                                         | |
|  |  +---------------+  +---------------+                                  | |
|  |  |   Transcriber |  |    Audio      |                                  | |
|  |  |   (Whisper)   |  |   Processor   |                                  | |
|  |  +---------------+  +---------------+                                  | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
+------------------------------------------------------------------------------+
```

### 8.3 Sequence Diagram: URL Summarization

```
+------+     +---------+     +---------+     +----------+     +---------+     +---------+
| User |     |Telegram |     | Gateway |     |Extractor |     |OpenCode |     | Storage |
+--+---+     +----+----+     +----+----+     +-----+----+     +----+----+     +----+----+
   |              |               |               |                |               |
   | /summarize   |               |               |                |               |
   | x.com/...    |               |               |                |               |
   |------------->|               |               |                |               |
   |              |   Webhook     |               |                |               |
   |              |-------------->|               |                |               |
   |              |               |               |                |               |
   |              |               | Inject        |                |               |
   |              |               | correlation_id|                |               |
   |              |               |---------------|                |               |
   |              |               |               |                |               |
   |              |               | Extract URL   |                |               |
   |              |               |-------------->|                |               |
   |              |               |               |                |               |
   |              |               |               | GraphQL API    |               |
   |              |               |               |--------------->|               |
   |              |               |               |<---------------|               |
   |              |               |               |                |               |
   |              |               |<--------------|                |               |
   |              |               | Thread content|                |               |
   |              |               |               |                |               |
   |              |               | Save original |                |               |
   |              |               |---------------|----------------|-------------->|
   |              |               |               |                |               |
   |              |               | Summarize     |                |               |
   |              |               |---------------|--------------->|               |
   |              |               |               |                |               |
   |              |               |<--------------|----------------|               |
   |              |               | Summary       |                |               |
   |              |               |               |                |               |
   |              |               | Save summary  |                |               |
   |              |               |---------------|----------------|-------------->|
   |              |               |               |                |               |
   |              | Send response |               |                |               |
   |              |<--------------|               |                |               |
   |              |               |               |                |               |
   |<-------------|               |               |                |               |
   | Summary msg  |               |               |                |               |
   |              |               |               |                |               |
```

---

## 9. Data Architecture

### 9.1 Folder Structure

```
data/                                    # Root data directory (Syncthing-synced)
|-- articles/                            # Original extracted content
|   |-- x-2026-01-31-karpathy-llm.md
|   |-- x-2026-01-30-andrej-backprop.md
|   |-- substack-2026-01-31-stratechery.md
|   `-- web-2026-01-31-some-blog.md
|
|-- summaries/                           # Generated summaries
|   |-- x-2026-01-31-karpathy-llm.md
|   `-- substack-2026-01-31-stratechery.md
|
|-- conversations/                       # Chat history (append-only JSONL)
|   |-- 2026-01-31.jsonl
|   |-- 2026-01-30.jsonl
|   `-- .index.json                     # Quick lookup index
|
|-- memories/                            # Future: Agent learnings
|   |-- user-preferences.yaml
|   `-- learned-facts.md
|
|-- voice/                               # Temporary voice files (auto-cleaned)
|   `-- .gitkeep
|
|-- logs/                                # Structured application logs
|   |-- jarvis-2026-01-31.jsonl
|   `-- jarvis-2026-01-30.jsonl
|
`-- config/                              # User configuration
    |-- user.yaml                        # User preferences
    `-- x-cookies.json                   # X authentication (encrypted)
```

### 9.2 Article Markdown Schema

```yaml
# Frontmatter
---
source: x | substack | web
url: https://original-url.com
title: "Article Title"
author: "@username"
author_name: "Full Name"
fetched_at: 2026-01-31T14:30:00Z
correlation_id: abc-123-def
tweet_count: 12                         # X threads only
word_count: 1500
reading_time_minutes: 7
tags: []                                 # Future: auto-generated
---

# Article Title

Original content in markdown format...

## Thread (for X)

### Tweet 1
Content...

### Tweet 2
Content...
```

### 9.3 Conversation JSONL Schema

```json
{
  "id": "msg-uuid-123",
  "timestamp": "2026-01-31T14:30:00Z",
  "correlation_id": "req-abc-123",
  "direction": "incoming|outgoing",
  "type": "text|voice|command|file",
  "command": "/summarize",
  "content": "Message content...",
  "metadata": {
    "telegram_message_id": 12345,
    "telegram_chat_id": 67890,
    "voice_duration_seconds": 15,
    "opencode_session_id": "ses-xyz"
  },
  "private": false
}
```

### 9.4 Log Entry Schema

```json
{
  "timestamp": "2026-01-31T14:30:00.123Z",
  "level": "INFO",
  "correlation_id": "req-abc-123",
  "service": "jarvis.gateway",
  "event": "summarize_complete",
  "data": {
    "url": "https://x.com/...",
    "duration_ms": 2500,
    "tokens_used": 1200,
    "source": "x"
  }
}
```

---

## 10. Security Design

### 10.1 Threat Model

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| Telegram bot token leaked | Medium | High | Allowlist, rate limit, monitoring |
| Unauthorized user access | Medium | Medium | User ID allowlist (silent ignore) |
| X account restricted | Medium | Low | Fallback to Playwright, cookie rotation |
| Mac Mini compromised via bot | Low | Critical | No public ports, Tailscale only |
| Secrets in logs | Medium | High | structlog filtering, no secrets logged |
| Data exfiltration | Low | Medium | Syncthing encryption, local storage |

### 10.2 Security Controls

```
+-----------------------------------------------------------------------------+
|                              SECURITY LAYERS                                 |
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  | LAYER 1: NETWORK                                                        | |
|  |                                                                         | |
|  |  [x] No public ports exposed                                           | |
|  |  [x] Tailscale mesh VPN (100.x.x.x addresses only)                     | |
|  |  [x] Telegram webhook via Tailscale Funnel (HTTPS)                     | |
|  |  [x] Internal services communicate via Docker network                   | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  | LAYER 2: AUTHENTICATION                                                 | |
|  |                                                                         | |
|  |  [x] Telegram user ID allowlist (env: TELEGRAM_ALLOWED_USERS)          | |
|  |  [x] Unauthorized requests silently ignored (no response)               | |
|  |  [x] All auth failures logged with user info                           | |
|  |  [x] OpenCode server password (env: OPENCODE_SERVER_PASSWORD)          | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  | LAYER 3: AUTHORIZATION                                                  | |
|  |                                                                         | |
|  |  [x] Rate limiting: 10 requests/minute per user                        | |
|  |  [x] Command allowlist (no arbitrary shell execution)                   | |
|  |  [x] File write restricted to data/ directory                          | |
|  |  [x] No email/X write operations (read-only external access)           | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  | LAYER 4: DATA PROTECTION                                                | |
|  |                                                                         | |
|  |  [x] Secrets in .env only (never in code, configs, or logs)            | |
|  |  [x] X cookies encrypted at rest                                       | |
|  |  [x] Private mode: /private messages not logged                        | |
|  |  [x] Log sanitization (filter sensitive patterns)                      | |
|  |  [x] Syncthing encryption for sync (optional)                          | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  | LAYER 5: AUDIT                                                          | |
|  |                                                                         | |
|  |  [x] All requests logged with correlation ID                           | |
|  |  [x] All LLM API calls logged (tokens, duration, model)                | |
|  |  [x] All file writes logged                                            | |
|  |  [x] Failed auth attempts logged with context                          | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
+------------------------------------------------------------------------------+
```

### 10.3 Secret Management

| Secret | Storage | Rotation |
|--------|---------|----------|
| `TELEGRAM_BOT_TOKEN` | .env | On compromise |
| `OPENCODE_ZEN_API_KEY` | .env | Monthly |
| `OPENCODE_SERVER_PASSWORD` | .env | On compromise |
| `X_AUTH_TOKEN` | data/config/x-cookies.json (encrypted) | On expiry |
| `X_CT0` | data/config/x-cookies.json (encrypted) | On expiry |

---

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

## 12. API Specifications

### 12.1 Internal Message Format

All internal communication uses this envelope:

```python
@dataclass
class JarvisMessage:
    correlation_id: str
    timestamp: datetime
    source: Literal["telegram", "voice", "internal"]
    user_id: int
    
    # Parsed content
    command: str | None  # e.g., "summarize", "help", None for chat
    text: str
    url: str | None
    file_path: str | None
    
    # Flags
    private: bool = False
    
    # Metadata
    telegram_message_id: int | None = None
    voice_duration_seconds: float | None = None
```

### 12.2 OpenCode HTTP API Usage

```python
# Session creation
POST /session
Body: {"title": "jarvis-telegram"}
Response: {"id": "ses-123", ...}

# Send message
POST /session/{id}/message
Body: {
    "model": {"providerID": "opencode", "modelID": "zen-default"},
    "parts": [{"type": "text", "text": "Summarize this: ..."}]
}
Response: {"info": {...}, "parts": [...]}

# Health check
GET /global/health
Response: {"healthy": true, "version": "1.2.3"}
```

### 12.3 X GraphQL API (Reverse-Engineered)

Based on baoyu-skills implementation:

```python
# Headers required
headers = {
    "Authorization": f"Bearer {BEARER_TOKEN}",  # Static app token
    "Cookie": f"auth_token={X_AUTH_TOKEN}; ct0={X_CT0}",
    "X-Csrf-Token": X_CT0,
    "Content-Type": "application/json",
}

# TweetDetail query
POST https://x.com/i/api/graphql/{query_id}/TweetDetail
Body: {
    "variables": {
        "focalTweetId": "1234567890",
        "with_rux_injections": false,
        ...
    },
    "features": {...}
}
```

---

## 13. Technical Specifications

### 13.1 Technology Stack

| Component | Technology | Version | Rationale |
|-----------|------------|---------|-----------|
| Language | Python | 3.11+ | Type hints, async, ecosystem |
| Package Manager | PDM | Latest | Modern, lockfile, PEP 621 |
| HTTP Server | AIOHTTP | 3.9+ | Async, lightweight, mature |
| Telegram SDK | python-telegram-bot | 21+ | Async, well-maintained |
| HTTP Client | httpx | 0.27+ | Async, HTTP/2, modern |
| Config | pydantic-settings | 2.0+ | Validation, .env support |
| Logging | structlog | 24.0+ | JSON, correlation ID native |
| X Extraction | httpx + custom | - | Port of baoyu-skills GraphQL |
| Web Extraction | trafilatura | 1.12+ | Best for articles/blogs |
| Browser Fallback | playwright | 1.40+ | Stealth mode for X |
| STT | faster-whisper | 1.0+ | CTranslate2, M4 optimized |
| Markdown | python-frontmatter | 1.1+ | YAML frontmatter parsing |
| Testing | pytest + pytest-asyncio | 8.0+ | Async test support |
| Linting | ruff | 0.5+ | Fast, replaces flake8+isort+black |
| Type Checking | mypy | 1.10+ | Strict mode |
| Container | Docker + Compose | 24+ | Isolation, reproducibility |
| Sync | Syncthing | 1.27+ | P2P, encrypted, no cloud |

### 13.2 Python Dependencies

```toml
[project]
name = "jarvis"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    # Core
    "aiohttp>=3.9",
    "python-telegram-bot>=21",
    "httpx>=0.27",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    
    # Logging
    "structlog>=24.0",
    
    # Content extraction
    "trafilatura>=1.12",
    "playwright>=1.40",
    
    # Voice
    "faster-whisper>=1.0",
    
    # Storage
    "python-frontmatter>=1.1",
    "aiofiles>=24.0",
    
    # Utils
    "python-slugify>=8.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "ruff>=0.5",
    "mypy>=1.10",
    "pre-commit>=3.7",
]
```

### 13.3 File Structure

```
jarvis/
|-- src/
|   |-- jarvis/
|   |   |-- __init__.py
|   |   |-- __main__.py              # Entry point
|   |   |-- config.py                # pydantic-settings config
|   |   |-- logging.py               # structlog setup
|   |   |
|   |   |-- gateway/
|   |   |   |-- __init__.py
|   |   |   |-- server.py            # AIOHTTP server
|   |   |   |-- context.py           # Request context (correlation ID)
|   |   |   `-- middleware.py        # Logging, error handling
|   |   |
|   |   |-- telegram/
|   |   |   |-- __init__.py
|   |   |   |-- bot.py               # Bot setup, webhook
|   |   |   |-- handlers.py          # Command handlers
|   |   |   |-- parser.py            # Message parsing
|   |   |   |-- formatter.py         # Response formatting
|   |   |   `-- security.py          # Allowlist, rate limiting
|   |   |
|   |   |-- extractors/
|   |   |   |-- __init__.py
|   |   |   |-- base.py              # Abstract extractor
|   |   |   |-- x_graphql.py         # X GraphQL API
|   |   |   |-- x_playwright.py      # X Playwright fallback
|   |   |   |-- substack.py          # Substack extractor
|   |   |   `-- web.py               # Generic web (trafilatura)
|   |   |
|   |   |-- opencode/
|   |   |   |-- __init__.py
|   |   |   |-- client.py            # HTTP client wrapper
|   |   |   `-- session.py           # Session management
|   |   |
|   |   |-- core/
|   |   |   |-- __init__.py
|   |   |   |-- summarizer.py        # Summarization logic
|   |   |   |-- chat.py              # Chat passthrough
|   |   |   `-- storage.py           # Article/conversation storage
|   |   |
|   |   `-- voice/
|   |       |-- __init__.py
|   |       `-- transcriber.py       # Whisper integration
|   |
|   `-- py.typed                     # PEP 561 marker
|
|-- tests/
|   |-- __init__.py
|   |-- conftest.py                  # pytest fixtures
|   |-- test_extractors/
|   |   |-- test_x_graphql.py
|   |   `-- test_web.py
|   |-- test_telegram/
|   |   |-- test_parser.py
|   |   `-- test_security.py
|   `-- test_core/
|       `-- test_summarizer.py
|
|-- data/                            # Runtime data (gitignored)
|   `-- .gitkeep
|
|-- docs/
|   |-- what-i-want.md               # (existing)
|   |-- jarvis-ideal.md              # (existing)
|   |-- prd.md                       # This document
|   `-- deployment.md                # Deployment guide
|
|-- scripts/
|   `-- setup-x-cookies.py           # Helper to get X cookies
|
|-- docker-compose.yml
|-- Dockerfile
|-- pyproject.toml
|-- .env.example
|-- .pre-commit-config.yaml
|-- .gitignore                       # (existing)
|-- LICENSE                          # (existing)
`-- AGENTS.md                        # OpenCode project config
```

---

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

## 15. Deployment Architecture

### 15.1 Docker Compose Configuration

```yaml
version: "3.9"

services:
  jarvis:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: jarvis-gateway
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - JARVIS_ENV=production
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_ALLOWED_USERS=${TELEGRAM_ALLOWED_USERS}
      - TELEGRAM_WEBHOOK_URL=${TELEGRAM_WEBHOOK_URL}
      - OPENCODE_URL=http://opencode:4096
      - OPENCODE_SERVER_PASSWORD=${OPENCODE_SERVER_PASSWORD}
      - WHISPER_MODEL=small
      - X_AUTH_TOKEN=${X_AUTH_TOKEN}
      - X_CT0=${X_CT0}
      - LOG_LEVEL=INFO
    volumes:
      - jarvis-data:/app/data
    depends_on:
      opencode:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  opencode:
    image: ghcr.io/anomalyco/opencode:latest
    container_name: jarvis-opencode
    restart: unless-stopped
    command: serve --hostname 0.0.0.0 --port 4096
    environment:
      - OPENCODE_ZEN_API_KEY=${OPENCODE_ZEN_API_KEY}
      - OPENCODE_SERVER_PASSWORD=${OPENCODE_SERVER_PASSWORD}
    volumes:
      - jarvis-data:/app/data
      - opencode-config:/root/.config/opencode
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4096/global/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  syncthing:
    image: syncthing/syncthing:latest
    container_name: jarvis-syncthing
    hostname: jarvis-sync
    restart: unless-stopped
    environment:
      - PUID=1000
      - PGID=1000
    volumes:
      - jarvis-data:/var/syncthing/data
      - syncthing-config:/var/syncthing/config
    ports:
      - "8384:8384"   # Web UI (local only)
      - "22000:22000" # Sync protocol

volumes:
  jarvis-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ${PWD}/data
  opencode-config:
  syncthing-config:

networks:
  default:
    name: jarvis-network
```

### 15.2 Dockerfile

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install PDM
RUN pip install --no-cache-dir pdm

# Copy dependency files
COPY pyproject.toml pdm.lock ./

# Install dependencies (production only)
RUN pdm install --prod --no-lock --no-editable

# Copy application
COPY src/ ./src/

# Create non-root user
RUN useradd -m -u 1000 jarvis && chown -R jarvis:jarvis /app
USER jarvis

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run application
CMD ["pdm", "run", "python", "-m", "jarvis"]
```

### 15.3 Tailscale Webhook Setup

```bash
# 1. Install Tailscale on Mac Mini (if not already)
brew install tailscale

# 2. Enable Tailscale Funnel for HTTPS webhook
tailscale funnel --bg 8080

# 3. Get your Funnel URL
tailscale funnel status
# Output: https://jarvis.tailnet-name.ts.net -> http://127.0.0.1:8080

# 4. Set Telegram webhook
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
    -H "Content-Type: application/json" \
    -d '{"url": "https://jarvis.tailnet-name.ts.net/webhook"}'

# 5. Verify webhook
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
```

### 15.4 Environment Variables

```bash
# .env.example

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_ALLOWED_USERS=12345678,87654321
TELEGRAM_WEBHOOK_URL=https://jarvis.tailnet-name.ts.net/webhook

# OpenCode
OPENCODE_ZEN_API_KEY=zen_...
OPENCODE_SERVER_PASSWORD=your-secure-password
OPENCODE_URL=http://opencode:4096

# X (Twitter)
X_AUTH_TOKEN=your-auth-token
X_CT0=your-ct0-token

# Whisper
WHISPER_MODEL=small

# Logging
LOG_LEVEL=INFO
JARVIS_ENV=production
```

---

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

## 17. Implementation Phases

### 17.1 Phase 1: Foundation (Week 1)

| Task | Description | Deliverable | Estimate |
|------|-------------|-------------|----------|
| 1.1 | Project scaffold | pyproject.toml, Dockerfile, docker-compose.yml | 2h |
| 1.2 | Configuration system | `src/jarvis/config.py` with pydantic-settings | 1h |
| 1.3 | Logging setup | `src/jarvis/logging.py` with structlog | 1h |
| 1.4 | Gateway server | `src/jarvis/gateway/server.py` with health endpoint | 2h |
| 1.5 | Request context | Correlation ID injection middleware | 1h |

**Exit Criteria**: `docker-compose up` starts healthy services, logs in JSON format.

### 17.2 Phase 2: Telegram Integration (Week 1-2)

| Task | Description | Deliverable | Estimate |
|------|-------------|-------------|----------|
| 2.1 | Webhook handler | `src/jarvis/telegram/bot.py` | 2h |
| 2.2 | Message parser | `src/jarvis/telegram/parser.py` | 2h |
| 2.3 | Security layer | `src/jarvis/telegram/security.py` (allowlist, rate limit) | 2h |
| 2.4 | Response formatter | `src/jarvis/telegram/formatter.py` | 1h |
| 2.5 | Command routing | `/help`, `/summarize` skeleton | 1h |

**Exit Criteria**: Bot responds to allowed users, ignores others, rate limits work.

### 17.3 Phase 3: Content Extraction (Week 2)

| Task | Description | Deliverable | Estimate |
|------|-------------|-------------|----------|
| 3.1 | Extractor base class | `src/jarvis/extractors/base.py` | 1h |
| 3.2 | X GraphQL extractor | `src/jarvis/extractors/x_graphql.py` | 4h |
| 3.3 | X Playwright fallback | `src/jarvis/extractors/x_playwright.py` | 3h |
| 3.4 | Substack extractor | `src/jarvis/extractors/substack.py` | 2h |
| 3.5 | Generic web extractor | `src/jarvis/extractors/web.py` (trafilatura) | 1h |
| 3.6 | Extractor tests | Unit tests with mocked responses | 2h |

**Exit Criteria**: Extract X threads, Substack articles, generic URLs successfully.

### 17.4 Phase 4: Core Logic (Week 2-3)

| Task | Description | Deliverable | Estimate |
|------|-------------|-------------|----------|
| 4.1 | OpenCode client | `src/jarvis/opencode/client.py` | 2h |
| 4.2 | Session management | `src/jarvis/opencode/session.py` | 2h |
| 4.3 | Summarizer | `src/jarvis/core/summarizer.py` | 2h |
| 4.4 | Chat passthrough | `src/jarvis/core/chat.py` | 2h |
| 4.5 | Storage manager | `src/jarvis/core/storage.py` | 2h |

**Exit Criteria**: Full `/summarize` flow works end-to-end.

### 17.5 Phase 5: Voice & Polish (Week 3)

| Task | Description | Deliverable | Estimate |
|------|-------------|-------------|----------|
| 5.1 | Whisper integration | `src/jarvis/voice/transcriber.py` | 3h |
| 5.2 | Voice message handling | Telegram voice -> Whisper -> process | 2h |
| 5.3 | Error handling polish | User-friendly error messages | 2h |
| 5.4 | Integration tests | End-to-end tests | 3h |
| 5.5 | Deployment guide | `docs/deployment.md` | 2h |

**Exit Criteria**: Voice messages work, deployment documented.

### 17.6 Phase 6: Infrastructure (Week 3-4)

| Task | Description | Deliverable | Estimate |
|------|-------------|-------------|----------|
| 6.1 | Syncthing configuration | Docker Compose, folder setup | 2h |
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

## 18. Success Metrics

### 18.1 MVP Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| URL summarization success rate | >90% | Successful extractions / Total attempts |
| Summarization latency (p95) | <30s | Log analysis |
| Voice transcription accuracy | >90% | Manual spot-check |
| Chat response latency (p95) | <15s | Log analysis |
| Unauthorized access attempts blocked | 100% | Security logs |
| Data sync reliability | 100% | Syncthing status |

### 18.2 User Satisfaction (Post-MVP)

| Question | Target |
|----------|--------|
| "Can I summarize my X bookmarks faster?" | Yes |
| "Is the bot responsive on mobile?" | Yes |
| "Do I trust the security model?" | Yes |
| "Can I find old summaries easily?" | Yes (grep, file search) |

---

## 19. Open Questions

### 19.1 Resolved

| Question | Resolution |
|----------|------------|
| Telegram or Discord? | Telegram (user preference) |
| Where to deploy? | Mac Mini with Tailscale |
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

## 20. Appendices

### 20.1 Appendix A: X GraphQL API Details

The X GraphQL API uses these key endpoints:

```
POST https://x.com/i/api/graphql/{query_id}/TweetDetail
POST https://x.com/i/api/graphql/{query_id}/TweetResultByRestId
```

Query IDs change periodically. The baoyu-skills approach:
1. Maintains known query IDs in `constants.ts`
2. Falls back to scraping if queries fail

Our Python port will:
1. Store query IDs in config
2. Implement auto-discovery if needed
3. Fall back to Playwright

### 20.2 Appendix B: Substack Extraction

Substack articles are standard HTML with consistent structure:
- Title: `<h1 class="post-title">`
- Author: `<a class="author-name">`
- Content: `<div class="body markup">`

trafilatura handles this well. Edge cases:
- Paywalled content: Returns partial or error
- Images: Extracted with alt text

### 20.3 Appendix C: Whisper Model Comparison

| Model | Size | VRAM | Speed (M4) | Accuracy |
|-------|------|------|------------|----------|
| tiny | 75MB | ~1GB | ~0.5s/s | 85% |
| base | 142MB | ~1GB | ~1s/s | 90% |
| small | 466MB | ~2GB | ~2s/s | 93% |
| medium | 1.5GB | ~5GB | ~5s/s | 95% |
| large | 3GB | ~10GB | ~10s/s | 97% |

Selected: **small** - Best balance for 60s audio limit.

### 20.4 Appendix D: References

1. [OpenCode Documentation](https://opencode.ai/docs)
2. [OpenCode Server API](https://opencode.ai/docs/server)
3. [baoyu-skills X extractor](https://github.com/JimLiu/baoyu-skills)
4. [trafilatura documentation](https://trafilatura.readthedocs.io/)
5. [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
6. [Syncthing documentation](https://docs.syncthing.net/)
7. [Tailscale Funnel](https://tailscale.com/kb/1223/funnel)

---

**Document History**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-31 | Jarvis Team | Initial PRD |

---

**Approval**

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Product Owner | | | |
| Tech Lead | | | |

---

Ready to proceed with implementation once approved. Do you want me to adjust any section or start building?