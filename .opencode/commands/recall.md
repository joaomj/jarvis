# Recall from Vault

Search Jarvis vault for bookmarks, saved URLs, attachments, and memories.

## Usage

```
/recall <query>
```

## Arguments

- `$ARGUMENTS` - Search query

## Behavior

1. Search across all vault content:
   - X bookmarks (auto-synced from database)
   - Saved URLs (`vault/url-saves/`)
   - Attachments (`vault/sources/attachments/`)
   - Curated memories (`vault/memories/`)
2. Use BM25 retrieval
3. Return results with citations
4. Indicate source type for each result

## Examples

- `/recall democracy`
- `/recall machine learning papers`
- `/recall tweets about AI`
- `/recall my preferences`

## Notes

- Searches all local content including X bookmarks
- Returns citations with source type indicator
