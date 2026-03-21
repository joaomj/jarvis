# Roadmap

This document captures Jarvis' current state, the gaps versus the main objectives, and an incremental plan to reach:

- Memory sovereignty: memories, logs, and learnings are stored locally, portable, and syncable.
- LLM independence: models/providers can be swapped without losing the assistant's usefulness.

## Decisions (Current)

- Telegram stays as the UI layer for now.
- The memory vault lives in `vault/`.
- Ignore Google Drive integration for now.
- No special "chat only with this source" mode; Jarvis detects source-grounded questions and prioritizes retrieved sources.
- Source priority order (deep research and normal conversations): attached files > local files (`vault/`) > high reputation web sources > general web sources.
- Deep research (5-20 page reports) must be explicit/confirmed to control cost/latency.
- When a question benefits from web sources, Jarvis defaults to a "Sourced Answer" that includes high-reputation web sources (no extra confirmation).
- **Commands:** Jarvis uses OpenCode custom commands instead of building NLU layer in Jarvis.
- **PDF extraction:** LLM-based via OpenCode models, avoid traditional PDF parsers.
- **Retrieval:** BM25-first approach, add semantic search only if needed.

## Architecture Principles

These principles guide all implementation decisions:

1. **Thin bridge:** Jarvis stays minimal, delegates intelligence to OpenCode.
2. **Leverage OpenCode:** Use OpenCode's extensibility (custom commands, agents, skills) instead of reimplementing.
3. **Incremental retrieval:** Start simple (BM25), add complexity only when needed.
4. **Configuration over code:** Avoid hardcoding, use declarative configs.
5. **LLM for complex tasks:** Use vision models for PDF extraction instead of error-prone traditional parsers.

## Current Status (What Exists Today)

Jarvis is a local Telegram bot that bridges mobile chat to OpenCode Server and includes local-data features.

**Complete:**
- Telegram bridge to OpenCode
  - Polling mode, no webhook/public port requirement.
  - Forwards prompts and OpenCode commands, streams SSE events, supports interactive question/permission flows.
  - Maintains a pinned status message with session/model/agent/tokens/changed files.
- Local persistence (SQLite)
  - Stores session records, message/response logs, feedback votes, X bookmarks, and a knowledge-base index.
- X bookmarks
  - OAuth2 PKCE + token refresh.
  - Daily incremental sync + weekly full reconciliation.
  - Basic natural-language time-range queries (e.g. last week/month/today/recent).
- URL save + Knowledge Base (KB)
  - Detects save intent for URLs.
  - Delegates scraping to OpenCode (Firecrawl workflow) and writes markdown under `.jarvis/url-saves/`.
  - Indexes saved markdown into SQLite (FTS5), chunked deterministically.
  - Can answer "grounded" questions using retrieved chunks and requires citations.
- Memory (vault-first)
  - Curated memory storage with remember/forget/recall flows.
  - Private-turn persistence guard.
- Attachment ingestion
  - Telegram document ingestion for text attachments.
  - Attachments persisted under `vault/sources/attachments/` and indexed.
- Deep research orchestration
  - Staged deep research with local artifact workspace under `vault/research/<job-id>/`.
  - dr-gate classification + explicit confirmation flow.
  - Callback-driven Telegram UX for confirm/cancel.

**Key limitation:** PDF extraction not yet supported (high priority).

## Objective Fit (How Close We Are)

### Memory sovereignty

Already good:

- A meaningful amount of data is local (bookmarks, URL saves, memories, logs) and inspectable.
- SQLite + markdown files are portable and easy to back up.
- Vault (`vault/`) established as source of truth.

Not there yet:

- PDF content not yet indexed (in progress).
- Retrieval quality could improve (BM25 upgrade pending).

### LLM independence

Already good:

- OpenCode provides multi-provider model selection; Jarvis acts as a thin bridge.
- PDF extraction will use OpenCode's model selection (GPT-4V, Claude Vision, etc.)

Not there yet:

- Retrieval-grounded answering limited to KB intent path; most questions default to generic LLM answering.

## Target Architecture (Simple, Stable, Sovereign)

The core pattern is: files are the source of truth; databases are derived indexes.

### Source of truth: `vault/`

`vault/` is a plain directory tree that contains:

- Raw conversation logs (append-only; organized by date).
- Derived artifacts (session summaries, daily summaries).
- Curated memories (atomic facts/preferences/decisions) with explicit user control.
- Saved sources (articles, books, PDFs) plus extracted markdown/text.

The vault should be safe to sync with Syncthing and/or git (with secrets excluded). The system should tolerate the index being deleted and rebuilt from `vault/`.

### Derived index: SQLite + BM25

