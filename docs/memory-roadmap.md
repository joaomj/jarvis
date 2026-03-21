# Memory System Roadmap: Unified Context Architecture

> Research findings and architectural recommendations for Jarvis memory system.
> Goal: ChatGPT-like memory + NotebookLM-like knowledge base integration.

## Research Summary

### ChatGPT Memory Architecture (4 Layers)

| Layer | Persistence | Example |
|-------|-------------|---------|
| **Session Metadata** | Ephemeral | Device, timezone, subscription tier |
| **User Memory** | Long-term facts | "User's name is X", "Prefers Y" |
| **Recent Conversations** | Summaries | ~15 chat titles + snippets |
| **Current Session** | Sliding window | Full conversation context |

**Key insight**: No vector DB, no RAG over history. Just curated facts + summaries.

### NotebookLM Approach

- **Grounded RAG** - Only answers from uploaded documents
- Heavy embedding/vector search
- Document-centric, creates synthesized outputs

### Engram (Best Personal Memory Reference)

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

### sqlite-vec

- SQLite extension for vector storage
- SIMD-accelerated (AVX, NEON)
- Zero external dependencies
- Perfect for personal-scale (100-10K entries)

---

## Assessment of Current Concerns

| Concern | Verdict |
|---------|---------|
| **Semantic search needed** | ✅ Yes. Concepts need similarity matching |
| **Graph mechanisms** | ✅ Valuable. Enables "related to", "caused by" links |
| **Memories = KB** | ✅ Correct. Separate tables is artificial |
| **External daemon necessity** | ❌ No. sqlite-vec + local embeddings is better |

---

## Recommended Architecture: Unified Context System

### 1. Unified Schema (Replace `memory_entries` + `kb_*`)

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

### 2. Search Stack (Hybrid)

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

### 3. Embeddings: Local, Zero API Cost

| Option | Model | Dimensions | Status |
|--------|-------|------------|--------|
| **sentence-transformers** (Python) | `all-MiniLM-L6-v2` | 384 | ✅ Recommended |
| **Transformers.js** (Node) | `BGE-M3` | 1024 | Cross-platform |
| **llama.cpp embedding** | Local GGUF | varies | If using LLM |

### 4. Memory Lifecycle (From Engram)

```
┌─────────────────────────────────────────────────────────┐
│                    ADD MEMORY                           │
│  1. Compute embedding (local)                           │
│  2. Check for merge (cosine ≥ 0.92, same type)         │
│  3. Auto-link to top-3 similar (cosine ≥ 0.7)          │
│  4. Insert with strength=1.0, importance=0.5            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  RECALL (Query)                         │
│  1. FTS5 lexical search                                 │
│  2. Vector semantic search                              │
│  3. RRF fusion                                          │
│  4. Optional: graph-hop expansion                      │
│  5. Composite scoring                                   │
│  6. Return within token budget                          │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│               SLEEP CONSOLIDATION (Daily)              │
│  1. Decay: strength *= 0.95^days                       │
│  2. Prune: Archive if strength < 0.05 (not permanent)  │
│  3. Merge: Combine near-duplicates                     │
│  4. Boost: +10% strength for access_count ≥ 3         │
└─────────────────────────────────────────────────────────┘
```

### 5. ChatGPT + NotebookLM Fusion

| Feature | From ChatGPT | From NotebookLM |
|---------|--------------|-----------------|
| Memory/KB separation | ❌ Merge into one | ✅ Single corpus |
| Source grounding | ✅ Citations | ✅ Document attribution |
| Summaries | ✅ Chat summaries | ✅ Auto-generated |
| Semantic search | ❌ (uses simple facts) | ✅ Vector search |
| Forgetting | ❌ Manual only | ❌ |
| Graph links | ❌ | ❌ |

**Your system adds:**
- Semantic search (from Engram)
- Knowledge graph (from Engram/Memonto)
- Ebbinghaus forgetting (from Engram)
- Memory types (from Engram)

---

## Implementation Phases

### Phase 1: Foundation (Native Hybrid + Unify Schema)

1. Remove legacy external retrieval client and handlers from runtime/config
2. Add `sqlite-vec` extension
3. Migrate `memory_entries` → `context_entries`
4. Migrate `kb_chunks` → `context_entries` (flatten)
5. Add `context_embeddings` virtual table

### Phase 2: Semantic Search

1. Add embedding generation (sentence-transformers)
2. Implement hybrid search (FTS5 + vector + RRF)
3. Update `/recall` to use hybrid search

### Phase 3: Knowledge Graph

1. Add `context_links` table
2. Implement auto-linking on add
3. Implement graph-hop expansion in recall

### Phase 4: Memory Lifecycle

1. Add Ebbinghaus decay
2. Add sleep consolidation command
3. Add importance scoring

---

## Trade-offs

| Aspect | External daemon retrieval | sqlite-vec (Proposed) |
|--------|---------------|----------------------|
| External services | Node.js daemon | None |
| Setup complexity | High (npm, embed) | Low (pip install) |
| Semantic search | ✅ Yes | ✅ Yes |
| Knowledge graph | ❌ No | ✅ Yes |
| Forgetting | ❌ No | ✅ Ebbinghaus |
| Memory types | ❌ No | ✅ 5 cognitive types |
| Single-user fit | Overkill | Perfect |
| Data locality | Separate process | Same SQLite file |

---

## Open Questions

### 1. Embedding Model Preference

| Model | Dimensions | Quality | Speed | Notes |
|-------|------------|---------|-------|-------|
| `all-MiniLM-L6-v2` | 384 | Good | Fast | Python native, recommended |
| `BGE-M3` | 1024 | Excellent | Slower | Multilingual, via Transformers.js |

**Recommendation**: Start with `all-MiniLM-L6-v2` for simplicity.

### 2. Graph Depth

1-hop or 2-hop expansion during recall?
- **1-hop**: Faster, focused context
- **2-hop**: Broader context, more latency

**Recommendation**: Start with 1-hop, measure performance.

### 3. Forgetting Aggressiveness

Ebbinghaus rate of 0.95/day means ~60% retention after 1 week.

| Rate | Retention after 1 week | Use case |
|------|------------------------|----------|
| 0.95 | 60% | Aggressive cleanup |
| 0.97 | 75% | Moderate |
| 0.99 | 90% | Conservative |

**Recommendation**: 0.97 for balanced retention.

### 4. Migration Strategy

- **Full replacement**: Remove external daemon retrieval, implement native system
- **Parallel run**: Both systems coexist during transition

**Recommendation**: Full replacement. External daemon retrieval adds complexity without benefit for single-user scenario.

---

## References

### ChatGPT Memory Architecture
- Reverse engineering: https://manthanguptaa.in/posts/chatgpt_memory/
- Key insight: 4-layer architecture, no RAG over history

### Engram (Cognitive Memory System)
- GitHub: https://github.com/foramoment/engram-ai-memory
- Key features: Ebbinghaus forgetting, hybrid search, knowledge graph, zero API cost

### sqlite-vec
- GitHub: https://github.com/asg017/sqlite-vec
- Key features: SQLite extension for vectors, SIMD-accelerated, zero dependencies

### NotebookLM
- Grounded RAG approach, document-centric synthesis
- Heavy use of embeddings for retrieval

### Related Projects
- Mem0: Managed memory layer with LLM extraction
- RECA: Lightweight memory and retrieval system
- Memonto: Knowledge graph-based long-term memory
