# Changelog

All notable changes to Jarvis will be documented in this file.

## [Unreleased]

## [Added] - 2026-02-18 - X Bookmarks Folder Support

### Database Schema
- **New tables**: `x_bookmark_folders` and `x_bookmark_folder_assignments`
  - Junction table design supports many-to-many relationship (bookmark can be in multiple folders)
  - Foreign key constraints with CASCADE delete
  - Indexes on tweet_id and folder_id for fast lookups

### API Client Changes
- Added `get_bookmark_folders()` - fetch folder definitions (ID, name)
- Added `get_folder_bookmark_ids()` - fetch only tweet IDs from a folder (X API limitation)
- Added `get_all_folder_bookmark_ids()` - paginated folder ID fetching
- Note: X API folder endpoint only returns tweet IDs, not full bookmark data

### Sync Strategy Redesign
- **Step 1**: Fetch all bookmarks with full data (99 max per sync)
- **Step 2**: Fetch folder definitions
- **Step 3**: Fetch tweet IDs per folder, cross-reference with full data
- **Result**: Accurate folder assignments without duplicate API calls
- Full sync clears existing folder assignments before rebuilding

### Database Operations
- Added `save_folder()` - upsert folder definitions
- Added `assign_bookmark_to_folder()` - create junction records
- Added `clear_all_folder_assignments()` - for full re-sync
- Added `get_folders_for_bookmark()` - query folders for a bookmark

### New Models
- `BookmarkFolder` - folder_id, folder_name
- `BookmarkWithFolders` - extends Bookmark with folder_ids list

### Query Examples
```sql
-- Export bookmarks from specific folder
SELECT b.text FROM x_bookmarks b
JOIN x_bookmark_folder_assignments a ON b.tweet_id = a.tweet_id
JOIN x_bookmark_folders f ON a.folder_id = f.folder_id
WHERE f.folder_name = 'Context retrieval';

-- Export with folder names (CSV)
SELECT b.text, GROUP_CONCAT(f.folder_name, ', ') as folders
FROM x_bookmarks b
LEFT JOIN x_bookmark_folder_assignments a ON b.tweet_id = a.tweet_id
LEFT JOIN x_bookmark_folders f ON a.folder_id = f.folder_id
GROUP BY b.tweet_id;
```

### Migration Path
```bash
# Clear existing data and re-sync with folders
sqlite3 .jarvis/jarvis.db "DELETE FROM x_bookmark_folder_assignments; DELETE FROM x_bookmark_folders; DELETE FROM x_bookmarks; UPDATE x_sync_status SET first_sync_complete=0;"

# Run full sync
pdm run python -c "import asyncio; from jarvis.config import get_settings; from jarvis.database import Database; from jarvis.bookmarks.sync import BookmarkSync; s = get_settings(); db = Database(s.database_path); sync = BookmarkSync(db, s.x_client_id, s.x_client_secret); asyncio.run(sync.sync_bookmarks(full_sync=True))"
```

## [Changed] - 2026-02-16 - X Bookmarks OAuth 2.0 Migration

### Authentication Migration
- **BREAKING**: Replaced X API Bearer token with OAuth 2.0 PKCE user-context authentication
- Bearer token (`X_BEARER_TOKEN`) is now deprecated; use `X_CLIENT_ID` and `X_CLIENT_SECRET`
- OAuth 2.0 required because Bookmarks API endpoint needs user-context (app-only tokens return 403 Forbidden)
- Added `scripts/setup_x_oauth.py` for one-time OAuth 2.0 authorization flow
- Scopes requested: `bookmark.read`, `tweet.read`, `users.read`, `offline.access`

### Database Schema
- **New table**: `x_oauth_tokens` stores access token, refresh token, expiration, and scope
- Tokens persist in database (not .env) because they rotate frequently
- Auto-refresh tokens when expired (5-minute buffer before expiration)

