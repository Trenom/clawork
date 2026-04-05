# clawork-sessions — Session History Management by Peer and Channel

This skill manages conversation history, maintaining one JSONL file per peer per channel. It is invoked internally by `clawork-soul` and other skills that need conversation context.

## File Structure

```
~/claw/sessions/
├── whatsapp/
│   ├── +1555000100.jsonl
│   └── +1555000200.jsonl
├── telegram/
│   ├── user_123456.jsonl
│   └── group_teamwork.jsonl
├── slack/
│   └── channel_general.jsonl
└── gmail/
    └── user@example.com.jsonl
```

## JSONL Format

Each line is an independent JSON object (one interaction):

```json
{"ts": "2026-04-05T10:30:00-04:00", "role": "user", "content": "Hi, I need to check my order status", "channel": "whatsapp", "peer": "+1555000100", "ticket_id": "ticket_001"}
{"ts": "2026-04-05T10:30:15-04:00", "role": "assistant", "content": "Looking up your order...", "channel": "whatsapp", "peer": "+1555000100", "ticket_id": "ticket_001"}
```

Fields:
- `ts`: ISO-8601 timestamp with timezone
- `role`: `"user"` or `"assistant"`
- `content`: Message text
- `channel`: Source channel
- `peer`: Peer ID (number, username, email)
- `ticket_id`: ID of the ticket that generated this interaction (for traceability)

## Operations

### Read History (get_context)

Invoked when a skill needs conversation context:

1. Determine the file: `~/claw/sessions/{channel}/{peer_id}.jsonl`
2. If it doesn't exist → return empty array (new conversation)
3. Read the last N lines (N = `config.yaml` → `limits.session_context_lines`, default 50)
4. If the first line is a `[SUMMARY]`, always include it as base context
5. Return as an array of JSON objects

### Save Interaction (append)

After processing a ticket:

1. Create file if it doesn't exist
2. Append one JSON line for the user's message
3. Append one JSON line for the assistant's response
4. If the file exceeds `limits.session_compact_threshold` (default 200 lines) → invoke compaction

### Compact Session (compact)

When a session file grows too large:

1. Read all lines from the file
2. Separate: the last N lines are preserved intact
3. Earlier lines are summarized into a concise paragraph
4. Write new file with:
   - Line 1: `{"ts": "...", "role": "system", "content": "[SUMMARY] Summary of previous conversation: ..."}`
   - Lines 2+: the N preserved lines
5. Save backup of original file to `~/claw/sessions/.archive/`

### Summary Format

The summary should capture:
- Main topics discussed
- Decisions made
- Relevant personal information mentioned
- Pending requests
- General tone of the relationship

Example:
```
[SUMMARY] Conversation with Alice Johnson (+1555000100) since 2026-03-01.
Topics: frequent queries about order #12345 status, tracking information,
delivery timelines. Alice is a regular customer, informal tone, prefers concise responses.
Last request: follow-up on shipment status.
```

## Migration from OpenClaw

```bash
# OpenClaw sessions are in ~/.openclaw/state/sessions/
# Similar format but with additional metadata
# Migration script:
~/claw/scripts/import-openclaw-sessions.sh
```

The script should:
1. Read session files from OpenClaw
2. Extract compatible fields (ts, role, content)
3. Add channel and peer inferred from filename
4. Write in Clawork JSONL format