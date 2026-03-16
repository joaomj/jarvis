# Definitive Plan: Context System Alignment

Status: temporary implementation plan
Date: 2026-03-15
Owner: Jarvis repo workstream

## Objective

Align Jarvis around one context system for bookmarks, saved web content, and curated memories so that:

- X bookmarks are stored with their full available content, especially X Articles via `article.plain_text`
- Jarvis can query bookmark content by keywords, semantics, or both
- bookmarks, KB documents, and memories follow the same retrieval architecture
- all deep-research feature code and naming are removed from the codebase
- X auth works through long-lived OAuth refresh, without manual bearer-token generation

## Locked Decisions

1. Bookmarks become first-class context artifacts, not a side table used only for list views.
2. The retrieval solution must be the same family across bookmarks, KB, and memories.
3. Retrieval must support lexical search, semantic search, and hybrid ranking.
4. X OAuth 2.0 user-context with refresh token is the only supported bookmark auth path.
5. Deep research is removed completely, including residual `dr-*` naming in unrelated paths.

## Current Reality

### What works

- X OAuth PKCE setup exists in `scripts/setup_x_oauth.py`.
- token persistence and refresh flow already exist in `src/jarvis/bookmarks/client.py`.
- KB already has chunking and FTS search via `kb_chunks`, `kb_chunks_fts`, and `src/jarvis/kb_retrieval.py`.
- memories are already vault-backed artifacts in `vault/memories/` via `src/jarvis/memory_store.py`.

### What is broken or incomplete

- bookmark fetch requests are minimal and do not request `article`
- bookmark parsing ignores `article` and long-form content normalization
- bookmark storage has no canonical content fields for full-text retrieval
- bookmarks are not part of the indexed context corpus
- retrieval is lexical-only today; no semantic/hybrid layer exists
- deprecated bearer-token config still exists
- deep-research runtime code and `dr-*` names still exist

## Target Architecture

Jarvis should have one context architecture with source-specific ingestion and one shared retrieval plane.

### Source-of-truth model

- SQLite stores structured metadata and normalized searchable text pointers
- `vault/` stores human-inspectable source artifacts
- chunk index stores retrievable segments for all context sources
- embedding index stores semantic vectors for the same chunk set

### Shared context sources

- X bookmarks
- saved web content / KB markdown
- curated memories
- later: attachments, if already represented as indexed text artifacts

### Shared retrieval modes

- lexical: exact words, names, URLs, phrases, filters
- semantic: paraphrases, concept matches, fuzzy recall
- hybrid: weighted merge of lexical and semantic results

### Recommended canonical model

Every context artifact should be representable as:

- `source_type`: `bookmark`, `kb_document`, `memory`, `attachment`
- `source_id`: stable id per source
- `title`: optional
- `canonical_text`: full normalized text body
- `metadata`: source-specific attributes
- `artifact_path`: local markdown path when applicable

## Retrieval Strategy

### Definitive choice

Adopt one hybrid context pipeline for bookmarks + KB + memories.

### How it should work

1. Ingest each source into a local artifact plus normalized metadata.
2. Chunk the canonical text with the same chunking strategy used by the KB.
3. Index chunks into:
   - SQLite FTS for lexical matching
   - an embedding-backed vector index for semantic matching
4. At query time:
   - run lexical retrieval
   - run semantic retrieval
   - merge and rerank into one result set
   - return source-aware citations so Jarvis knows whether evidence came from a bookmark, KB doc, or memory

### Why this is the right choice

- one retrieval mental model across all saved context
- exact-match queries keep working well
- article-style bookmarks become searchable by meaning, not just literal words
- memories and bookmarks can participate in the same grounded answers

## X Bookmark Plan

## Phase 1 - Remove Deep Research Completely

### Scope

- remove runtime deep-research behavior from:
  - `src/jarvis/bot.py`
  - `src/jarvis/bot_updates.py`
  - `src/jarvis/bot_research.py`
  - `src/jarvis/deep_research.py`
