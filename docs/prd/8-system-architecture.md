
## 8. System Architecture

### 8.1 High-Level Architecture (Phase 1 - Simplified)

```
+---------------------------------------------------------------------------------+
|                                   INTERNET                                       |
|                                                                                  |
|    +--------------+                                    +--------------+         |
|    |   Telegram   |                                    |   OpenCode   |         |
|    |   Servers    |                                    |   Server API |         |
|    +------+-------+                                    +------+-------+         |
|           |                                                   |                  |
|           | HTTPS (webhook/long-polling)                      | HTTP (local)    |
|           v                                                   |                  |
+-----------------------------------+---------------|---------------+---------------+
|                              TAILSCALE MESH                   |                  |
|                                                               |                  |
|    +--------------------------------------------------------------------------+ |
|    |                         MAC MINI (M4, 16GB)                              | |
|    |                                                                          | |
|    |    +-------------------------------------------------------------+      | |
|    |    |                    DOCKER COMPOSE                            |      | |
|    |    |                                                                |      | |
|    |    |   +-------------------+        +-------------------------+    |      | |
|    |    |   |   Jarvis Bot      |------->|   OpenCode Server       |    |      | |
|    |    |   |   (Python)        |        |   opencode serve :4096  |    |      | |
|    |    |   |                   |        |                         |    |      |
|    |    |   |  Responsibilities:|        |  - Session management   |    |      |
|    |    |   |  - Telegram bot   |        |  - Command execution    |    |      |
|    |    |   |  - User allowlist |        |  - LLM provider calls   |    |      |
|    |    |   |  - HTTP client    |        |  - Tool execution       |    |      |
|    |    |   |  - Response fmt   |        |  - File operations      |    |      |
|    |    |   +-------------------+        +-------------------------+    |      | |
|    |    |                                                                |      | |
|    |    +-------------------------------------------------------------+      | |
|    |                                                                          | |
|    +--------------------------------------------------------------------------+ |
|                                                                                  |
+----------------------------------------------------------------------------------+

Key Design Decision: Jarvis is a THIN BRIDGE
- No Gateway abstraction
- No command interpretation
- No LLM provider management
- All intelligence lives in OpenCode Server
- Jarvis only: receive -> validate -> forward -> format -> respond
```

### 8.2 Component Diagram (Phase 1)

```
+-----------------------------------------------------------------------------+
|                              JARVIS BOT                                      |
|  Pure passthrough - no command interpretation, no business logic             |
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  |                        TELEGRAM INTERFACE                               | |
|  |                                                                         | |
|  |  +---------------+  +---------------+  +---------------+               | |
|  |  |  Telegram     |  |    User       |  |   Response    |               | |
|  |  |  Bot Handler  |  |   Allowlist   |  |   Formatter   |               | |
|  |  |  (python-     |  |   (silent     |  |   (chunking,  |               | |
|  |  |   telegram-   |  |   ignore)     |  |   markdown)   |               | |
|  |  |   bot)        |  |               |  |               |               | |
|  |  +---------------+  +---------------+  +---------------+               | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                    |                                         |
|                                    v                                         |
|  +------------------------------------------------------------------------+ |
|  |                      OPENCODE HTTP CLIENT                               | |
|  |                                                                         | |
|  |  +---------------+  +---------------+  +---------------+               | |
|  |  |   Session     |  |   Message     |  |   Command     |               | |
|  |  |   Manager     |  |   Sender      |  |   Executor    |               | |
|  |  |   (1 per user)|  |   (/message)  |  |   (/command)  |               | |
|  |  +---------------+  +---------------+  +---------------+               | |
|  |                                                                         | |
|  |  Responsibilities:                                                      | |
|  |  - Detect /command vs regular message                                   | |
|  |  - Route to appropriate OpenCode endpoint                               | |
|  |  - Parse OpenCode response                                              | |
|  |  - No command interpretation!                                           | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                    |                                         |
|                                    v                                         |
|  +------------------------------------------------------------------------+ |
|  |                      OPENCODE SERVER (External)                         | |
|  |                                                                         | |
|  |  All intelligence lives here:                                           | |
|  |  - Command parsing (/undo, /share, /compact, etc.)                     | |
|  |  - LLM provider management                                              | |
|  |  - Tool execution (bash, file ops, browser)                            | |
|  |  - Session persistence                                                  | |
|  |  - File reference resolution (@file)                                    | |
|  |  - Git operations for undo/redo                                         | |
|  |                                                                         | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
+------------------------------------------------------------------------------+
```