SQLite remains for storage; BM25 provides better lexical retrieval:

- BM25 for keyword search (Phase 7.1).
- Optional: sentence-transformers embeddings for semantic search (Phase 7.2).
- Optional: native hybrid retrieval tuning (Phase 7.3).

### Deterministic retrieval and prompt injection

To meet the requirement "prioritize retrieved sources over training data":

- Jarvis detects when the user wants a sourced/grounded answer (explicitly or implicitly).
- Jarvis retrieves evidence deterministically in this order: attached files > `vault/` > high-rep web > general web.
- Jarvis injects retrieved excerpts first and instructs the model to cite them.

If the user requires academic-style grounding, then factual claims must be backed by captured sources. If retrieval + web search are insufficient, Jarvis should say "insufficient evidence" rather than inventing citations.

## OpenCode Custom Commands

Jarvis leverages OpenCode's built-in command system for Jarvis-specific features instead of building NLU in Jarvis.

### Why Custom Commands?

- Keeps Jarvis as thin Telegram bridge (no NLU complexity)
- Leverages OpenCode's model-agnostic design
- Uses OpenCode's existing command infrastructure
- Avoids duplicating LLM logic

### Planned Commands

```
.opencode/commands/
├── ingest-pdf.md      # PDF extraction via LLM vision
├── recall.md          # Search vault memories
├── research.md        # Deep research with citations
├── save.md            # Save URL to vault
├── remember.md        # Store curated memory
├── forget.md          # Remove curated memory
└── help-jarvis.md     # List Jarvis commands
```

See [OpenCode Custom Commands Documentation](https://opencode.ai/docs/commands/) and [Opencode Native Commands](https://opencode.ai/docs/tui#commands) for implementation details.

### Command Discovery

Users discover Jarvis commands via:
- `/help-jarvis` - Lists all Jarvis-specific commands
- OpenCode's built-in command help system

## How Deep Research Works (Jarvis + OpenCode)

Deep research is implemented as: Jarvis is the deterministic orchestrator and archivist; OpenCode is the provider-agnostic LLM + tools runtime.

### Responsibilities

Jarvis:

- Decides whether to run deep research (explicit trigger or confirmation).
- Enforces source priority (attachments > `vault/` > high-rep web > general web).
- Creates a research job workspace under `vault/` and writes all artifacts there.
- Splits work into stages to manage context windows.
- Verifies output constraints (citations present, references section generated from used sources).

OpenCode:

- Executes LLM calls against whichever provider/model is configured.
- Runs tools (web search with citations, scraping/capture, etc.).
- Uses agents/subagents to parallelize work while keeping each step's context bounded.
- Streams progress/events back to Jarvis.

Telegram:

- UI transport only: message + attachments in, progress + report out.

### Effort Ladder (Cost Control)

- Quick Answer (default): attachments + local retrieval only; no web.
- Sourced Answer: attachments + local + high-rep web sources; citations required.
- Deep Research Report: explicit/confirmed; 5-20 pages; saves a job workspace and an evidence trail under `vault/`.

Deep Research triggers (natural language examples): "do a deep research", "write a literature review", "write a 10-page report", "academic-style report with citations".

### Research Job Workspace (Artifacts)

Each deep research run creates a folder under `vault/` (a durable artifact, not just chat text):

- `question.md` (task + constraints)
- `plan.md` (outline + subquestions)
- `sources/` (captured attachments and captured web pages)
- `notes/` (per-source notes/extractions)
- `evidence.json` (the evidence ledger)
- `report.md` (final report)

### Pipeline (Context-Window Safe)

1) Plan: outline + research questions.
2) Collect: ingest attachments and pull relevant items from `vault/`.
3) Expand: if needed, search high-rep web sources; capture/snapshot sources locally.
4) Extract: convert sources into small evidence units (snippets/quotes + anchors) written to `evidence.json`.
5) Draft: write each section using only the evidence units relevant to that section.
6) Integrate: consistency pass, missing-citation pass, and references generation.
7) Deliver: send `report.md` via Telegram; keep the full job workspace in `vault/`.

This design avoids putting all sources into a single context window. The long-horizon state lives in `vault/`, not in the model context.

## Retrieval Strategy (BM25-First)

### Phase 7.1: Upgrade to BM25 (Quick Win)

