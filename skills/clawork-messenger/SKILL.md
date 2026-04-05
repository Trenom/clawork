# clawork-messenger — Browser-based message sending and reading

This skill handles bidirectional communication with WhatsApp Web and Telegram Web using browser automation tools available in Claude Cowork (Computer Use / Claude in Chrome).

## Activation

This skill is invoked when:
- The router needs to **send a response** to a peer on WhatsApp or Telegram
- The heartbeat needs to **read new messages** from browser channels
- A **channel status check** is needed

## Supported Channels

| Channel | URL | Method |
|---------|-----|--------|
| WhatsApp Web | https://web.whatsapp.com | Claude in Chrome |
| Telegram Web | https://web.telegram.org/k/ | Claude in Chrome |

## Operations

### 1. Read new messages (read_channel)

Invoked by the heartbeat to detect unread messages.

#### WhatsApp Web

```
1. Navigate to https://web.whatsapp.com (or verify it's already open)
2. Wait for the interface to fully load
3. Look for chats with unread message indicators (green badges)
4. For each chat with new messages:
   a. Click the chat
   b. Read new messages (those after the last processed)
   c. Extract: sender, timestamp, text content, attachments
   d. Create ticket in ~/claw/inbox/ with standard format
   e. Do NOT mark as read yet (marked after processing)
5. Return to chat list
```

**Key WhatsApp Web selectors:**
- Chat list: left panel with scroll
- Unread badge: span with green numeric badge class
- Messages: containers within the conversation panel
- Text input: contenteditable div at the bottom
- Send button: button to the right of the input

#### Telegram Web

```
1. Navigate to https://web.telegram.org/k/ (or verify it's already open)
2. Wait for the interface to fully load
3. Look for chats with unread message indicators
4. For each chat with new messages:
   a. Click the chat
   b. Read new messages
   c. Extract: sender, timestamp, text content
   d. Create ticket in ~/claw/inbox/
5. Return to chat list
```

### 2. Send message (send_message)

Invoked when a ticket has been processed and there's a response to send.

#### Input

```json
{
  "channel": "whatsapp",
  "peer_id": "+1234567890",
  "peer_name": "Contact Name",
  "message": "Your response here...",
  "ticket_id": "ticket_001"
}
```

#### WhatsApp Web Process

```
1. Navigate to WhatsApp Web if not already open
2. Search for the peer's chat:
   - Use the search field
   - Type the peer's name or number
   - Wait for results
   - Click the correct chat
3. Verify we're in the correct chat (name in header)
4. Type the message:
   - Click the text input
   - Write the content (respect max_message_length: 4000 chars)
   - If the message is too long, split into parts with delay between each
5. Send:
   - Click send button (or Enter)
6. Verify delivery:
   - Wait for "sent" checkmark (single tick)
   - If not visible in 10 seconds, report error
7. Wait message_delay_seconds (default 3s) before the next send
```

#### Telegram Web Process

```
1. Navigate to Telegram Web if not already open
2. Search for the peer's chat in the search bar
3. Click the chat
4. Type message in the input
5. Send with Enter or button
6. Verify the message appears in the conversation
7. Wait configured delay
```

### 3. Check channel status (check_status)

```
1. Attempt to navigate to the channel URL
2. Verify the session is active (not asking for QR/login)
3. Return status: "connected", "needs_auth", "error"
```

## Anti-detection and Rate Limiting

To prevent platforms from detecting automated behavior:

- **Delay between actions**: Minimum 1-2 seconds between clicks
- **Delay between messages**: Configurable (default 3 seconds)
- **Timing variation**: Add +/-500ms random variation
- **Max 20 chats read** per heartbeat cycle
- **Max 10 messages sent** per cycle
- **Simulate typing**: Type character by character with 30-80ms delay
- **Long pauses**: If CAPTCHA or rate limit detected, pause 5 minutes and retry

## Error Handling

| Error | Action |
|-------|--------|
| Session expired (QR) | Log error, mark channel as `needs_auth`, notify via Dispatch |
| Chat not found | Log warning, set ticket status to `error` with reason |
| Message not sent | Retry up to 3 times with backoff (3s, 10s, 30s) |
| Load timeout | Wait 10s, retry once, then error |
| Rate limit detected | Pause channel for 5 minutes, process other channels |
| UI changed (broken selector) | Log detailed error with screenshot, notify for update |

## Inbound Ticket Format (created when reading messages)

```json
{
  "id": "wa_{timestamp}_{peer_hash}",
  "status": "pending",
  "created": "2026-04-05T10:30:00-03:00",
  "updated": null,
  "source": {
    "channel": "whatsapp",
    "peer_id": "+1234567890",
    "peer_name": "Contact Name",
    "group": null,
    "message_id": "wa_msg_12345"
  },
  "instruction": "The received message text",
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

## Output Format (after sending response)

Update the ticket:
```json
{
  "result": {
    "status": "done",
    "output": "Message sent successfully",
    "files": [],
    "reply_sent": true,
    "completed_at": "2026-04-05T10:30:45-03:00"
  }
}
```

## Relevant Configuration (config.yaml)

```yaml
channels:
  whatsapp:
    enabled: true
    method: "browser"
    check_interval: "5m"
    url: "https://web.whatsapp.com"
    session_mode: "per-peer"
    auto_reply: true
    read_receipts: false

  telegram:
    enabled: true
    method: "browser"
    check_interval: "5m"
    url: "https://web.telegram.org/k/"
    session_mode: "per-peer"

limits:
  message_delay_seconds: 3
  max_message_length: 4000
```

## Dependencies

- **Claude in Chrome** (MCP tools): `navigate`, `read_page`, `form_input`, `computer`, `get_page_text`
- **clawork-sessions**: To save history after sending
- **clawork-router**: Invokes messenger for sending
- **Filesystem**: To read/write ticket JSON files

## Implementation Notes

1. **WhatsApp Web requires a permanently open tab**. The heartbeat should verify the tab exists before attempting to read messages.

2. **Telegram Web is more stable** and selectors change less frequently.

3. **Connector-type channels (Slack, Gmail) do NOT use this skill**. They use Cowork's native MCP connectors.

4. **Every message send must be logged** in `~/claw/logs/messenger.jsonl` with: timestamp, channel, peer, message preview (first 100 chars), status.
