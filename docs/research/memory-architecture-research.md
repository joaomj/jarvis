# Memory Architecture Research

> Research findings and architectural recommendations for Jarvis memory system.
> Goal: ChatGPT-like memory + NotebookLM-like knowledge base integration.

## ChatGPT Memory Architecture (4 Layers)

| Layer | Persistence | Example |
|-------|-------------|---------|
| **Session Metadata** | Ephemeral | Device, timezone, subscription tier |
| **User Memory** | Long-term facts | "User's name is X", "Prefers Y" |
| **Recent Conversations** | Summaries | ~15 chat titles + snippets |
| **Current Session** | Sliding window | Full conversation context |

**Key insight**: No vector DB, no RAG over history. Just curated facts + summaries.

## NotebookLM Approach

- **Grounded RAG** - Only answers from uploaded documents
- Heavy embedding/vector search
- Document-centric, creates synthesized outputs

## Engram (Best Personal Memory Reference)

The most relevant reference for this use case:

| Feature | Implementation |
|---------|---------------|
| Storage | LibSQL/SQLite (single file) |
| Embeddings | BGE-M3 local (Transformers.js) |
| Vector Index | DiskANN built-in |
| Search | Hybrid (semantic + FTS5 + RRF) |
| Reranking | BGE-reranker cross-encoder (local) |
| Knowledge Graph | SQLite-embedded links |
| Forgetting | Ebbinghaus decay + sleep consolidation |
| Memory Types | reflex, episode, fact, preference, decision |
| **External APIs** | **None** |

## sqlite-vec

- SQLite extension for vector storage
- SIMD-accelerated (AVX, NEON)
- Zero external dependencies
- Perfect for personal-scale (100-10K entries)

## Assessment

| Concern | Verdict |
|---------|---------|
| **Semantic search needed** | Yes. Concepts need similarity matching |
| **Graph mechanisms** | Valuable. Enables "related to", "caused by" links |
| **Memories = KB** | Correct. Separate tables is artificial |
| **External daemon necessity** | No. sqlite-vec + local embeddings is better |

## Proposed Architecture: Unified Context System

### Unified Schema (Replace `memory_entries` + `kb_*`)

```sql
-- Single source of truth
CREATE TABLE context_entries (
    id INTEGER PRIMARY KEY,
    entry_type TEXT NOT NULL,  -- 'memory' | 'kb_doc' | 'url_save' | 'attachment'
    memory_type TEXT,           -- 'reflex' | 'fact' | 'preference' | 'episode' | 'decision'
    title TEXT,
    content TEXT NOT NULL,
    source_path TEXT,          -- markdown file path
    source_url TEXT,           -- original URL if any
    importance REAL DEFAULT 0.5,
    strength REAL DEFAULT 1.0, -- Ebbinghaus decay
    access_count INTEGER DEFAULT 0,
    created_at TEXT,
    last_accessed TEXT,
    is_permanent BOOLEAN DEFAULT 0
);

-- Vector embeddings (sqlite-vec)
CREATE VIRTUAL TABLE context_embeddings USING vec0(
    entry_id INTEGER,
    embedding FLOAT[1024]  -- or 384 for smaller model
);

-- Knowledge graph edges
CREATE TABLE context_links (
    source_id INTEGER,
    target_id INTEGER,
    relation TEXT,  -- 'related_to' | 'caused_by' | 'evolved_from' | 'contradicts' | 'supersedes'
    weight REAL DEFAULT 1.0,
    created_at TEXT
);

-- FTS5 for lexical (already have)
CREATE VIRTUAL TABLE context_fts USING fts5(content, title, source);
```

### Search Stack (Hybrid)

```
Query: "democracy risks"
         │
    ┌────┴────┐
    ▼         ▼
 Semantic    FTS5
(sqlite-vec)(BM25)
    │         │
    └────┬────┘
         ▼
   Reciprocal Rank Fusion (k=60)
         │
         ▼
   Graph Expansion (1-2 hops)
         │
         ▼
   Composite Score:
   relevance × importance × strength × recency
```

### Embeddings: Local, Zero API Cost

| Option | Model | Dimensions | Status |
|--------|-------|------------|--------|
| **sentence-transformers** (Python) | `all-MiniLM-L6-v2` | 384 | Recommended |
| **Transformers.js** (Node) | `BGE-M3` | 1024 | Cross-platform |
| **llama.cpp embedding** | Local GGUF | varies | If using LLM |

### Memory Lifecycle (From Engram)

```
┌─────────────────────────────────────────────────────────┐
│                    ADD MEMORY                           │
│  1. Compute embedding (local)                           │
│  2. Check for merge (cosine >= 0.92, same type)         │
│  3. Auto-link to top-3 similar (cosine >= 0.7)          │
│  4. Insert with strength=1.0, importance=0.5            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  RECALL (Query)                         │
│  1. FTS5 lexical search                                 │
│  2. Vector semantic search                              │
│  3. RRF fusion                                          │
│  4. Optional: graph-hop expansion                       │
│  5. Composite scoring                                   │
│  6. Return within token budget                          │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│               SLEEP CONSOLIDATION (Daily)               │
│  1. Decay: strength *= 0.95^days                        │
│  2. Prune: Archive if strength < 0.05 (not permanent)   │
│  3. Merge: Combine near-duplicates                      │
│  4. Boost: +10% strength for access_count >= 3          │
└─────────────────────────────────────────────────────────┘
```

## Trade-offs

| Aspect | External daemon retrieval | sqlite-vec (Proposed) |
|--------|--------------------------|----------------------|
| External services | Node.js daemon | None |
| Setup complexity | High (npm, embed) | Low (pip install) |
| Semantic search | Yes | Yes |
| Knowledge graph | No | Yes |
| Forgetting | No | Ebbinghaus |
| Memory types | No | 5 cognitive types |
| Single-user fit | Overkill | Perfect |
| Data locality | Separate process | Same SQLite file |

## References

- ChatGPT Memory: https://manthanguptaa.in/posts/chatgpt_memory/
- Engram: https://github.com/foramoment/engram-ai-memory
- sqlite-vec: https://github.com/asg017/sqlite-vec
