# Changelog

All notable changes to Jarvis will be documented in this file.

## [Unreleased]

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
