# X Bookmarks Database Queries

Quick reference for querying the local bookmarks database.

## Database Location

```bash
# Default location (relative to project root)
.jarvis/jarvis.db

# Or check config
pdm run python -c "from jarvis.config import get_settings; print(get_settings().database_path)"
```

## Common Queries

### Recent Bookmarks

```bash
# Last 10 bookmarks
sqlite3 .jarvis/jarvis.db ".mode column" ".headers on" \
  "SELECT author_username, substr(text, 1, 60) as preview, created_at \
   FROM x_bookmarks ORDER BY id DESC LIMIT 10;"
```

### Statistics

```bash
# Total count
sqlite3 .jarvis/jarvis.db "SELECT COUNT(*) as total FROM x_bookmarks;"

# Sync status
sqlite3 .jarvis/jarvis.db ".mode line" "SELECT * FROM x_sync_status;"

# Token status (expiration only, not actual tokens)
sqlite3 .jarvis/jarvis.db \
  "SELECT scope, expires_at, updated_at FROM x_oauth_tokens;"
```

### Search

```bash
# By keyword in text
sqlite3 .jarvis/jarvis.db ".mode column" ".headers on" \
  "SELECT author_username, text FROM x_bookmarks \
   WHERE text LIKE '%AI%' LIMIT 20;"

# By author
sqlite3 .jarvis/jarvis.db ".mode column" ".headers on" \
  "SELECT text, created_at FROM x_bookmarks \
   WHERE author_username = 'hwchase17' ORDER BY created_at DESC;"

# By date range (tweet creation date)
sqlite3 .jarvis/jarvis.db ".mode column" ".headers on" \
  "SELECT author_username, substr(text, 1, 50) FROM x_bookmarks \
   WHERE created_at >= '2026-02-01' AND created_at < '2026-03-01';"
```

### Metrics

```bash
# Most liked bookmarks
sqlite3 .jarvis/jarvis.db ".mode column" ".headers on" \
  "SELECT author_username, like_count, substr(text, 1, 40) \
   FROM x_bookmarks ORDER BY like_count DESC LIMIT 10;"

# Most bookmarked (by others)
sqlite3 .jarvis/jarvis.db ".mode column" ".headers on" \
  "SELECT author_username, bookmark_count, substr(text, 1, 40) \
   FROM x_bookmarks ORDER BY bookmark_count DESC LIMIT 10;"
```

### Export

```bash
# Export to CSV
sqlite3 .jarvis/jarvis.db \
  ".mode csv" ".headers on" \
  ".output bookmarks.csv" \
  "SELECT tweet_id, author_username, text, tweet_url, created_at FROM x_bookmarks;" \
  ".output stdout"

# Export specific author to JSON
sqlite3 .jarvis/jarvis.db \
  "SELECT json_group_array(json_object('id', tweet_id, 'text', text, 'url', tweet_url)) \
   FROM x_bookmarks WHERE author_username = 'hwchase17';" > author_bookmarks.json
```

### URLs

```bash
# Get tweet URLs for opening in browser
sqlite3 .jarvis/jarvis.db \
  "SELECT tweet_url FROM x_bookmarks ORDER BY id DESC LIMIT 5;"

# Open most recent in browser (macOS)
sqlite3 .jarvis/jarvis.db \
  "SELECT tweet_url FROM x_bookmarks ORDER BY id DESC LIMIT 1;" | xargs open
```

## Schema Reference

```bash
# Show all tables
sqlite3 .jarvis/jarvis.db ".tables"

# Show bookmarks table schema
sqlite3 .jarvis/jarvis.db ".schema x_bookmarks"

# Show sync status schema
sqlite3 .jarvis/jarvis.db ".schema x_sync_status"

# Show OAuth tokens schema
sqlite3 .jarvis/jarvis.db ".schema x_oauth_tokens"
```

## Known Limitations

### `bookmarked_at` Timestamp

The X API Bookmarks endpoint does not return when a tweet was bookmarked. The `bookmarked_at` column in the database reflects the **sync time**, not the actual bookmark action time.

Workarounds:
- Use `id` column order as proxy for bookmark order (newer bookmarks have higher IDs in the database)
- Use `created_at` for tweet creation time

### Cost

X API charges ~$0.005 per bookmark fetched. A full sync of 100 bookmarks costs approximately $0.50.

```bash
# Estimate next sync cost
sqlite3 .jarvis/jarvis.db \
  "SELECT COUNT(*) * 0.005 as estimated_cost_usd FROM x_bookmarks;"
```