- rename remaining `dr-*` agent references in unrelated logic such as:
  - `src/jarvis/bot_memory.py`
  - `src/jarvis/kb_web_fallback.py`
- remove or update deep-research docs and tests

### Gate

- repo grep shows no deep-research feature references and no `dr-*` names remain

## Phase 2 - Align X API Client With Real Responses

### API alignment

- switch bookmark/post base URL defaults to `https://api.x.com/2`
- request a rich bookmark field set including at minimum:
  - `article`
  - `note_tweet`
  - `text`
  - `entities`
  - `attachments`
  - `public_metrics`
  - `author_id`
  - `created_at`
  - useful author fields via `user.fields`
- preserve folder support as a second pass, since folder endpoints return ids only

### Normalization rules

Canonical bookmark content precedence:

1. `article.plain_text`
2. `note_tweet.text`
3. `text`

Also extract and normalize:

- `content_kind`: `article`, `note_tweet`, `post`, `link_only`, `media_only`, `unknown`
- `content_title`: from `article.title` when present
- `content_preview`: from `article.preview_text` when present
- `canonical_text`: full searchable text
- `source_unwound_url`: best resolved external/article url
- `tweet_url`
- `author_username`, `author_name`, `author_verified`
- metrics, timestamps, folders

### Gate

- live fetch of known long-form bookmark returns populated normalized article content locally

## Phase 3 - Upgrade Bookmark Schema and Storage

### Schema changes

Extend `x_bookmarks` with normalized content columns:

- `content_kind TEXT`
- `content_title TEXT`
- `content_preview TEXT`
- `content_text TEXT`
- `source_unwound_url TEXT`
- optional `artifact_path TEXT`
- optional `content_hash TEXT`

Keep existing `raw_json` unchanged as immutable API evidence.

### Storage design

- continue storing structured bookmark metadata in SQLite
- create one local artifact per bookmark under a dedicated vault path, for example:
  - `vault/sources/x-bookmarks/<tweet_id>.md`
- render the artifact with frontmatter and full canonical content

Artifact frontmatter should include:

- `source_type: bookmark`
- `tweet_id`
- `content_kind`
- `author_username`
- `author_name`
- `tweet_url`
- `source_unwound_url`
- `created_at`
- `bookmarked_at`
- `folder_ids`
- engagement metrics

### Gate

- saving one article bookmark yields:
  - normalized DB row
  - local markdown artifact
  - raw JSON retained intact

## Phase 4 - Unify Bookmarks With the Existing Context System

### Strategy

Treat bookmark artifacts exactly like KB and memory artifacts from the indexing perspective.

### Required changes

- extend the indexer to include bookmark artifacts
- bring memory artifacts into the same chunk search surface if they are not already indexed
- ensure bookmark artifacts are chunked with the same chunking logic as KB documents
- preserve source metadata so retrieval can filter or rank by source type

### Result

The context system becomes:

- `vault/memories/...`
- `vault/sources/web/...`
- `vault/sources/x-bookmarks/...`
- one shared chunk and vector retrieval plane

### Gate

- one query can return evidence from bookmarks, KB docs, and memories in a single ranked set

## Phase 5 - Add Semantic Search to the Whole Context System

### Requirement

Use the same semantic solution for bookmarks, KB, and memories.

### Implementation direction

- add chunk embeddings for all indexed context artifacts
- maintain a vector index keyed by chunk id and source metadata
- preserve SQLite FTS as the lexical baseline
- build a hybrid retriever that merges:
  - lexical FTS candidates
  - semantic nearest-neighbor candidates

### Ranking policy

- explicit keyword queries favor lexical relevance
- conceptual queries favor semantic relevance
- hybrid answers use merged scoring with source diversity caps

### Source-aware filters

Support ranking or filters for:

- source type
- recency
- author
- folder
- content kind

### Gate

- exact phrase queries hit lexical matches
- paraphrase queries hit semantic matches
- hybrid ranking returns a better blended set than either method alone

## Phase 6 - Remove Manual Bearer Token Workflow

