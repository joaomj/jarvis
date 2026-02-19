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

### Folder Queries

```bash
# List all folders
sqlite3 .jarvis/jarvis.db "SELECT folder_name FROM x_bookmark_folders ORDER BY folder_name;"

# Count bookmarks per folder
sqlite3 .jarvis/jarvis.db ".mode column" ".headers on" \
  "SELECT f.folder_name, COUNT(a.tweet_id) as count \
   FROM x_bookmark_folders f \
   LEFT JOIN x_bookmark_folder_assignments a ON f.folder_id = a.folder_id \
   GROUP BY f.folder_id ORDER BY count DESC;"

# Export bookmarks from specific folder
sqlite3 .jarvis/jarvis.db -csv -header \
  "SELECT b.text \
   FROM x_bookmarks b \
   JOIN x_bookmark_folder_assignments a ON b.tweet_id = a.tweet_id \
   JOIN x_bookmark_folders f ON a.folder_id = f.folder_id \
   WHERE f.folder_name = 'Context retrieval' \
   ORDER BY b.bookmarked_at DESC;" > context_retrieval.csv

# Export all bookmarks with their folders
sqlite3 .jarvis/jarvis.db -csv -header \
  "SELECT b.text, GROUP_CONCAT(f.folder_name, ', ') as folders \
   FROM x_bookmarks b \
   LEFT JOIN x_bookmark_folder_assignments a ON b.tweet_id = a.tweet_id \
   LEFT JOIN x_bookmark_folders f ON a.folder_id = f.folder_id \
   GROUP BY b.tweet_id \
   ORDER BY b.bookmarked_at DESC;" > bookmarks_with_folders.csv

# Find uncategorized bookmarks (not in any folder)
sqlite3 .jarvis/jarvis.db -csv -header \
  "SELECT b.text FROM x_bookmarks b \
   LEFT JOIN x_bookmark_folder_assignments a ON b.tweet_id = a.tweet_id \
   WHERE a.tweet_id IS NULL \
   ORDER BY b.bookmarked_at DESC;"
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

# Show folder tables schema
sqlite3 .jarvis/jarvis.db ".schema x_bookmark_folders"
sqlite3 .jarvis/jarvis.db ".schema x_bookmark_folder_assignments"
```

### Table Relationships

```
x_bookmarks (1) <---> (N) x_bookmark_folder_assignments (N) <---> (1) x_bookmark_folders
  - tweet_id (PK)         - tweet_id (FK)                          - folder_id (PK)
  - text                  - folder_id (FK)                         - folder_name
  - author_username
  - ...
```

- **One bookmark** can be in **many folders** (e.g., "Context retrieval" + uncategorized)
- **One folder** can contain **many bookmarks**
- Junction table enables many-to-many relationship

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