### API Client Changes
- `XAPIClient` now requires `db`, `client_id`, `client_secret` (instead of `access_token`)
- Added `_get_user_id()` method to fetch authenticated user ID (API requires actual user ID, not "me")
- Added `_get_valid_access_token()` method with auto-refresh logic
- Endpoint changed from `/users/me/bookmarks` to `/users/{user_id}/bookmarks`
- Removed tweepy dependency; now uses httpx directly for simpler OAuth 2.0 handling

### Configuration
- Added `x_client_id` to Settings (OAuth 2.0 Client ID from Developer Console)
- Added `x_client_secret` to Settings (OAuth 2.0 Client Secret from Developer Console)
- `x_bearer_token` marked as deprecated but still present for backward compatibility

### Bot Integration
- Auto-sync now checks for OAuth tokens (`db.has_oauth_tokens()`) instead of bearer token
- Warning logged if OAuth tokens not found, prompting user to run setup script

### Testing
- Updated `TestXAPIClient` fixture to create mock database with stored OAuth tokens
- Updated `TestBookmarkSync` to use new constructor signature
- All 37 tests passing

### Setup Instructions
1. Create X app at https://developer.x.com
2. Set callback URL to `http://127.0.0.1:8080/callback`
3. Set type to "Web App, Automated App or Bot" (confidential client)
4. Copy Client ID and Client Secret to `.env` as `X_CLIENT_ID` and `X_CLIENT_SECRET`
5. Purchase API credits (Bookmarks endpoint is pay-per-use: $0.005/request)
6. Run `pdm run python scripts/setup_x_oauth.py` to authorize
7. First sync triggered automatically on first message of the day

### Known Limitations
- **bookmarked_at**: X API doesn't return bookmark timestamp; column shows sync time, not actual bookmark action time
- Use `id` order as proxy for bookmark recency (newer bookmarks have higher database IDs)
- **Cost**: Full sync of 100 bookmarks costs ~$0.50 ($0.005 per bookmark)

### Documentation
- Added `docs/x-bookmarks-queries.md` with SQLite query reference

## [Added] - c508752 - X Bookmarks Integration

### Database Schema
- `x_bookmarks` table stores tweet data (text, author, metrics, URLs, media, context annotations)
- `x_sync_status` table tracks sync metadata (last_sync_date, last_tweet_id, total_bookmarks)
- Indexes on `bookmarked_at` and `created_at` for fast time-range queries

### Bookmarks Module (`src/jarvis/bookmarks/`)
- **models.py**: Pydantic models (Bookmark, Author, Metrics, SyncStatus)
- **client.py**: X API client using tweepy with pagination support
- **sync.py**: Sync logic with auto-sync on first message of each day

### Authentication
- Uses X API Bearer token (read-only, from developer.twitter.com)
- Token stored in `.env` as `X_BEARER_TOKEN`
- No OAuth flow required (simpler setup, one-time configuration)

### Sync Strategy
- **Trigger**: Auto-sync on first Telegram message of each day
- **Mode**: Full sync on first run, incremental sync thereafter
- **Pagination**: Uses `since_id` to fetch only new bookmarks
- **Status tracking**: Tracks last sync date, tweet ID, and total count

### Query Interface
- Natural language via Telegram: "What did I save last week?"
- Keyword detection: saved, bookmarked, my tweets, my bookmarks, saved posts
- Time expressions: last week, yesterday, today, last month, past week, recent
- Results: Summaries with author, text preview, option for details
- Implementation: `query_bookmarks()` in `handlers/commands.py`

### Bot Integration
- Auto-sync on first message of each day
- Natural language query detection before sending to OpenCode
- Bookmark query handled locally, not forwarded to OpenCode

### Configuration
- Added `x_bearer_token` to Settings in `config.py`
- Updated `.env.example` with X_BEARER_TOKEN documentation

### Testing
- 11 new tests in `tests/test_bookmarks.py`
- Tests cover models, storage, client, and sync logic
- All 37 tests passing (including existing bot, formatter, opencode_client tests)

