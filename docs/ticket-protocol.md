# Clawork Ticket Protocol Specification

Formal specification of the Clawork ticket format and message flow protocol.

---

## Overview

Clawork uses a standardized ticket format (JSON) for all inter-component communication. This protocol allows:
- Multi-channel message normalization
- Uniform routing logic
- Extensible processing workflows
- Debugging and auditability

A ticket represents a single message or task that flows through the system from receipt to completion.

---

## Ticket Format

### Complete Specification

```json
{
  "id": "ticket_20260405_001",
  "status": "pending|processing|done|error|waiting_input",
  "created": "2026-04-05T10:30:00-05:00",
  "updated": "2026-04-05T10:30:15-05:00",
  "retry_count": 0,

  "source": {
    "channel": "whatsapp|telegram|slack|gmail|dispatch",
    "peer_id": "+1555000100",
    "peer_name": "Alice Johnson",
    "group": null,
    "message_id": "wa_msg_abc123"
  },

  "instruction": "Send me a summary of order #12345",

  "context": {
    "conversation_history": [],
    "attachments": [],
    "reply_to_ticket": null
  },

  "routing": {
    "target_skill": null,
    "priority": "normal|high|critical|low",
    "deadline": null,
    "context_file": null
  },

  "result": {
    "status": null,
    "output": null,
    "files": [],
    "reply_sent": false,
    "completed_at": null
  }
}
```

### Top-Level Fields

#### `id` (required)
**Type**: String
**Format**: `ticket_{TIMESTAMP}_{SEQUENCE}`
**Example**: `ticket_20260405_001`, `ticket_20260405_142358_abc`
**Description**: Unique identifier for this ticket across all time.
**Generation**: Created by heartbeat when ticket is first written.
**Immutable**: Once created, never changes.

#### `status` (required)
**Type**: Enum
**Values**:
- `"pending"` — Waiting to be processed
- `"processing"` — Currently being handled by a skill
- `"done"` — Completed successfully
- `"error"` — Failed processing, will retry
- `"waiting_input"` — Paused, waiting for external data

**Transitions**:
```
pending ──→ processing ──→ done (or)
                          error (or)
                          waiting_input
```

**Rules**:
- Router sets to `"processing"` before invoking skill
- Skill updates to `"done"`, `"error"`, or `"waiting_input"`
- Heartbeat retries `"error"` tickets (if retry_count < limit)
- `"done"` tickets are moved to outbox and archived after 24h

#### `created` (required)
**Type**: ISO 8601 timestamp with timezone
**Format**: `"2026-04-05T10:30:00-05:00"`
**Description**: When the ticket was first created.
**Immutable**: Never changes.
**Timezone**: Must include timezone offset.

#### `updated` (optional)
**Type**: ISO 8601 timestamp with timezone
**Format**: `"2026-04-05T10:30:15-05:00"`
**Description**: When the ticket was last modified.
**Auto-updated**: Whenever any field changes.

#### `retry_count` (optional)
**Type**: Number
**Default**: `0`
**Description**: How many times this ticket has been retried.
**Increment rule**: Incremented by router when a skill returns error.
**Limit**: Default 3 retries. After that, ticket becomes permanent error.

---

### Source Section

Information about the message origin.

#### `source.channel` (required)
**Type**: Enum
**Values**: `"whatsapp"`, `"telegram"`, `"slack"`, `"gmail"`, `"dispatch"`, `"filesystem"`
**Description**: Which channel this message came from.

#### `source.peer_id` (required)
**Type**: String
**Format**: Channel-specific
**Examples**:
- WhatsApp: `"+1555000100"` (with country code)
- Telegram: `"user_123456"` or `"@username"`
- Gmail: `"sender@example.com"`
- Slack: `"U12345"` or `"@username"`
- Dispatch: User ID from Cowork

**Description**: Identifier for the person who sent the message.