### 8.3 Sequence Diagram: Chat Passthrough (Phase 1)

```
+------+     +---------+     +---------+     +----------+
| User |     |Telegram |     | Jarvis  |     |OpenCode  |
|      |     |  Bot    |     |  Bot    |     | Server   |
+--+---+     +----+----+     +----+----+     +-----+----+
   |              |               |               |
   | "explain      |               |               |
   |  @main.py"    |               |               |
   |------------->|               |               |
   |              |               |               |
   |              | Forward       |               |
   |              | message       |               |
   |              |-------------->|               |
   |              |               |               |
   |              |               | Check         |
   |              |               | allowlist     |
   |              |               | (silent OK)   |
   |              |               |               |
   |              |               | POST          |
   |              |               | /session/:id  |
   |              |               | /message      |
   |              |               |-------------->|
   |              |               |               |
   |              |               |               | LLM process
   |              |               |               | (with @file
   |              |               |               |  resolution)
   |              |               |               |
   |              |               | Response      |
   |              |               | (parts[])     |
   |              |               |<--------------|
   |              |               |               |
   |              |               | Format for    |
   |              |               | Telegram      |
   |              |               | (chunk if     |
   |              |               |  needed)      |
   |              |               |               |
   |              | Send response |               |
   |              |<--------------|               |
   |              |               |               |
   |<-------------|               |               |
   | [Explanation|               |               |
   |  of main.py] |               |               |
   |              |               |               |
```

### 8.4 Sequence Diagram: Command Execution (Phase 1)

```
+------+     +---------+     +---------+     +----------+
| User |     |Telegram |     | Jarvis  |     |OpenCode  |
|      |     |  Bot    |     |  Bot    |     | Server   |
+--+---+     +----+----+     +----+----+     +-----+----+
   |              |               |               |
   | /undo        |               |               |
   |------------->|               |               |
   |              |               |               |
   |              | Forward       |               |
   |              | message       |               |
   |              |-------------->|               |
   |              |               |               |
   |              |               | Detects /     |
   |              |               | command       |
   |              |               | prefix        |
   |              |               |               |
   |              |               | POST          |
   |              |               | /session/:id  |
   |              |               | /command      |
   |              |               | {command:     |
   |              |               |  "undo"}      |
   |              |               |-------------->|
   |              |               |               |
   |              |               |               | Git revert
   |              |               |               | last commit
   |              |               |               |
   |              |               | Response      |
   |              |               | (undo OK)     |
   |              |               |<--------------|
   |              |               |               |
   |              | Send response |               |
   |              |<--------------|               |
   |              |               |               |
   |<-------------|               |               |
   | [Last change |               |               |
   |  reverted]   |               |               |
   |              |               |               |
```

### 8.5 Sequence Diagram: URL Summarization (Phase 2)

> To be completed in Phase 2. Simplified flow:
> 
> 1. User sends URL via Telegram
> 2. Jarvis extracts content (X GraphQL or trafilatura)
> 3. Jarvis saves original to data/articles/
> 4. Jarvis sends content to OpenCode for summarization
> 5. Jarvis saves summary to data/summaries/
> 6. Jarvis returns summary via Telegram
> 
> See Epic 1 (Section 5.1) for detailed user stories and acceptance criteria.

---