### Definitive auth model

- keep one-time PKCE setup via `scripts/setup_x_oauth.py`
- store refresh token in SQLite
- refresh access token automatically in app code
- persist rotated refresh tokens when X returns them

### Cleanup

- remove deprecated `X_BEARER_TOKEN` references from:
  - `src/jarvis/config.py`
  - `.env.example`
  - docs
- add a small auth health-check command or script that reports:
  - token present/missing
  - token expiry window
  - refresh success/failure
  - reauth required/not required

### User experience goal

After initial authorization, bookmark sync should run without any manual bearer-token generation.

### Gate

- expired access token refreshes automatically and sync still succeeds without manual intervention

## Phase 7 - Repair Sync Correctness

### Issues to fix

- `x_sync_status` drift from actual bookmark row count
- stale `last_sync_at`
- reconcile behavior around full sync and incremental sync

### Required changes

- make sync status updates happen as one coherent end-of-sync write
- ensure `last_sync_date`, `last_sync_at`, `last_tweet_id`, and `total_bookmarks` are always consistent
- keep full-sync prune behavior, but verify it against artifact/index updates

### Gate

- after sync, status metadata matches actual DB counts and timestamps

## Phase 8 - Backfill and Reindex Existing Data

### Backfill steps

1. migrate schema
2. reparse existing `raw_json` rows where possible
3. run a full bookmark resync with rich fields
4. write bookmark markdown artifacts
5. rebuild chunk and vector indexes

### Validation reports

Produce counts for:

- total bookmarks
- bookmarks by `content_kind`
- bookmarks with empty `content_text`
- bookmarks with `article.title`
- bookmarks with `article.plain_text`
- bookmarks that still only contain wrapper text

### Gate

- most article bookmarks now have full canonical content stored locally and indexed

## Phase 9 - Testing and Verification

### Tests to add or update

- parser tests for:
  - article bookmarks
  - note-tweet bookmarks
  - regular post bookmarks
  - link-wrapper bookmarks
- DB tests for new normalized fields and artifact paths
- sync tests for:
  - incremental sync
  - full reconcile
  - folder assignment integrity
  - sync status correctness
  - token refresh success path
  - revoked refresh-token recovery path
- retrieval tests for:
  - exact keyword search
  - semantic search
  - hybrid search
  - mixed-source results across bookmarks, KB, and memories

### End-state verification queries

- exact term present only in one bookmark article body
- semantic paraphrase of one saved memory
- mixed query spanning bookmark article + web KB doc + memory

## Non-Goals

- no support for deprecated app-only bearer-token auth
- no separate bookmark-only retrieval stack if it diverges from the shared context system
- no assumption that all bookmarks are articles
- no hidden reliance on raw JSON parsing at query time

## Tradeoffs

### Recommended approach

Use one shared hybrid context system for all saved knowledge sources.

Pros:

- one mental model
- one retrieval stack
- bookmark articles become first-class evidence
- easier grounded responses across source types

Cons:

- larger migration
- embedding index adds complexity and storage
- backfill and reindex take real time

### Rejected alternative

Build a bookmark-only search subsystem and keep KB/memory separate.

Reasons rejected:

- duplicates retrieval logic
- weakens the value of a unified context system
- makes cross-source answers harder

## Execution Order

1. remove deep research and residual naming
2. align X client fields and parsing
3. migrate bookmark schema and artifact generation
4. unify bookmark artifacts with existing context indexing
5. add semantic + hybrid retrieval across all context sources
6. remove deprecated bearer-token config and harden OAuth refresh
7. backfill, full resync, and reindex
8. run verification suite and real query checks

## Definition of Done

- no deep-research code or `dr-*` naming remains
- X article bookmarks store full `article.plain_text` when available
- non-article bookmarks still ingest and index correctly
- bookmarks, KB docs, and memories share one retrieval architecture
- Jarvis can query saved context by keyword, semantics, or hybrid ranking
- X OAuth works without manual bearer-token generation after one-time setup
- sync metadata matches reality
