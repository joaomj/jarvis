
## 1. Executive Summary

### 1.1 Vision

Jarvis is a personal AI assistant accessible via Telegram that provides a unified, continuous chat experience. Unlike traditional chatbots with fragmented thread-based UIs, Jarvis presents a single conversation stream where context management, memory organization, and tool selection happen transparently in the background.

### 1.2 Core Value Proposition

- **Single continuous chat**: No thread management, no chat history navigation
- **Mobile-first**: Full functionality via Telegram on iPhone
- **Privacy-respecting**: User owns all data (Syncthing-portable)
- **Provider-agnostic**: Switch LLM providers without lock-in
- **Security-constrained**: Limited write permissions, user allowlist

### 1.3 MVP Scope

The first release focuses on **replacing the OpenCode TUI with Telegram for mobile use**. The primary use case: accessing OpenCode AI assistance from an iPhone where the terminal interface is unusable due to screen size constraints.

**Phase 1 (MVP)**: Telegram as OpenCode Interface
- Send text messages to Telegram bot
- Messages forwarded directly to OpenCode Server API
- Responses returned via Telegram
- All OpenCode commands work (/undo, /share, /compact, etc.)
- Single persistent session per user

**Phase 2**: Enhanced Features  
- URL summarization (X threads, Substack articles)
- Voice message transcription
- Content archiving

The bot acts as a **pure passthrough** - no command translation, no custom logic. OpenCode handles all intelligence including command parsing, LLM calls, file operations, and session management.

---
