
## 12. API Specifications

### 12.1 Internal Message Format

All internal communication uses this envelope:

```python
@dataclass
class JarvisMessage:
    correlation_id: str
    timestamp: datetime
    source: Literal["telegram", "voice", "internal"]
    user_id: int
    
    # Parsed content
    command: str | None  # e.g., "summarize", "help", None for chat
    text: str
    url: str | None
    file_path: str | None
    
    # Flags
    private: bool = False
    
    # Metadata
    telegram_message_id: int | None = None
    voice_duration_seconds: float | None = None
```

### 12.2 OpenCode HTTP API Usage

**Key Principle**: Jarvis is a thin bridge. It does NOT interpret commands - it only routes them.

#### Endpoint Selection Logic

| User Input | Jarvis Action | OpenCode Endpoint |
|------------|---------------|-------------------|
| Starts with `/` (e.g., `/undo`, `/share`) | Extract command + args | `POST /session/{id}/command` |
| Regular text (incl. `@file`, `!cmd`) | Forward as-is | `POST /session/{id}/message` |

#### API Endpoints Used

```python
# Health check
GET /global/health
Response: {"healthy": true, "version": "1.2.3"}

# Create session (one per Telegram user)
POST /session
Body: {"title": "jarvis-user-{telegram_user_id}"}
Response: {"id": "ses-123", ...}

# Send regular message (most common)
POST /session/{id}/message
Body: {
    "parts": [{"type": "text", "text": "explain @src/config.py"}]
}
Response: {
    "info": {"id": "msg-456", "role": "assistant", ...},
    "parts": [{"type": "text", "text": "This config file..."}]
}

# Execute slash command
POST /session/{id}/command
Body: {
    "command": "undo",      # without the /
    "arguments": ""         # for commands with args
}
Response: {
    "info": {"id": "msg-789", ...},
    "parts": [{"type": "text", "text": "Reverted last changes"}]
}
```

#### Supported OpenCode Commands (Passthrough)

All these work transparently via Telegram:
- `/new`, `/clear` - New session
- `/undo`, `/redo` - Git-based revert/restore
- `/share`, `/unshare` - Session sharing
- `/compact` - Summarize session context
- `/sessions` - List sessions
- `/models` - List available models
- `/help` - Show help
- `/thinking` - Toggle thinking display
- Custom commands defined in OpenCode config

**Note**: OpenCode handles all @file references and !bash commands internally. Jarvis just passes the raw text.

**File Access Strategy**:
OpenCode Server runs with `working_dir: /projects`, mounting the host's `~/projects` directory. This allows:
- `@jarvis/src/config.py` resolves to `/projects/jarvis/src/config.py`
- Each project can have its own `AGENTS.md` for project-specific rules
- Git operations work naturally within project directories
- Session data stored separately in `/root/.opencode` (via `OPENCODE_HOME`)

#### Response Handling

```python
# Parse response parts
for part in response["parts"]:
    if part["type"] == "text":
        # Send to Telegram (chunk if >4096 chars)
        send_telegram_message(part["text"])
    elif part["type"] == "tool_result":
        # Include in context or display
        pass
```

### 12.3 X GraphQL API (Reverse-Engineered)

Based on baoyu-skills implementation:

```python
# Headers required
headers = {
    "Authorization": f"Bearer {BEARER_TOKEN}",  # Static app token
    "Cookie": f"auth_token={X_AUTH_TOKEN}; ct0={X_CT0}",
    "X-Csrf-Token": X_CT0,
    "Content-Type": "application/json",
}

# TweetDetail query
POST https://x.com/i/api/graphql/{query_id}/TweetDetail
Body: {
    "variables": {
        "focalTweetId": "1234567890",
        "with_rux_injections": false,
        ...
    },
    "features": {...}
}
```

---
