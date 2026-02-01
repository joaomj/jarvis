
## 5. User Stories and Use Cases

### 5.0 Epic 0: Telegram-OpenCode Bridge (MVP - Phase 1)

#### US-0.1: Chat via Telegram
```
AS A user
I WANT TO send text messages to Telegram and receive OpenCode responses
SO THAT I can use OpenCode AI from my iPhone without the TUI
```

**Acceptance Criteria**:
- [ ] Telegram bot receives text messages from allowed user only
- [ ] Messages starting with `/` are sent to `POST /session/:id/command`
- [ ] Regular messages are sent to `POST /session/:id/message`
- [ ] OpenCode responses returned via Telegram
- [ ] Responses >4096 chars are chunked at natural boundaries
- [ ] Session persists across messages (continuous context)
- [ ] All OpenCode commands work: /undo, /redo, /share, /compact, /new, /sessions

**Message Routing**:
```
User: /undo
Bot: [Sends to POST /session/:id/command with {"command": "undo"}]
Bot: [Returns OpenCode response]

User: explain @src/config.py
Bot: [Sends to POST /session/:id/message with {"parts": [{"type": "text", "text": "explain @src/config.py"}]}]
Bot: [Returns OpenCode response with file analysis]

User: !ls -la
Bot: [Sends to POST /session/:id/message with {"parts": [{"type": "text", "text": "!ls -la"}]}]
Bot: [Returns bash output from OpenCode]
```

#### US-0.2: Session Management via Commands
```
AS A user
I WANT TO use OpenCode session commands from Telegram
SO THAT I can manage conversations without the TUI
```

**Acceptance Criteria**:
- [ ] `/new` or `/clear` creates new OpenCode session
- [ ] `/sessions` lists available sessions
- [ ] `/undo` reverts last message and file changes
- [ ] `/redo` restores undone message
- [ ] `/share` generates shareable session link
- [ ] `/compact` summarizes session context

### 5.1 Epic 1: URL Summarization (Phase 2)

#### US-1.1: Summarize X Thread
```
AS A user
I WANT TO send an X thread URL to Telegram
SO THAT I can get a summary without reading the full thread
```

**Acceptance Criteria**:
- [ ] Accepts URLs: `x.com/*/status/*`, `twitter.com/*/status/*`
- [ ] Extracts full thread (all posts in conversation)
- [ ] Saves original content as `data/articles/x-{date}-{slug}.md`
- [ ] Returns summary via Telegram (<4096 chars)
- [ ] Includes author, date, tweet count in response
- [ ] Completes in <30 seconds

**Flow**:
```
User: /summarize https://x.com/karpathy/status/1234567890
Bot: Fetching thread...
Bot: [Summary]
     Author: @karpathy
     Thread: 12 tweets
     Saved to: x-2026-01-31-karpathy-on-ai.md
```

#### US-1.2: Summarize Substack Article
```
AS A user
I WANT TO send a Substack URL to Telegram
SO THAT I can get the key points without reading 20 minutes
```

**Acceptance Criteria**:
- [ ] Accepts URLs: `*.substack.com/*`
- [ ] Extracts article title, author, content
- [ ] Saves original as `data/articles/substack-{date}-{slug}.md`
- [ ] Returns summary with key takeaways
- [ ] Handles paywalled content gracefully (error message)

#### US-1.3: Summarize Generic URL
```
AS A user
I WANT TO send any article URL
SO THAT I can get a quick summary of blog posts, news, etc.
```

**Acceptance Criteria**:
- [ ] Falls back to trafilatura extraction
- [ ] Handles most news sites, blogs, documentation
- [ ] Saves original content with source metadata

### 5.2 Epic 2: Voice Interaction (MVP)

#### US-2.1: Voice Message Transcription
```
AS A user
I WANT TO send voice messages to the bot
SO THAT I can interact hands-free
```

**Acceptance Criteria**:
- [ ] Accepts Telegram voice messages (OGG format)
- [ ] Transcribes using local Whisper (small model)
- [ ] Processes transcribed text as regular message
- [ ] Responds with text only (no audio)
- [ ] Max voice duration: 60 seconds
- [ ] Transcription completes in <10 seconds

### 5.3 Epic 3: General Chat (MVP)

#### US-3.1: Chat Passthrough
```
AS A user
I WANT TO chat with the AI about any topic
SO THAT I can get answers without switching tools
```

**Acceptance Criteria**:
- [ ] Messages without commands forwarded to OpenCode
- [ ] OpenCode session persists across messages
- [ ] Responses formatted for Telegram markdown
- [ ] Long responses split at natural boundaries

### 5.4 Epic 4: Security (MVP)

#### US-4.1: User Allowlist
```
AS the system owner
I WANT TO restrict access to my Telegram user ID
SO THAT no one else can interact with my assistant
```

**Acceptance Criteria**:
- [ ] `TELEGRAM_ALLOWED_USERS` env var (comma-separated IDs)
- [ ] Unauthorized users receive no response (silent ignore)
- [ ] All unauthorized attempts logged with user info

---
