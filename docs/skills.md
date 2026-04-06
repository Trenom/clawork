# Skills Reference

Clawork is built as a modular skills system. Each component is an independent skill that can be invoked by the router or other skills.

## Core Skills

| Skill | Purpose | Phase |
|-------|---------|-------|
| `clawork-soul` | Agent personality and response generation | Phase 1 |
| `clawork-router` | Ticket routing and dispatch | Phase 1 |
| `clawork-sessions` | Conversation history management | Phase 1 |
| `clawork-messenger` | WhatsApp Web / Telegram Web integration | Phase 2 |

---

## clawork-soul

The Soul defines the personality, capabilities, and base behavior of the Clawork agent. It is the direct equivalent of the SOUL from OpenClaw, ported to the native Cowork ecosystem.

### Activation

- The router dispatches a ticket without a specific skill target
- A ticket has `routing.target_skill: "clawork-soul"`
- No routing rule matches (default handler)

### Execution Flow

1. **Load Personality** — Reads `~/claw/soul.md` for the user's custom personality. Falls back to a neutral default if not found.
2. **Load Session History** — Invokes `clawork-sessions` to get conversation context with the peer.
3. **Process the Ticket** — Understands the instruction, uses tools if needed, generates a response.
4. **Send Response** — Routes the reply back through the appropriate channel.
5. **Save Interaction** — Appends the exchange to the session history.

### Response Routing

| Channel | Send Method |
|---------|-------------|
| WhatsApp | Invoke `clawork-messenger` |
| Telegram | Invoke `clawork-messenger` |
| Slack | Native Slack connector |
| Gmail | Native Gmail connector (reply) |
| Dispatch | Respond in Cowork context |

### Default Personality

If no custom `soul.md` exists:

> You are an efficient and straightforward personal assistant. You respond in the same language you are spoken to in. You are concise. If you don't know something, you say so. If you can solve it with available tools, you do it without asking. You maintain context from previous conversations.

---

## clawork-router

The routing engine reads tickets from the inbox, consults routing rules in `config.yaml`, and dispatches each ticket to the appropriate skill.

### Execution Logic

**Step 1 — Read Inbox**

```
List all .json files in ~/claw/inbox/
Filter those with status: "pending"
Sort by: priority (critical > high > normal > low), then by created (oldest first)
Limit to max_tickets_per_heartbeat (default: 10)
```

**Step 2 — Apply Routing Rules**

For each ticket, iterate through `routing.rules` in `config.yaml`. First matching rule wins:

```
IF ticket.source.channel matches rule.match.channel (or "*")
  AND (no rule.match.peer OR peer_id matches)
  AND (no rule.match.group OR group matches)
  AND (no rule.match.content_contains OR instruction contains text)
THEN → Apply rule.action (skill, priority, context_file)
```

If no rule matches → use `routing.default`.

**Step 3 — Execute Skill**

Invoke the matched skill with the ticket. If the rule has `context_file`, load it as supplementary context.

**Step 4 — Handle Result**

| Ticket Status | Action |
|---------------|--------|
| `done` | Move from `inbox/` to `outbox/` |
| `error` | Leave in inbox, increment `retry_count` (max 3) |
| `waiting_input` | Leave in inbox, process next cycle |

**Step 5 — Log**

Write cycle summary to `~/claw/logs/router.jsonl`.

### Advanced Routing

- **Content-based**: `content_contains` supports case-insensitive matching and OR patterns (`"order|invoice|shipping"`)
- **External orchestrator**: Route to `external-orchestrator-bridge` to hand off tickets to an external agent system
- **Attachment-aware**: Router can add instructions when tickets contain attachments

---

## clawork-sessions

Manages conversation history with one JSONL file per peer per channel.

### File Structure

```
~/claw/sessions/
├── whatsapp/
│   ├── +1555000100.jsonl
│   └── +1555000200.jsonl
├── telegram/
│   └── user_123456.jsonl
├── slack/
│   └── channel_general.jsonl
└── gmail/
    └── user@example.com.jsonl
```

### JSONL Format

Each line is an independent JSON object:

```json
{"ts": "2026-04-05T10:30:00-04:00", "role": "user", "content": "Hi, check my order", "channel": "whatsapp", "peer": "+1555000100", "ticket_id": "ticket_001"}
{"ts": "2026-04-05T10:30:15-04:00", "role": "assistant", "content": "Looking up your order...", "channel": "whatsapp", "peer": "+1555000100", "ticket_id": "ticket_001"}
```

### Operations

| Operation | Description |
|-----------|-------------|
| `get_context` | Read last N lines of history (N = `limits.session_context_lines`, default 50). Always includes `[SUMMARY]` line if present. |
| `append` | Save user message + assistant response after processing a ticket. |
| `compact` | When file exceeds `limits.session_compact_threshold` (200 lines), summarize older lines into a `[SUMMARY]` and keep recent ones. |

### Compaction Summary

The summary captures: main topics discussed, decisions made, relevant personal information, pending requests, and relationship tone.

---

## clawork-messenger

Handles bidirectional communication with WhatsApp Web and Telegram Web using browser automation (Computer Use / Claude in Chrome).

### Supported Channels

| Channel | URL | Method |
|---------|-----|--------|
| WhatsApp Web | `https://web.whatsapp.com` | Claude in Chrome |
| Telegram Web | `https://web.telegram.org/k/` | Claude in Chrome |

!!! note
    Connector-based channels (Slack, Gmail) do **not** use this skill. They use Cowork's native MCP connectors.

### Operations

**read_channel** — Detect and ingest unread messages:

1. Navigate to the channel URL
2. Look for chats with unread indicators
3. Extract sender, timestamp, text, attachments
4. Create tickets in `~/claw/inbox/`

**send_message** — Send a response to a peer:

1. Search for the peer's chat
2. Type and send the message (respects `max_message_length`)
3. Verify delivery
4. Wait `message_delay_seconds` before next send

**check_status** — Verify channel session is active. Returns: `connected`, `needs_auth`, or `error`.

### Anti-Detection

| Measure | Value |
|---------|-------|
| Delay between actions | 1-2 seconds |
| Delay between messages | Configurable (default 3s) |
| Timing variation | ±500ms random |
| Max chats read/cycle | 20 |
| Max messages sent/cycle | 10 |
| Typing simulation | 30-80ms per character |
| Rate limit pause | 5 minutes |

### Error Handling

| Error | Action |
|-------|--------|
| Session expired (QR) | Mark channel as `needs_auth`, notify via Dispatch |
| Chat not found | Set ticket status to `error` |
| Message not sent | Retry up to 3 times with backoff (3s, 10s, 30s) |
| Rate limit detected | Pause channel for 5 minutes |
| UI changed | Log error with screenshot, notify for update |

### Dependencies

- **Claude in Chrome**: `navigate`, `read_page`, `form_input`, `computer`, `get_page_text`
- **clawork-sessions**: Save history after sending
- **clawork-router**: Invokes messenger for sending
- **Filesystem**: Read/write ticket JSON files

---

## Integration Points

Clawork integrates with custom skills through the routing system. Configure which skills to route to in `config.yaml`:

```yaml
routing:
  rules:
    - match:
        channel: "*"
        content_contains: "order"
      action:
        skill: "crm-agent"
        priority: "high"
  default:
    skill: "clawork-soul"
```

Available routing targets include any skill installed in your Cowork project — CRM agents, inventory agents, data retrieval skills, or custom business logic.