#### `source.peer_name` (optional)
**Type**: String
**Example**: `"Alice Johnson"`, `"alice@company.com"`
**Description**: Display name of the sender. Used for logs and replies.

#### `source.group` (optional)
**Type**: String
**Example**: `"family"`, `"dev-team"`
**Description**: If message came from a group, the group ID or name.
**Null if**: Message is from a direct message (1-on-1).

#### `source.message_id` (optional)
**Type**: String
**Example**: `"wa_msg_abc123"`, `"telegram_msg_456"`
**Description**: Unique ID of the message in the originating platform.
**Purpose**: Allows replying to specific message (threading).

---

### Instruction Section

The user's request or message.

#### `instruction` (required)
**Type**: String
**Description**: The text content of the message.
**Length**: Should not exceed `config.limits.max_message_length`.
**Special characters**: UTF-8 encoded (including emojis).

**Examples**:
- `"Hello, I need help"`
- `"Send me a summary of order #12345"`
- `"Meeting tomorrow at 10am?"`

---

### Context Section

Additional data for processing.

#### `context.conversation_history` (optional)
**Type**: Array of objects
**Description**: Previous messages in this conversation.
**Populated by**: `clawork-sessions` skill when loading context.
**Format**: Each element is a message object:
```json
{
  "ts": "2026-04-05T10:29:00-05:00",
  "role": "user|assistant",
  "content": "Previous message text"
}
```

#### `context.attachments` (optional)
**Type**: Array of objects
**Description**: Files attached to the message (images, documents, etc.).
**Format**:
```json
{
  "type": "image|document|audio|video",
  "filename": "photo.jpg",
  "path": "/tmp/photo.jpg",
  "mime_type": "image/jpeg",
  "size_bytes": 102400
}
```

**Note**: Actual files are stored on disk. The ticket only references them.

#### `context.reply_to_ticket` (optional)
**Type**: String (ticket ID)
**Description**: If this is a reply to an earlier message, the ID of that message's ticket.
**Purpose**: Thread continuity.

---

### Routing Section

Instructions for routing and priority.

#### `routing.target_skill` (optional on creation, required after routing)
**Type**: String
**Example**: `"clawork-soul"`, `"order-agent"`, `"custom-skill"`
**Description**: Which skill should process this ticket.
**Set by**: Router skill based on routing rules.
**Immutable after set**: Don't change this after router has decided.

#### `routing.priority` (optional)
**Type**: Enum
**Values**: `"critical"`, `"high"`, `"normal"`, `"low"`
**Default**: `"normal"`
**Description**: Processing priority.
**Effect**: Router processes critical > high > normal > low.
**Set by**: Routing rule in config.yaml.

#### `routing.deadline` (optional)
**Type**: ISO 8601 timestamp
**Example**: `"2026-04-05T11:30:00-05:00"`
**Description**: Time by which this ticket should be completed.
**Current use**: Logged but not enforced. Future: auto-escalate if deadline passes.

#### `routing.context_file` (optional)
**Type**: String (path)
**Example**: `"./contexts/vip.md"`, `"~/claw/contexts/team.md"`
**Description**: Additional context file to load.
**Set by**: Routing rule if matched rule includes context_file.
**Used by**: Skill can load this file for additional instructions.

---

### Result Section

Outcome of processing.

#### `result.status` (optional)
**Type**: Enum
**Values**: `"success"`, `"error"`, `"partial"`
**Description**: Whether processing succeeded.
**Set by**: Skill after it completes.

#### `result.output` (optional)
**Type**: String
**Description**: The response or result text.
**Example**: `"Order #12345 has 8 items..."`
**Populated by**: Skill.
**Sent as**: Reply to the originating channel.

#### `result.files` (optional)
**Type**: Array of strings (paths)
**Example**: `["/tmp/order_summary.pdf", "/tmp/attachments.zip"]`
**Description**: Files generated or prepared as part of processing.
**Management**: Skill is responsible for cleanup after sending.

