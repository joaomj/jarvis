# Save Content to Vault

Save a URL to the Jarvis vault for later retrieval.

## Usage

```
/save <url>
```

## Arguments

- `$ARGUMENTS` - URL to save (any URL including tweets, articles, blogs)

## Behavior

1. Extract URL from `$ARGUMENTS`
2. Use Firecrawl to scrape content
3. Save markdown to `vault/raw/url-saves/`
4. Index into KB for retrieval
5. Confirm save with file path

## Examples

- `/save https://twitter.com/user/status/123`
- `/save https://example.com/article`
- `/save https://blog.example.com/post`

## Notes

- Works with any URL (tweets, articles, newsletters)
- Content becomes automatically searchable via auto-retrieval
