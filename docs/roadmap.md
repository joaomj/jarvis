# Roadmap

Alfred: a personal AI assistant (butler, consigliere) accessible via Telegram.

## Vision & Principles

- **Single continuous chat** - no thread management UI. All organization happens in the background.
- **Memory sovereignty** - memories, logs, and learnings stored locally in `vault/`, portable and syncable.
- **LLM independence** - models/providers swappable without losing assistant usefulness.
- **Self-improving** - the agent must passively learn from its user over time.
- **Skill-based** - extend capabilities via skills (plugins/tools/commands).
- **No full autonomy** - the agent does not have unrestricted OS/filesystem access. Allowlist-only.
- **Auto-context** - every message automatically retrieves relevant context from conversation history and memory.

## Use Cases (Priority Order)

### Daily Use
- Chat about topics (History, Economics, random questions)
- Personal counselling (Alfred persona — Christopher Nolan's trilogy)
- Private questions (not recorded)

### Research
- Detailed technical reports from trustworthy sources
- Research paper analysis
- PDF document discussion

### On Demand
- Summarize content
- Software engineering discussions

## Current Status

Alfred is a standalone PydanticAI agent with a Telegram interface. No external dependencies beyond the LLM provider.

**Implemented:**
- PydanticAI agent with skill-based architecture
- Skill loading (YAML frontmatter + Python scripts)
- Memory management (SOUL.md, MEMORY.md, USER.md)
- Conversation store (FTS5-backed message history)
- Telegram gateway (polling, command routing, streaming)
- Model switching via /model inline keyboard
- Structured JSON logging with correlation IDs
- Docker containerization
- 4 skills: core, deep-research, private, summarize

**Planned:**
- X bookmarks sync
- URL save and indexing (/save)
- Hybrid retrieval (FTS5 + semantic search)
- Passive learning / self-improvement
- Cloud sync strategy (Syncthing vs git-based)

## Implementation History

- **Phase 0-8**: Original OpenCode-bridge architecture (replaced)
- **Phase 9**: Decoupled from OpenCode, rewrote as standalone PydanticAI agent
- **Phase 10**: Skill-based architecture with memory management
- **Phase 11**: Jarvis → Alfred rename, OpenCode Go provider, model menu, structured logging