#### `result.reply_sent` (optional)
**Type**: Boolean
**Default**: `false`
**Description**: Whether the reply has been sent to the origin channel.
**Set by**: Soul skill (or messenger) after successfully sending.

#### `result.completed_at` (optional)
**Type**: ISO 8601 timestamp
**Description**: When processing finished.
**Set by**: Skill when it's done.

---

## Ticket Lifecycle in Detail

### Phase 1: Creation (Heartbeat)

```json
{
  "id": "ticket_20260405_001",
  "status": "pending",
  "created": "2026-04-05T10:30:00-05:00",
  "updated": null,

  "source": {
    "channel": "whatsapp",
    "peer_id": "+1555000100",
    "peer_name": "Alice Johnson",
    "group": null,
    "message_id": "wa_msg_abc123"
  },

  "instruction": "Hello, I need help",

  "context": {
    "conversation_history": [],
    "attachments": [],
    "reply_to_ticket": null
  },

  "routing": {
    "target_skill": null,
    "priority": "normal",
    "deadline": null,
    "context_file": null
  },

  "result": {
    "status": null,
    "output": null,
    "files": [],
    "reply_sent": false,
    "completed_at": null
  },

  "retry_count": 0
}
```

**What happens**:
1. Heartbeat reads message from WhatsApp Web
2. Creates ticket with source information
3. Sets status to `"pending"`
4. Writes to `~/claw/inbox/ticket_20260405_001.json`

---

### Phase 2: Routing (Router Skill)

```json
{
  "id": "ticket_20260405_001",
  "status": "processing",
  "updated": "2026-04-05T10:30:05-05:00",

  "context": {
    "conversation_history": [
      {"ts": "2026-04-04T15:00:00-05:00", "role": "user", "content": "Hello, how are you?"},
      {"ts": "2026-04-04T15:00:30-05:00", "role": "assistant", "content": "I'm doing well, how are you?"}
    ],
    "attachments": [],
    "reply_to_ticket": null
  },

  "routing": {
    "target_skill": "clawork-soul",
    "priority": "normal",
    "deadline": null,
    "context_file": null
  }
}
```

**What happens**:
1. Router reads ticket from inbox
2. Loads conversation history via `clawork-sessions`
3. Applies routing rules from config.yaml
4. Determines target_skill: `"clawork-soul"`
5. Updates status to `"processing"`
6. Updates ticket JSON in-place
7. Invokes `clawork-soul` skill with this ticket

---

### Phase 3: Processing (Soul Skill)

```json
{
  "id": "ticket_20260405_001",
  "status": "done",
  "updated": "2026-04-05T10:30:15-05:00",

  "result": {
    "status": "success",
    "output": "I'm doing well! How can I help?",
    "files": [],
    "reply_sent": true,
    "completed_at": "2026-04-05T10:30:15-05:00"
  }
}
```

**What happens**:
1. Soul skill receives ticket
2. Loads personality from `soul.md`
3. Loads conversation history (already in ticket)
4. Calls Claude with full context
5. Generates response
6. Stores response in `result.output`
7. Sends response via WhatsApp Web
8. Updates `result.reply_sent = true`
9. Appends both user and assistant message to session file
10. Updates `result.status = "success"`
11. Updates `status = "done"`
12. Writes updated ticket back to inbox

---

### Phase 4: Archive (Router on next heartbeat)

Router sees ticket with `status: "done"`:
1. Moves ticket from `inbox/` to `outbox/`
2. Logs completion to `logs/router.jsonl`

After 24h, cleanup action:
1. Moves old `outbox/` tickets to `outbox/archive/`
2. Frees up space, keeps history

---

## Error Handling Protocol

### Skill Failure

If skill encounters an error:

```json
{
  "status": "error",
  "retry_count": 1,

  "result": {
    "status": "error",
    "output": "Could not find order #9999999",
    "files": [],
    "reply_sent": false,
    "completed_at": "2026-04-05T10:30:20-05:00"
  }
}
```