### Dependencies
- Added `tweepy>=4.16.0` (X API client)
- Added `cryptography>=46.0.5` (for future token encryption if needed)
- Added `apscheduler>=3.11.2` (scheduled sync, currently using on-message trigger)

## [Changed] - 73f0384 - Comprehensive Error Handling

### Error Handling Improvements
- Fixed 14 silent failure points where errors were not logged
- All errors now logged with context (user_id, session_id, operation)
- Added error handling for message audit logging, response logging, user state management

### Database Changes
- Responses table with 30-day auto-cleanup
- User state management for model selection flow

### Test Cleanup
- Removed 25 fake library tests that provided no value
- Retained 26 real tests with meaningful assertions

## [Changed] - 256f2f3 - Telegram Polling Implementation

### Architecture Migration
- Migrated from webhook to polling mode
- No public ports required, runs entirely locally
- No Tailscale needed for deployment
- Exponential backoff for resilience

### Polling Engine
- `src/jarvis/polling_engine.py` - Handles Telegram polling with backoff
- Configurable interval and timeout via environment variables
- Graceful shutdown handling

## [Changed] - fd64175 - Modular Architecture

### Command Router
- Central command routing in `src/jarvis/command_router.py`
- Categories: blocked, bridge-native, intercept, pass-through
- Simplifies adding new commands

### Handlers Package
- `src/jarvis/handlers/commands.py` - Modular command implementations
- Bridge-native commands: switch, agent, model
- Intercept commands: models, new, sessions

### Benefits
- Better testability
- Clearer separation of concerns
- Easier maintenance
- Each file under 300 lines (pre-commit enforced)

## [Fixed] - 0a5a7d8 - OpenCode Model Format

### Model API Format
- Fixed model parameter to be object: `{providerID: "opencode", modelID: "glm-5"}`
- Model and agent info extracted from response `info` object
- No separate API calls needed for model/agent metadata

## [Fixed] - efb701e - Security: Bot Token Exposure

### Logging Security
- Suppress httpx INFO logs that expose bot tokens
- All secrets filtered from structured logging

## [Added] - 4a02cd9 - Response Logging

### Database Schema
- `responses` table stores LLM responses
- Fields: session_id, user_id, model, response_text, timestamp
- 30-day auto-cleanup to prevent database bloat

## [Added] - d77ea33 - Model Selection

### Favorite Models
- `.jarvis/favorite_models.json` stores user's preferred models
- ModelsManager with auto-reload on file changes
- `/models` or `!models` command for interactive selection
- Per-user model preferences stored in SQLite

## [Changed] - 66094de - Configuration

### Environment Variables
- Added `OPENCODE_LOG_LEVEL` for server logging control
- Updated `.env.example` with new options

## [Changed] - 11bbffb - Documentation

### README Updates
- Model selection documentation
- Response logging features
- Comprehensive error handling strategy

## [Changed] - 2bcafb9 - Testing

### Test Updates
- Updated tests for OpenCode client API changes
- Fixed model format handling in tests

## [Added] - 31d4d6f - Default Models

### Model Defaults
- Set default models for initial use
- Favorite models can be customized

## [Added] - 256f2f3 - Telegram Bridge

### Initial Implementation
- Telegram bot using python-telegram-bot
- OpenCode Server integration
- Basic command forwarding
- Allowlist-based authorization

## [Documentation] - 762ef90 - AGENTS.md

### Skill Routing
- Added `AGENTS.md` for skill routing rules
- x-bookmarks skill with keyword patterns
- Natural language query examples
- Behavior guidelines for context-aware responses

## [Chore] - e631d3c - Gitignore

### Runtime Directories
- Added `.opencode/` to gitignore (local runtime directory)

## [Chore] - 270c5fd - Gitignore

### Temporary Files
- Added patterns for `*_PLAN.md` and `*_IMPLEMENTATION_PLAN.md`
- Ignore temporary planning files
