# Ticket Protocol

All messages in Clawork flow through a standardized ticket format (JSON). This protocol enables multi-channel message normalization, uniform routing, extensible workflows, and full auditability.

## Ticket Format

```json
{
  "id": "ticket_20260405_001",
  "status": "pending",
  "created": "2026-04-05T10:30:00-03:00",
  "updated": null,
  "retry_count": 0,

  "source": {
    "channel": "whatsapp",
    "peer_id": "+1555000100",
    "peer_name": "Alice Johnson",
    "group": null,
    "message_id": "wa_msg_abc123"
  },

  "instruction": "Check order #12345",

  "context": {
    "conversation_history": [],
    "attachments": [],
    "reply_to_ticket": null
  },

  "routing": {
    "target_skill": null,
    "priority": "normal",
    "deadline": null
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

## Field Reference

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | String | Unique identifier (`ticket_{date}_{seq}` or `{channel}_{timestamp}_{hash}`) |
| `status` | Enum | Current state (see lifecycle below) |
| `created` | ISO-8601 | Creation timestamp with timezone |
| `updated` | ISO-8601 | Last modification timestamp |
| `retry_count` | Integer | Number of processing retries (max 3) |

### Source Block

| Field | Type | Description |
|-------|------|-------------|
| `channel` | Enum | `whatsapp`, `telegram`, `slack`, `gmail`, `dispatch` |
| `peer_id` | String | Sender identifier (phone, username, email) |
| `peer_name` | String | Display name of the sender |
| `group` | String | Group name (if from a group chat) |
| `message_id` | String | Platform-specific message ID |

### Context Block

| Field | Type | Description |
|-------|------|-------------|
| `conversation_history` | Array | Recent messages for context |
| `attachments` | Array | Files attached to the message |
| `reply_to_ticket` | String | ID of ticket being replied to |

### Routing Block

| Field | Type | Description |
|-------|------|-------------|
| `target_skill` | String | Skill to handle this ticket (set by router) |
| `priority` | Enum | `critical`, `high`, `normal`, `low` |
| `deadline` | ISO-8601 | Optional deadline for processing |

### Result Block

| Field | Type | Description |
|-------|------|-------------|
| `status` | Enum | `success`, `error`, or `null` |
| `output` | String | Response text or error message |
| `files` | Array | Generated files |
| `reply_sent` | Boolean | Whether reply was sent to the channel |
| `completed_at` | ISO-8601 | Completion timestamp |

## Ticket Lifecycle

```
pending ──→ processing ──→ done
                │
                ├──→ error (retry up to 3x)
                │
                └──→ waiting_input (paused)
```

| Status | Description |
|--------|-------------|
| `pending` | Waiting to be processed |
| `processing` | Currently being handled by a skill |
| `done` | Completed successfully, reply sent |
| `error` | Failed processing (retries or permanent) |
| `waiting_input` | Paused, waiting for user input or external data |

## File Location

- **Pending tickets**: `~/claw/inbox/`
- **Completed tickets**: `~/claw/outbox/`
- **Naming convention**: `{id}.json`

For the full specification, see `docs/ticket-protocol.md` in the repository.