BM25 (https://pypi.org/project/BM25/) provides better keyword relevance than SQLite FTS:

- Pure Python (no new system dependencies)
- Simple API: `BM25.index()` + `BM25.search()`
- Better ranking algorithm than FTS5
- Easy migration from current FTS implementation

### Phase 7.2: Add Semantic Search (If Needed)

If BM25 alone shows consistent retrieval misses for semantic queries:

- Add sentence-transformers embeddings
- Hybrid retrieval: BM25 (lexical) + embeddings (semantic)
- Fallback: If embeddings are insufficient, tune native rank fusion and thresholds

### Phase 7.3: Improve Native Hybrid Search (If Still Needed)

If Phase 7.2 still shows retrieval gaps:

- Tune lexical/semantic rank fusion weights and thresholds
- Add optional lightweight reranking in Python stack
- Keep local-first, Python-first retrieval path

## PDF Extraction Strategy

### Why LLM-Based?

Traditional PDF parsers (PyMuPDF, pdfplumber) struggle with:
- Multi-column layouts
- Tables and figures
- Scanned documents (OCR needed)
- Complex formatting

LLM-based extraction (via OpenCode models) provides:
- 95%+ accuracy on complex layouts
- Table and structure understanding
- Consistent output format

### Implementation

**Phase 8.1:** Create `/ingest-pdf` custom command
- Uses OpenCode's model selection
- Accepts PDF attachment or path
- Extracts text, tables, structure
- Saves to `vault/sources/pdfs/`

**Phase 8.2:** Intelligent extraction pipeline
- Simple PDFs: Fast extraction
- Complex PDFs: LLM vision fallback
- Store extraction metadata (method, confidence)

**Phase 8.3:** PDF search & retrieval
- Index PDF content into vault/
- BM25 retrieval across PDF content
- Citation support with page numbers

## Next Steps (Incremental Plan With Acceptance Criteria)

### Phase 1-6: [COMPLETE] ✅

- Phase 1: Establish vault/ as source of truth
- Phase 2: Private mode (do not record)
- Phase 3: Curated memory (explicit remember/forget)
- Phase 4: Source-grounded answers by default when asked
- Phase 5: Attached files as first-class sources
- Phase 6: Deep research reports

### Phase 7: Improve Retrieval Quality

#### Phase 7.1: Upgrade to BM25

Acceptance criteria:

- BM25 package integrated (`pip install BM25`)
- Existing FTS queries migrated to BM25
- Benchmark shows improved relevance over FTS5
- Index rebuilds automatically from vault/

#### Phase 7.2: Add Semantic Search (If Needed)

Acceptance criteria:

- sentence-transformers embeddings integrated
- Hybrid retrieval (BM25 + embeddings) working
- Semantic queries return relevant results ("articles about distributed systems")
- Falls back gracefully when embeddings unavailable

#### Phase 7.3: Improve Native Hybrid Search (If Still Needed)

Acceptance criteria:

- Native hybrid search tuned for improved precision/recall
- Hybrid search (FTS + vectors + rank fusion tuning) working
- Performance acceptable for vault/ size

### Phase 8: PDF Ingestion via OpenCode Commands

#### Phase 8.1: Custom `/ingest-pdf` Command

Acceptance criteria:

- `.opencode/commands/ingest-pdf.md` created
- Command accepts PDF via attachment or path
- Extracts text using OpenCode vision model
- Saves extracted content to `vault/sources/pdfs/`
- Shows extraction status to user

#### Phase 8.2: Intelligent Extraction Pipeline

Acceptance criteria:

- Simple PDFs: Fast extraction (under 5 seconds)
- Complex PDFs: LLM vision fallback triggered automatically
- Extraction metadata stored (method, confidence, page count)
- 95%+ extraction accuracy on mixed layouts

#### Phase 8.3: PDF Search & Retrieval

Acceptance criteria:

- PDF content indexed into BMWhat does the Tocqueville PDF say25
- " about democracy?" returns relevant excerpts
- Citations include page numbers
- PDF content searchable alongside other vault/ content

### Phase 9: Jarvis-Specific OpenCode Commands

#### Phase 9.1: Core Jarvis Commands

Status: **Partially Complete** ✅ (2/7 commands implemented)

Commands created:
- ✅ `/save` - Save URL to vault (implemented with Firecrawl workflow)
- ✅ `/recall` - Search vault (searches all content: bookmarks, URLs, attachments, memories)
- ⏳ `/ingest-pdf` - PDF extraction (Phase 8.1)
- ⏳ `/research` - Deep research with citations (Phase 6)
- ⏳ `/remember` - Store curated memory (future)
- ⏳ `/forget` - Remove curated memory (future)
- ⏳ `/help-jarvis` - List Jarvis commands (using native `/help` instead)

**Note:** We removed natural language routing in favor of explicit commands. Commands use OpenCode's native infrastructure (`$ARGUMENTS`).

#### Phase 9.2: Command Discoverability

Acceptance criteria:

- `/help-jarvis` lists all Jarvis-specific features
- Commands have descriptions visible in OpenCode help
- User can discover features without reading docs

#### Phase 9.3: Argument Handling

Acceptance criteria:

- Commands accept user input via `$ARGUMENTS`
- Example: `/recall democracy in America` searches vault
- Commands work naturally without requiring slash syntax

### Phase 10: UX Improvements

#### Phase 10.1: Feedback Mechanism

Acceptance criteria:

- Thumbs up/down buttons on bot messages
- Feedback stored in SQLite (linked to message_id, session_id)
- Analytics view shows response quality by model/agent
- User can see which responses are helpful

#### Phase 10.2: Model/Agent Visibility

Acceptance criteria:

- Every response shows `provider/model-id` in footer
- Agent name shown when using specialized agents
- Pinned status message includes model info

### Phase 11: Environment & Dependency Management

#### Phase 11.1: Fix Hardcoded Paths

Acceptance criteria:

- `scripts/start-opencode.sh` uses environment variables
- No absolute local paths in scripts
- Configurable paths for all runtime directories

#### Phase 11.2: Docker Isolation Options

Acceptance criteria:

Docker Compose profiles:
- `jarvis-only` (current): `docker compose up jarvis`
- `full-stack`: `docker compose --profile full up` (OpenCode + Jarvis)

Clear documentation for each mode.

#### Phase 11.3: Dependency Isolation Strategies

Acceptance criteria:

Documentation for three approaches:
1. **Hybrid (recommended for dev):** Jarvis in Docker, OpenCode on host with venv
2. **Full Docker:** Both containerized (cleanest isolation)
3. **Venv-only:** Both on host with isolated Python environments

## Priority Order

### Immediate (Next 2-4 weeks)

1. **Phase 8.1** - PDF ingestion via `/ingest-pdf` command
2. **Phase 7.1** - BM25 upgrade (quick retrieval win)
3. **Phase 9.1-9.2** - Core Jarvis commands + discoverability

### Short-term (1-2 months)

4. **Phase 10.1** - Feedback mechanism
5. **Phase 8.2-8.3** - Intelligent PDF pipeline + search
6. **Phase 11.1-11.2** - Path fixes + Docker options

### Medium-term (if needed)

7. **Phase 7.2** - Semantic search (only if BM25 insufficient)
8. **Phase 10.2** - Model visibility
9. **Phase 7.3** - native hybrid tuning (only if needed)

## Risks and Tradeoffs

- Telegram is convenient but not sovereign: bot chats are stored on Telegram infrastructure. Vault sovereignty still holds because Jarvis keeps the durable memory local, but private conversations should be explicitly supported.
- "Agent decides to retrieve" is unreliable: we should avoid architectures that depend on the model correctly invoking a skill. Prefer deterministic routing + retrieval + prompt injection. ( *suggestion: we can still use skills, but clear rules/decision trees to AGENTS.md telling the agent when to invoke a skill; skills are a very convenient way to offload context from the agent context window, alowwing for easy 'lazy on-demand retrieval'.* )
- Over-indexing early is a trap: embeddings/reranking are useful, but FTS + good metadata often wins on simplicity and debuggability.

Additional deep research tradeoffs:

- Long reports must be staged to avoid context-window degradation; this increases orchestration complexity but improves stability and reduces cost.
- Web search improves coverage but reduces privacy; the source-priority policy minimizes unnecessary web use.
- External deep research engines can accelerate time-to-value but add operational weight and can conflict with the vault-first architecture.

## External References

- BM25 (Python): https://pypi.org/project/BM25/
- sqlite-vec (local vector search): https://github.com/asg017/sqlite-vec
- OpenCode Commands: https://opencode.ai/docs/commands/
- Vercel (filesystem + bash for agents): https://vercel.com/blog/how-to-build-agents-with-filesystems-and-bash
- Vercel (AGENTS.md index outperforms skills): https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals
- Turso (everything is a file; AgentFS concept): https://turso.tech/blog/nothing-new-under-the-sun
- Thalo (plain-text + validation loop for knowledge): https://thalo.rejot.dev/blog/plain-text-knowledge-management
- Plastic Labs (memory as reasoning; useful later for "learning"/distillation): https://blog.plasticlabs.ai/blog/Memory-as-Reasoning
- OpenCode agents/subagents: https://opencode.ai/docs/agents/
- OpenCode plugins: https://opencode.ai/docs/plugins/

Optional/inspiration:

- GPT-Researcher: https://github.com/assafelovic/gpt-researcher
- ThinkDepth.ai Deep Research: https://github.com/thinkdepthai/Deep_Research
- Onyx: https://github.com/onyx-dot-app/onyx
- DeepResearch Bench leaderboard: https://huggingface.co/spaces/muset-ai/DeepResearch-Bench-Leaderboard
