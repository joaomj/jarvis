# Commands Reference

Complete reference for all Jarvis commands.

## Local Commands (Handled by Jarvis)

| Command | Description |
|---------|-------------|
| `/models` | Show and select favorite models |
| `/new [title]` | Create new session |
| `/sessions` | List your sessions |
| `/model <provider/model>` | Set model directly |
| `/save <url>` | Save a URL to the vault for later retrieval |

## OpenCode Commands

Commands forwarded to OpenCode Server:

| Command | Description |
|---------|-------------|
| `!models` | Same as `/models` |
| `!favmodels` | Same as `/models` |
| `!<cmd>` | Forward any OpenCode command (e.g., `!undo`, `!compact`, `!share`) |

## Command Discovery

Jarvis fetches available commands from OpenCode Server on startup and registers them
in Telegram's native command menu. Use the menu button in Telegram chat to see all commands.

## Jarvis Custom Commands

### `/save <url>`

Save a URL to the vault for later retrieval.

**Usage:**
```
/save https://example.com/article
```

**Behavior:**
1. Extract URL from arguments
2. Use Firecrawl to scrape content
3. Save markdown to `vault/raw/url-saves/`
4. Index into KB for retrieval
5. Confirm save with file path

**Examples:**
- `/save https://twitter.com/user/status/123`
- `/save https://example.com/article`

## Auto-Retrieval

Jarvis automatically retrieves relevant context on every message. No manual `/recall` needed.

**What gets searched:**
- KB content (bookmarks, saved URLs, attachments)
- OpenCode conversation history

**Retrieval method:**
- FTS5 (BM25 keyword search)
- sqlite-vec (semantic embeddings)
- RRF fusion ranking
- Results injected as system prefix into OpenCode prompt

## Natural Language Queries

Jarvis also responds to natural language without commands:

**X Bookmarks:**
- "What did I save last week?"
- "Show me my recent bookmarks"
- "What did I bookmark about AI?"

**Saved Content:**
- "Find that article about Rust async"
- "What do I have on vector databases?"

**Attachments:**
- "[attach file.txt] What does this say?"
