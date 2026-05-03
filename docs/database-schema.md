# Database Schema

SQLite database structure for Alfred conversation store.

## Core Table

### messages

Message history with FTS5 full-text search support.

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);

CREATE VIRTUAL TABLE messages_fts USING fts5(
    content,
    session_id UNINDEXED,
    role UNINDEXED,
    content='messages',
    content_rowid='id'
);
```

### FTS5 Triggers

```sql
CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
END;

CREATE TRIGGER messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
```

## Query Examples

### Recent Messages

```sql
SELECT id, role, substr(content, 1, 80) AS preview, created_at
FROM messages
WHERE session_id = 'session-uuid'
ORDER BY created_at DESC
LIMIT 20;
```

### Full-Text Search

```sql
SELECT m.id, m.role, substr(m.content, 1, 100) AS preview, m.created_at
FROM messages m
JOIN messages_fts fts ON fts.rowid = m.id
WHERE messages_fts MATCH 'search terms'
ORDER BY rank
LIMIT 10;
```

### Session List

```sql
SELECT session_id, COUNT(*) AS message_count,
       MIN(created_at) AS started_at, MAX(created_at) AS last_at
FROM messages
GROUP BY session_id
ORDER BY last_at DESC;
```
