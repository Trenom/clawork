# Clawork Architecture

Complete technical architecture documentation for Clawork, including system design, data flow, and design decisions.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Data Flow](#data-flow)
4. [Ticket Lifecycle](#ticket-lifecycle)
5. [Session Management](#session-management)
6. [Routing Engine](#routing-engine)
7. [Channel Integration](#channel-integration)
8. [Filesystem Layout](#filesystem-layout)
9. [Design Decisions](#design-decisions)

---

## System Overview

```
┌────────────────────────────────────────────────────────────┐
│                   Cowork Project: Clawork                   │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  HEARTBEAT (Scheduled Task)                          │  │
│  │  Triggers every 15 minutes (configurable)            │  │
│  │  • Reads config.yaml                                 │  │
│  │  • Checks all enabled channels for new messages     │  │
│  │  • Creates tickets from new messages                 │  │
│  │  • Invokes router skill                              │  │
│  └──────────────────────────────────────────────────────┘  │
│           │                                                │
│           ▼                                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ROUTER (clawork-router skill)                       │  │
│  │  Dispatcher that reads tickets and applies rules     │  │
│  │  Decision tree:                                      │  │
│  │  • Native channel? → Use Cowork connector           │  │
│  │  • Browser channel? → Use Computer Use skill        │  │
│  │  • Match routing rule? → Route to specialized skill │  │
│  │  • No match? → Use default skill (usually soul)     │  │
│  └──────────────────────────────────────────────────────┘  │
│           │                                                │
│           ├─────────────────┬──────────────────┬────────┤  │
│           │                 │                  │        │  │
│           ▼                 ▼                  ▼        ▼  │
│     ┌──────────┐      ┌──────────┐     ┌─────────┐ ┌────┐ │
│     │  SOUL    │      │MESSENGER │     │ Custom  │ │...  │ │
│     │Skill    │      │ Skill    │     │ Skills  │ │    │ │
│     └──────────┘      └──────────┘     └─────────┘ └────┘ │
│           │                 │                               │
│           │                 ├─ WhatsApp Web               │
│           │                 ├─ Telegram Web               │
│           │                 └─ Other apps                  │
│           │                                                │
│           ▼                                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  SESSIONS (clawork-sessions skill)                   │  │
│  │  Manages conversation history for context            │  │
│  │  • Read: Get conversation context for a peer        │  │
│  │  • Write: Append new interaction to history         │  │
│  │  • Compact: Summarize old messages, keep recent    │  │
│  └──────────────────────────────────────────────────────┘  │
│           │                                                │
│           ▼                                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  FILESYSTEM (message bus & persistence)              │  │
│  │  ~/claw/inbox/     ← Pending tickets                 │  │
│  │  ~/claw/outbox/    ← Completed tickets               │  │
│  │  ~/claw/sessions/  ← Conversation history            │  │
│  │  ~/claw/config.yaml ← Configuration                  │  │
│  │  ~/claw/soul.md    ← Agent personality               │  │
│  │  ~/claw/logs/      ← Activity logs                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

**Key insight:** The filesystem acts as the message bus. All communication between components flows through JSON files in the inbox/outbox directories.

---

## Component Architecture

### 1. Heartbeat (Scheduled Task)

**What it is**: A scheduled task in Cowork that runs at configurable intervals.

**Responsibilities**:
- Read `config.yaml` to determine enabled channels
- Check each enabled channel for new messages
- Create ticket JSON files in `~/claw/inbox/` for new messages
- Invoke the router skill to process pending tickets
- Log heartbeat execution to `~/claw/logs/heartbeat.jsonl`

**Pseudo-code**:
```
function heartbeat():
  1. Load config.yaml
  2. For each channel with enabled=true:
     a. Invoke appropriate message reading mechanism
     b. For each new message:
        i. Create ticket JSON with message data
        ii. Write to ~/claw/inbox/{ticket_id}.json
        iii. Set status="pending"
  3. Invoke router skill with path to inbox
  4. Log results to heartbeat log
  5. If errors: create error ticket for user notification
```

**Interval options**: 5m, 15m (default), 30m, 1h

### 2. Router (clawork-router skill)

**What it is**: The intelligent dispatcher that reads tickets and decides where to send them.

**Responsibilities**:
- Read all pending tickets from `~/claw/inbox/`
- For each ticket:
  1. Consult `config.yaml` routing rules
  2. Determine target skill based on rules
  3. Load context (previous messages, attachments, etc.)
  4. Invoke the target skill
  5. Update ticket status based on skill result
  6. Move ticket to appropriate directory (outbox or error)

**Routing Logic**:
```
routing_rules = config.yaml.routing.rules
target_skill = null

for rule in routing_rules:
  if rule.match.channel matches ticket.source.channel (or "*"):
    if not rule.match.peer OR rule.match.peer matches ticket.source.peer_id:
      if not rule.match.content_contains OR ticket.instruction contains rule.match.content_contains:
        target_skill = rule.action.skill
        break  # First matching rule wins

if target_skill is null:
  target_skill = config.yaml.routing.default.skill

return target_skill
```

**Ticket Processing**:
```
for ticket in pending_tickets (sorted by priority, then by created time):
  1. Update ticket.status = "processing"
  2. Determine target_skill via routing logic above
  3. Set ticket.routing.target_skill = target_skill
  4. Load conversation context via clawork-sessions
  5. Invoke target_skill with ticket as input
  6. Wait for skill to complete
  7. If skill completed successfully:
     a. Update ticket.status = "done"
     b. Move ticket to ~/claw/outbox/
  8. Else if skill failed:
     a. Update ticket.status = "error"
     b. Increment ticket.retry_count
     c. If retry_count >= 3: mark as permanent error
     d. Leave ticket in inbox for next heartbeat to retry
  9. Write log entry to ~/claw/logs/router.jsonl
```

### 3. Soul (clawork-soul skill)

**What it is**: The agent's personality and response generator.

**Responsibilities**:
- Load agent personality from `~/claw/soul.md`
- Load conversation history for the peer via clawork-sessions
- Process the ticket instruction
- Generate an appropriate response
- Handle errors gracefully
- Send response back to the origin channel
- Append interaction to conversation history

**Personality Loading**:
```
soul_file = config.yaml.agent.soul  (default: ~/claw/soul.md)
if file exists:
  soul_prompt = read(soul_file)
else:
  soul_prompt = DEFAULT_PERSONALITY

if ticket.routing has context_file:
  additional_context = read(context_file)
else:
  additional_context = ""
```

**Response Generation**:
```
1. Load soul prompt
2. Get conversation history for peer via clawork-sessions
3. Build context:
   a. Include soul prompt
   b. Include last N messages of conversation history
   c. Include any attached context files
   d. Include ticket metadata
4. Invoke Claude with full context + ticket instruction
5. Stream response
6. Write response to ticket.result.output
7. Mark ticket.status = "success"
```

**Response Sending**:
```
Based on ticket.source.channel:
  "whatsapp" → Invoke clawork-messenger with action="send"
  "telegram" → Invoke clawork-messenger with action="send"
  "slack" → Use Slack connector to send reply
  "gmail" → Use Gmail connector to send reply
  "dispatch" → Return response to Dispatch
  "filesystem" → Write to outbox directory
```

### 4. Sessions (clawork-sessions skill)

**What it is**: Persistent conversation history manager.

**Responsibilities**:
- Read conversation history for a given peer and channel
- Append new interactions to history
- Summarize and compact old sessions
- Archive old sessions

**Data Structure** (JSONL format):
```
~/claw/sessions/{channel}/{peer_id}.jsonl

Each line is a JSON object:
{
  "ts": "2026-04-05T10:30:00-03:00",
  "role": "user|assistant|system",
  "content": "The message text",
  "channel": "whatsapp",
  "peer": "+1555000100",
  "ticket_id": "ticket_001"
}
```

**Read Operation**:
```
function get_context(channel, peer_id, num_lines=50):
  filepath = ~/claw/sessions/{channel}/{peer_id}.jsonl

  if not exists(filepath):
    return []  # New conversation

  lines = read_last_n_lines(filepath, num_lines)

  # If first line is [SUMMARY], always include it
  if lines[0].role == "system" and "[SUMMARY]" in lines[0].content:
    # Keep first line, return it with the rest
    return lines
  else:
    # Return the last N lines as-is
    return lines
```

**Write Operation**:
```
function append_interaction(channel, peer_id, user_message, assistant_response):
  filepath = ~/claw/sessions/{channel}/{peer_id}.jsonl

  # Create file if doesn't exist
  if not exists(filepath):
    mkdir -p ~/claw/sessions/{channel}/
    create(filepath)

  # Append user message
  append_line(filepath, {
    "ts": now_iso8601(),
    "role": "user",
    "content": user_message,
    "channel": channel,
    "peer": peer_id
  })

  # Append assistant response
  append_line(filepath, {
    "ts": now_iso8601(),
    "role": "assistant",
    "content": assistant_response,
    "channel": channel,
    "peer": peer_id
  })

  # Check if compaction needed
  line_count = count_lines(filepath)
  if line_count >= config.limits.session_compact_threshold:
    compact_session(filepath)
```

**Compaction Logic**:
```
function compact_session(filepath):
  lines = read_all_lines(filepath)
  preserve_count = config.limits.session_context_lines

  # Last N lines are preserved as-is
  preserve_lines = lines[-preserve_count:]

  # Earlier lines are summarized
  old_lines = lines[:-preserve_count]

  # Create summary
  summary = create_summary(old_lines)

  # Build new file
  summary_line = {
    "ts": now_iso8601(),
    "role": "system",
    "content": "[SUMMARY] " + summary,
    "channel": extract_channel_from_lines(old_lines),
    "peer": extract_peer_from_lines(old_lines)
  }

  new_content = [summary_line] + preserve_lines

  # Backup original
  backup_path = ~/claw/sessions/.archive/{peer_id}_{timestamp}.jsonl.bak
  copy(filepath, backup_path)

  # Write compacted file
  write_jsonl(filepath, new_content)
```

### 5. Messenger (clawork-messenger skill) — Phase 2

**What it is**: Browser automation for WhatsApp Web and Telegram Web.

**Responsibilities**:
- Open and maintain Chrome tabs with WhatsApp Web and Telegram Web
- Read new messages from both platforms
- Extract message metadata (sender, timestamp, attachments)
- Create tickets from messages
- Send responses to the correct chat
- Handle rate limiting and bot detection

**WhatsApp Web Flow**:
```
1. Verify Chrome is open with web.whatsapp.com
2. Find chats with unread badges (green dot)
3. For each chat with unread messages:
   a. Click to open chat
   b. Scroll to find new messages (bottom of chat)
   c. Extract: sender, timestamp, text, attachments
   d. Create ticket in ~/claw/inbox/
4. Wait before processing next message (anti-bot delay)
```

**Telegram Web Flow**:
```
1. Verify Chrome is open with web.telegram.org/k/
2. Find chats with unread count badge
3. For each chat:
   a. Click to open chat
   b. Scroll to latest messages
   c. Extract message data
   d. Create ticket
4. Handle Telegram's different UI structure
```

**Sending Messages**:
```
function send_message(channel, peer_id, message_text):

  if channel == "whatsapp":
    1. Open web.whatsapp.com
    2. Use search to find peer by number or name
    3. Click on peer to open chat
    4. Find message input field
    5. Click input field
    6. Type message (with rate limiting)
    7. Press Send button or Enter key
    8. Verify message sent (look for send checkmark)
    9. Update ticket.result.reply_sent = true

  elif channel == "telegram":
    1. Open web.telegram.org/k/
    2. Search for peer
    3. Open chat
    4. Type in input field
    5. Send (Ctrl+Enter or click button)
    6. Verify
```

---

## Data Flow

### Complete Message Flow: WhatsApp → Response

```
Time: T=0
User sends WhatsApp message: "Hello, I need help"

Time: T=5min (next heartbeat)
  1. Heartbeat task runs
  2. Checks config.yaml, finds whatsapp.enabled=true
  3. Invokes clawork-messenger to read WhatsApp Web
  4. Messenger opens web.whatsapp.com, finds new message
  5. Creates ticket JSON:
     {
       "id": "ticket_20260405_001",
       "status": "pending",
       "source": {
         "channel": "whatsapp",
         "peer_id": "+1555000100"
       },
       "instruction": "Hello, I need help"
     }
  6. Writes to ~/claw/inbox/ticket_20260405_001.json
  7. Invokes router skill

Time: T=5min+1sec
  8. Router reads inbox
  9. Finds ticket, consults config.yaml routing rules
  10. No specific rule matches → uses default
  11. Default skill: "clawork-soul"
  12. Loads soul.md (agent personality)
  13. Calls clawork-sessions to get conversation history
      - Reads ~/claw/sessions/whatsapp/+1555000100.jsonl
      - Returns last 50 lines as context
  14. Calls Claude with:
       - System: soul.md + conversation context
       - User: ticket.instruction
  15. Claude generates response
  16. Appends both user message and response to session
  17. Updates ticket.result.output
  18. Updates ticket.status = "done"
  19. Invokes clawork-messenger to send response
  20. Messenger sends message via WhatsApp Web
  21. Moves ticket to ~/claw/outbox/

Time: T=5min+3sec
  22. User sees response on WhatsApp

User sees the full interaction took ~5 minutes from message to response (next heartbeat cycle).
```

---

## Ticket Lifecycle

```
Created (by heartbeat)
  │
  ▼
pending ──────────────┐
  │                  │
  │ (Router processes)
  │                  │
  ▼                  │
processing           │
  │                  │
  ├─ Skill succeeds  │
  │  ▼               │
  │  done ──────────┐│
  │                ││
  ├─ Skill fails    ││
  │  ▼              ││
  │  error          ││
  │  (retry_count < 3)
  │  ▼              ││
  │  pending ───────┘│ (wait for next heartbeat)
  │  (retry)         │
  │                  │
  ├─ Skill needs    ││
  │  input           │
  │  ▼              ││
  │  waiting_input   │
  │  (wait for user) │
  │                  │
  ▼                  │
Reply sent to user ◄─┘
(via channel)
```

**Status transitions**:
- `pending` → `processing` (when router picks up ticket)
- `processing` → `done` (skill completed successfully)
- `processing` → `error` (skill failed, retry_count < 3)
- `processing` → `error` (permanent, retry_count >= 3)
- `processing` → `waiting_input` (skill needs external data)
- `error`/`waiting_input` → `pending` (when retried)
- `done` → `archived` (after 24h via cleanup action)

---

## Session Management

### Directory Structure

```
~/claw/sessions/
├── whatsapp/
│   ├── +1555000100.jsonl          ← Alice Johnson's chat history
│   ├── +1555000200.jsonl          ← Bob Smith's chat history
│   └── group_family.jsonl         ← Family group chat history
│
├── telegram/
│   ├── user_123456.jsonl          ← Direct message user
│   └── group_dev-team.jsonl       ← Group chat
│
├── slack/
│   ├── channel_general.jsonl
│   ├── channel_projects.jsonl
│   └── dm_alice@company.com.jsonl
│
├── gmail/
│   ├── user@example.com.jsonl
│   └── auto-responses.jsonl
│
└── .archive/
    ├── +1555000100_2026-03-15.jsonl.bak
    └── [old backups from compaction]
```

### Conversation Summary Format

When a session is compacted, old messages are summarized. The summary includes:

```
[SUMMARY] Conversation with Alice Johnson (+1555000100) since 2026-03-01.
Main topics: order queries (especially order #12345),
shipping status updates. Alice is a frequent customer, prefers quick responses.
Last action: requested status update on order placement.
Tone: informal, direct.
```

This summary is stored as the first line of the compacted file with `role: "system"`.

---

## Routing Engine

### Rule Matching Algorithm

**Input**: ticket object, routing rules from config.yaml

**Output**: target skill name

```
function determine_target_skill(ticket, config):

  rules = config.routing.rules  # Already in priority order

  for rule in rules:
    # Check channel match
    if rule.match.channel != "*":
      if ticket.source.channel != rule.match.channel:
        continue  # This rule doesn't apply

    # Check peer match (if specified)
    if rule.match has "peer":
      if ticket.source.peer_id != rule.match.peer:
        continue  # This rule doesn't apply

    # Check group match (if specified)
    if rule.match has "group":
      if ticket.source.group != rule.match.group:
        continue  # This rule doesn't apply

    # Check content match (if specified)
    if rule.match has "content_contains":
      search_text = rule.match.content_contains
      if search_text not in ticket.instruction.lower():
        continue  # This rule doesn't apply

    # All conditions matched! Apply this rule
    return rule.action.skill

  # No rule matched, use default
  return config.routing.default.skill
```

### Example Routing Scenarios

**Scenario 1: Peer-based routing**
```yaml
routing:
  rules:
    - match:
        channel: "whatsapp"
        peer: "+1555000100"
      action:
        skill: "clawork-soul"
        priority: "high"
```
Messages from Alice (+1555...) go directly to soul with high priority.

**Scenario 2: Content-based routing**
```yaml
routing:
  rules:
    - match:
        channel: "*"
        content_contains: "order"
      action:
        skill: "crm-skill"
        priority: "normal"
```
Any message mentioning "order" (regardless of channel) goes to crm-skill.

**Scenario 3: Multi-condition routing**
```yaml
routing:
  rules:
    - match:
        channel: "telegram"
        group: "dev-team"
        content_contains: "deploy"
      action:
        skill: "deploy-agent"
```
Messages in the Telegram "dev-team" group containing "deploy" go to deploy-agent.

---

## Channel Integration

### Native Connectors (Slack, Gmail)

These use Cowork's official connectors. No custom code needed.

**Slack**:
- Messages flow through Cowork's Slack connector
- Replies are sent via the same connector
- Real-time delivery (on-event check_interval)

**Gmail**:
- Read emails from specified labels
- Reply via Gmail API
- Polling interval (default 15m)

### Browser Channels (WhatsApp, Telegram)

These use Computer Use to control Chrome.

**Control flow**:
1. Heartbeat task invokes clawork-messenger skill
2. Messenger uses Computer Use to control Chrome
3. Takes screenshots to analyze current state
4. Clicks UI elements to navigate chats
5. Extracts message text
6. Creates tickets
7. Later, sends responses via same mechanism

**Key limitations**:
- Dependent on Chrome UI remaining stable
- Rate limiting required (3-5 second delays)
- Session must stay open (don't close WhatsApp Web tab)
- Requires human to scan QR code initially

---

## Filesystem Layout

### Directory Tree

```
~/claw/
├── inbox/                          ← Incoming tickets
│   ├── ticket_20260405_001.json
│   ├── ticket_20260405_002.json
│   └── [...]
│
├── outbox/                         ← Completed tickets
│   ├── ticket_20260405_001.json
│   ├── ticket_20260405_002.json
│   └── archive/                    ← Tickets older than 24h
│       └── ticket_20260404_*.json
│
├── sessions/                       ← Conversation history
│   ├── whatsapp/
│   │   ├── +1555000100.jsonl
│   │   └── [...]
│   ├── telegram/
│   ├── slack/
│   ├── gmail/
│   └── .archive/                   ← Backups from compaction
│
├── logs/                           ← Activity logs
│   ├── heartbeat.jsonl
│   ├── router.jsonl
│   ├── soul.jsonl
│   └── error.jsonl
│
├── memory/                         ← Persistent memory (future)
│   └── [custom memory structures]
│
├── contexts/                       ← Additional context files
│   ├── crm.md
│   ├── inventory.md
│   └── [...]
│
├── config.yaml                     ← Main configuration
├── soul.md                         ← Agent personality
└── [other project files]
```

### File Formats

**Ticket JSON** (inbox/outbox):
```json
{
  "id": "ticket_20260405_001",
  "status": "pending|processing|done|error|waiting_input",
  "created": "2026-04-05T10:30:00-03:00",
  "updated": "2026-04-05T10:30:15-03:00",
  "source": {
    "channel": "whatsapp|telegram|slack|gmail|dispatch",
    "peer_id": "+1555000100",
    "peer_name": "Alice Johnson",
    "group": null,
    "message_id": "wa_msg_abc123"
  },
  "instruction": "User's message or instruction",
  "context": {
    "conversation_history": [],
    "attachments": [],
    "reply_to_ticket": null
  },
  "routing": {
    "target_skill": "clawork-soul",
    "priority": "normal|high|critical|low",
    "deadline": null
  },
  "result": {
    "status": "success|error",
    "output": "Response text",
    "files": [],
    "reply_sent": false,
    "completed_at": null
  },
  "retry_count": 0
}
```

**Session JSONL** (sessions/{channel}/{peer_id}.jsonl):
```
{"ts": "2026-04-05T10:30:00-03:00", "role": "user", "content": "...", "channel": "whatsapp", "peer": "+1555000100"}
{"ts": "2026-04-05T10:30:15-03:00", "role": "assistant", "content": "...", "channel": "whatsapp", "peer": "+1555000100"}
```

**Log JSONL** (logs/*.jsonl):
```
{"ts": "2026-04-05T10:30:00-03:00", "event": "heartbeat_start", "channels": ["whatsapp", "gmail"]}
{"ts": "2026-04-05T10:30:15-03:00", "event": "tickets_created", "count": 3}
{"ts": "2026-04-05T10:30:45-03:00", "event": "tickets_processed", "count": 3, "errors": 0}
```

---

## Design Decisions

### 1. Filesystem as Message Bus

**Decision**: Use filesystem (JSON files) as the primary message bus between components.

**Rationale**:
- Cowork has native filesystem access
- No external infrastructure needed (no queues, DBs, etc.)
- Human-inspectable (use `cat` to debug)
- Atomic operations (file creation/move)
- Compatible with OpenClaw's philosophy
- Works with scheduled tasks

**Alternatives considered**:
- Redis/message queue: Would require external service
- SQLite database: Slower, less transparent
- Memory-based state: Lost on process restart

### 2. Browser-Based Messaging (vs. ADB)

**Decision**: Use WhatsApp Web/Telegram Web + Computer Use instead of ADB-controlled native apps.

**Rationale**:
- More stable (web UI changes less than app)
- No emulator required
- Computer Use already knows how to control Chrome
- Fewer dependencies
- Lower barrier to entry

**Trade-offs**:
- Can't use foreground notifications
- Requires keeping tabs open
- Slightly slower (UI automation vs. direct API)

**ADB approach**: Kept as experimental Phase 4 module for power users who need native app control.

### 3. YAML Configuration

**Decision**: Use YAML instead of JSON for config.yaml.

**Rationale**:
- More human-readable (users edit this manually)
- Supports comments
- Less verbose syntax
- Easier to maintain

**Alternatives considered**:
- JSON: Less readable, no comments
- TOML: Not as widely supported
- YAML as JSONC: Compromise that chose YAML

### 4. Skill-Based Architecture

**Decision**: Each component (router, soul, sessions, messenger) is a separate skill.

**Rationale**:
- Modularity: Each skill has single responsibility
- Reusability: Skills can be invoked independently
- Testability: Skills can be tested in isolation
- Extensibility: Users can add custom skills
- Composability: Skills can call other skills

**Alternative**: Monolithic skill that handles everything (rejected as inflexible).

### 5. Per-Peer Session Model

**Decision**: Maintain separate conversation history for each peer in each channel.

**Rationale**:
- Isolates conversations (privacy)
- Allows per-person personalization
- Matches user mental model ("I have different conversations with different people")
- Enables group conversations (separate from DMs)

**Alternative**: Per-channel sessions (loses per-person context).

### 6. JSONL Session Format

**Decision**: Use newline-delimited JSON (JSONL) for session storage.

**Rationale**:
- Append-only (efficient writes)
- Human-readable (can inspect with `cat`)
- Easy to parse line-by-line
- Compatible with log aggregation tools
- Supports batch summarization

**Alternative**: Single JSON array (would require rewriting entire file to append).

### 7. Compaction with Summarization

**Decision**: When sessions exceed threshold, summarize old messages and keep only recent ones.

**Rationale**:
- Prevents token bloat in context
- Preserves important historical context
- Reduces processing time
- Keeps most recent interactions (highest relevance)

**Algorithm**: Keep last N lines, summarize everything before that.

### 8. No External Dependencies for Core

**Decision**: Core Clawork (Phase 1-3) requires only Cowork, no external services.

**Rationale**:
- Maximizes reliability
- Minimizes setup complexity
- No API keys required
- Works offline (except for channel APIs)
- Respects ToS constraints

**Optional modules**: ADB gateway, cloud scheduling can have external dependencies.

---

## Performance Considerations

### Ticket Processing Throughput

With default config:
- Heartbeat interval: 15 minutes
- Max tickets per heartbeat: 10
- Average response time: 3-5 seconds per ticket

**Calculated throughput**: ~40 messages/hour

### Session Compaction Overhead

- Compaction happens when session exceeds 200 lines
- Takes ~1-2 seconds for typical sessions
- Reduces future context lookup time

### Memory Usage

- Typical session file: 50-200 KB (50 lines × ~2-4 KB per line)
- Config loading: < 10 KB
- Soul file: < 5 KB
- Per-ticket overhead: ~1 KB

### Filesystem Scalability

- Inbox/outbox: Each ticket is a separate file
  - Tested up to 10k files in single directory (no issues)
  - Recommend archiving after 24h for maintainability

- Sessions: One file per peer per channel
  - With compaction: typically 100-500 lines per file
  - Can have hundreds of files without issues
  - Filesystem supports millions of files

---

## Error Handling

### Ticket Processing Errors

```
If skill fails processing a ticket:
1. Update ticket.status = "error"
2. Increment ticket.retry_count
3. If retry_count < 3:
   - Leave ticket in inbox
   - Wait for next heartbeat to retry
4. If retry_count >= 3:
   - Mark as permanent error
   - Move to error directory
   - Create error ticket for user notification
5. Log error with full context to ~/claw/logs/error.jsonl
```

### Channel Errors

**WhatsApp Web session lost**:
- Messenger detects QR code appears
- Creates "error" ticket
- Notifies user via Dispatch
- Awaits human to rescan QR code

**Channel disabled in config**:
- Heartbeat skips disabled channels
- No error, just silent skip
- Can be re-enabled by editing config

### Skill Invocation Errors

**If a skill cannot be found**:
- Router logs error
- Ticket status = "error"
- Creates error notification
- Includes available skills in message

---

## Security Considerations

### Data Isolation

- Sessions are stored locally in `~/claw/sessions/`
- Each peer's conversation is in a separate file
- File permissions: User-only access (700)

### SOUL Privacy

- SOUL file is local only (no cloud sync)
- Contains sensitive personality/instructions
- Should be protected (chmod 600)

### Credential Handling

- WhatsApp/Telegram sessions: Stored in Chrome browser
- Cowork credentials: Managed by Cowork
- No credentials stored in Clawork files

### Attachment Handling

- Attachments referenced in tickets (not embedded)
- Actual files stored in browser cache or downloads
- Risk: Depends on browser security model

---

## Testing & Validation

### Test Scenarios

1. **Router routing logic**
   - Create test tickets with various metadata
   - Verify correct skill is selected
   - Test rule priority (first match wins)

2. **Session compaction**
   - Create long session file
   - Trigger compaction
   - Verify summary is generated
   - Verify recent lines are preserved
   - Verify old lines are not lost

3. **Multi-channel flow**
   - Send message via WhatsApp
   - Verify ticket created in inbox
   - Verify response sent back to WhatsApp

4. **Error recovery**
   - Simulate skill failure
   - Verify retry logic
   - Verify error tracking

### Debugging Techniques

1. **Inspect inbox**: `cat ~/claw/inbox/*.json | jq`
2. **Inspect session**: `cat ~/claw/sessions/whatsapp/+1555*.jsonl`
3. **Inspect logs**: `tail -f ~/claw/logs/heartbeat.jsonl`
4. **Trace ticket**: Find ticket ID in logs, follow through inbox → processing → outbox
5. **Test skill directly**: Invoke skill with test ticket manually

---

This architecture prioritizes simplicity, transparency, and working within Cowork's native boundaries. Each component is independent and replaceable. The filesystem-as-bus approach makes everything inspectable and debuggable with standard Unix tools.