**Router behavior**:
1. Sees `status: "error"`
2. Increments `retry_count` to 1
3. Leaves ticket in inbox
4. On next heartbeat, retries

**After 3 retries** (`retry_count >= 3`):
1. Marks as permanent error
2. Moves to error directory (or keeps in inbox with error flag)
3. Notifies user (via Dispatch or email)

### Validation Errors

If ticket is malformed (invalid JSON):
1. Heartbeat catches parse error
2. Creates separate error ticket
3. Notifies user
4. Skips malformed ticket

### Timeout Errors

If skill takes too long:
1. Heartbeat has timeout (e.g., 30 seconds)
2. Kills hung skill
3. Sets ticket to `"waiting_input"` or `"error"`
4. Retries on next heartbeat

---

## Channel-Specific Variations

### WhatsApp

```json
{
  "source": {
    "channel": "whatsapp",
    "peer_id": "+1555000100",
    "peer_name": "Alice Johnson",
    "group": null,
    "message_id": "wa_msg_abc123"
  },
  "context": {
    "attachments": [
      {
        "type": "image",
        "filename": "photo.jpg",
        "path": "/tmp/whatsapp_photo.jpg",
        "mime_type": "image/jpeg"
      }
    ]
  }
}
```

**Special behavior**:
- Attachments are saved from WhatsApp Web
- Message IDs allow thread replies
- Emojis and special characters preserved
- Read receipts controlled by config

### Telegram

```json
{
  "source": {
    "channel": "telegram",
    "peer_id": "@username",
    "peer_name": "John",
    "group": "dev-team",
    "message_id": "telegram_msg_456"
  }
}
```

**Special behavior**:
- Peer IDs include `@` prefix for users
- Groups have separate IDs from DMs
- Markdown formatting preserved in instruction

### Slack

```json
{
  "source": {
    "channel": "slack",
    "peer_id": "U12345",
    "peer_name": "Alice Smith",
    "group": "C67890",
    "message_id": "slack_msg_123"
  }
}
```

**Special behavior**:
- Thread replies via message_id
- Reactions handled separately
- User IDs always start with U or W

### Gmail

```json
{
  "source": {
    "channel": "gmail",
    "peer_id": "sender@example.com",
    "peer_name": "John Smith",
    "group": null,
    "message_id": "msg_id_from_gmail"
  },
  "context": {
    "attachments": [
      {
        "type": "document",
        "filename": "report.pdf",
        "path": "/tmp/gmail_attachment_report.pdf",
        "mime_type": "application/pdf"
      }
    ]
  }
}
```

**Special behavior**:
- Subject line included in instruction or context
- Reply uses Gmail reply (not forward)
- Attachments downloaded to temp folder

---

## Protocol Rules & Constraints

### Immutable Fields (never change after creation)

- `id`
- `created`
- `source` (all fields)

### Router-Only Fields (router sets these)

- `routing.target_skill`
- `routing.priority`
- `routing.context_file`

### Skill-Only Fields (skill sets these)

- `result.*`
- `status` (when transitioning to done/error/waiting)
- `updated` (always when anything changes)

### Heartbeat-Only Fields

- `retry_count`

### Append-Only Context

- `context.conversation_history` — Items are added, never removed
- `context.attachments` — Items are added, never removed

---

## Validation Rules

### Required Fields (must always exist)

- `id`
- `status`
- `created`
- `source.channel`
- `source.peer_id`
- `instruction`

### Format Validation

**ID format**:
```regex
^ticket_\d{8}_\d{6}_[a-z0-9]{3,}$
or
^ticket_\d{8}_\d{3}$
```

**Timestamps**:
```regex
^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$
```

**Channel values**:
```
"whatsapp" | "telegram" | "slack" | "gmail" | "dispatch" | "filesystem"
```

**Status values**:
```
"pending" | "processing" | "done" | "error" | "waiting_input"
```

**Priority values**:
```
"critical" | "high" | "normal" | "low"
```

---

