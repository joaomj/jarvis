# SQL Query Examples

Practical SQLite queries for inspecting Jarvis local data.

## Choose database file

```bash
# Default project-local DB
DB=.jarvis/jarvis.db

# Or resolve from app config
DB="$(pdm run python -c "from jarvis.config import get_settings; print(get_settings().database_path)")"
```

## Explore schema

```bash
sqlite3 "$DB" ".tables"
sqlite3 "$DB" ".schema x_bookmarks"
sqlite3 "$DB" ".schema x_sync_status"
sqlite3 "$DB" ".schema x_bookmark_folders"
sqlite3 "$DB" ".schema x_bookmark_folder_assignments"
```

## Sync health checks

```bash
sqlite3 "$DB" ".mode line" \
  "SELECT id, last_sync_date, last_sync_at, last_tweet_id, last_full_sync_date, \
          last_folders_sync_date, total_bookmarks, sync_in_progress \
   FROM x_sync_status WHERE id = 1;"

sqlite3 "$DB" "SELECT COUNT(DISTINCT tweet_id) AS bookmarks_in_db FROM x_bookmarks;"
```

## Bookmark queries

```bash
# Latest bookmarks
sqlite3 "$DB" ".mode column" ".headers on" \
  "SELECT author_username, substr(text, 1, 80) AS preview, created_at \
   FROM x_bookmarks ORDER BY created_at DESC LIMIT 20;"

# Search by keyword
sqlite3 "$DB" ".mode column" ".headers on" \
  "SELECT tweet_id, author_username, substr(text, 1, 100) AS preview \
   FROM x_bookmarks \
   WHERE text LIKE '%agent%' \
   ORDER BY created_at DESC LIMIT 50;"

# Top authors
sqlite3 "$DB" ".mode column" ".headers on" \
  "SELECT author_username, COUNT(*) AS total \
   FROM x_bookmarks \
   GROUP BY author_username \
   ORDER BY total DESC LIMIT 20;"
```

## Folder queries

```bash
# Folder list
sqlite3 "$DB" ".mode column" ".headers on" \
  "SELECT folder_id, folder_name FROM x_bookmark_folders ORDER BY folder_name;"

# Count per folder
sqlite3 "$DB" ".mode column" ".headers on" \
  "SELECT f.folder_name, COUNT(a.tweet_id) AS total \
   FROM x_bookmark_folders f \
   LEFT JOIN x_bookmark_folder_assignments a ON a.folder_id = f.folder_id \
   GROUP BY f.folder_id \
   ORDER BY total DESC;"

# Bookmarks from one folder
sqlite3 "$DB" ".mode column" ".headers on" \
  "SELECT b.author_username, substr(b.text, 1, 100) AS preview, b.tweet_url \
   FROM x_bookmarks b \
   JOIN x_bookmark_folder_assignments a ON a.tweet_id = b.tweet_id \
   JOIN x_bookmark_folders f ON f.folder_id = a.folder_id \
   WHERE f.folder_name = 'Context retrieval' \
   ORDER BY b.created_at DESC;"
```

## Other app data examples

```bash
# Recent Telegram interactions
sqlite3 "$DB" ".mode column" ".headers on" \
  "SELECT direction, substr(content, 1, 100) AS preview, timestamp \
   FROM messages ORDER BY id DESC LIMIT 30;"

# Recent OpenCode responses
sqlite3 "$DB" ".mode column" ".headers on" \
  "SELECT session_id, model, substr(content, 1, 100) AS preview, created_at \
   FROM responses ORDER BY id DESC LIMIT 30;"

# Session history
sqlite3 "$DB" ".mode column" ".headers on" \
  "SELECT telegram_user_id, opencode_session_id, session_title, date_key, created_at \
   FROM opencode_sessions ORDER BY id DESC LIMIT 30;"
```

## Export examples

```bash
# CSV export (bookmarks)
sqlite3 "$DB" -csv -header \
  "SELECT tweet_id, author_username, text, tweet_url, created_at \
   FROM x_bookmarks ORDER BY created_at DESC;" > bookmarks.csv

# JSON export (single folder)
sqlite3 "$DB" \
  "SELECT json_group_array(json_object( \
      'id', b.tweet_id, \
      'author', b.author_username, \
      'text', b.text, \
      'url', b.tweet_url, \
      'created_at', b.created_at \
   )) \
   FROM x_bookmarks b \
   JOIN x_bookmark_folder_assignments a ON a.tweet_id = b.tweet_id \
   JOIN x_bookmark_folders f ON f.folder_id = a.folder_id \
   WHERE f.folder_name = 'Context retrieval';" > folder-context-retrieval.json
```

## Safety

- Prefer `SELECT` queries for exploration.
- Back up `.jarvis/jarvis.db` before any `UPDATE`/`DELETE`/`VACUUM` operations.