## Examples

### Example 1: Simple WhatsApp Message

```json
{
  "id": "ticket_20260405_001",
  "status": "done",
  "created": "2026-04-05T10:30:00-05:00",
  "updated": "2026-04-05T10:30:15-05:00",

  "source": {
    "channel": "whatsapp",
    "peer_id": "+1555000100",
    "peer_name": "Alice Johnson",
    "group": null,
    "message_id": "wa_msg_abc123"
  },

  "instruction": "Hello",

  "context": {
    "conversation_history": [
      {
        "ts": "2026-04-05T10:00:00-05:00",
        "role": "user",
        "content": "Hello, how are you?"
      },
      {
        "ts": "2026-04-05T10:00:15-05:00",
        "role": "assistant",
        "content": "I'm doing well, how are you?"
      }
    ],
    "attachments": [],
    "reply_to_ticket": null
  },

  "routing": {
    "target_skill": "clawork-soul",
    "priority": "normal",
    "deadline": null,
    "context_file": null
  },

  "result": {
    "status": "success",
    "output": "I'm here, what do you need?",
    "files": [],
    "reply_sent": true,
    "completed_at": "2026-04-05T10:30:15-05:00"
  },

  "retry_count": 0
}
```

### Example 2: Slack Message with Attachments

```json
{
  "id": "ticket_20260405_002",
  "status": "done",
  "created": "2026-04-05T11:00:00-05:00",
  "updated": "2026-04-05T11:01:00-05:00",

  "source": {
    "channel": "slack",
    "peer_id": "U67890",
    "peer_name": "Alice Smith",
    "group": "C123456",
    "message_id": "slack_ts_1712326800000"
  },

  "instruction": "Can you review this document?",

  "context": {
    "conversation_history": [],
    "attachments": [
      {
        "type": "document",
        "filename": "proposal.pdf",
        "path": "/tmp/slack_proposal.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 512000
      }
    ],
    "reply_to_ticket": null
  },

  "routing": {
    "target_skill": "document-review-skill",
    "priority": "high",
    "deadline": "2026-04-05T18:00:00-05:00",
    "context_file": "./contexts/review_guidelines.md"
  },

  "result": {
    "status": "success",
    "output": "Reviewed. Main points: [1] Title page needs company logo [2] Executive summary is clear [3] Budget section needs detail.",
    "files": ["/tmp/review_comments.pdf"],
    "reply_sent": true,
    "completed_at": "2026-04-05T11:01:00-05:00"
  },

  "retry_count": 0
}
```

### Example 3: Error with Retry

```json
{
  "id": "ticket_20260405_003",
  "status": "error",
  "created": "2026-04-05T12:00:00-05:00",
  "updated": "2026-04-05T12:02:00-05:00",

  "source": {
    "channel": "whatsapp",
    "peer_id": "+1555000111",
    "peer_name": "Maria Garcia",
    "group": null,
    "message_id": "wa_msg_def456"
  },

  "instruction": "Send me order #9999999",

  "routing": {
    "target_skill": "order-agent",
    "priority": "normal",
    "deadline": null,
    "context_file": null
  },

  "result": {
    "status": "error",
    "output": "Order #9999999 not found in system",
    "files": [],
    "reply_sent": false,
    "completed_at": "2026-04-05T12:02:00-05:00"
  },

  "retry_count": 1
}
```

---

## Protocol Evolution

The ticket protocol is versioned implicitly by the `id` format. Current version is implied by the format.

### Future Enhancements

1. **Versioning**: Add `protocol_version` field
2. **Encryption**: Optional `encrypted` flag for sensitive content
3. **Signing**: Optional `signature` for validation
4. **Batch processing**: Multiple instructions per ticket
5. **Dependencies**: Reference other tickets this depends on

These can be added without breaking existing tickets (graceful degradation).

---

This protocol provides a stable foundation for Clawork's message processing. All components (heartbeat, router, skills) adhere to this format for interoperability.