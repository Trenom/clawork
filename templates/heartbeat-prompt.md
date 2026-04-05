# Clawork Heartbeat — Prompt for Scheduled Task

Run the Clawork heartbeat cycle. Follow these steps in order:

## 1. Read Configuration

Read `~/claw/config.yaml` to determine which channels are active and the routing rules.

## 2. Check Active Channels

For each channel with `enabled: true`:

- **WhatsApp** (`method: browser`): Invoke the `clawork-messenger` skill to read new messages from WhatsApp Web. For each new message, create a JSON ticket in `~/claw/inbox/`.
- **Telegram** (`method: browser`): Same as WhatsApp but on Telegram Web.
- **Slack** (`method: connector`): Use the Slack connector to read new messages.
- **Gmail** (`method: connector`): Use the Gmail connector to read new emails in the configured labels.

## 3. Process Inbox

Read all JSON files in `~/claw/inbox/` with `status: "pending"`. For each ticket:

1. Invoke the `clawork-router` skill with the ticket as input
2. The router decides which skill processes the ticket (based on config.yaml rules)
3. Update ticket status to "processing"
4. Execute the appropriate skill
5. Write the result to `ticket.result`
6. Send the response to the source channel (via `clawork-messenger` or connector)
7. Update status to "done" and move to `~/claw/outbox/`

## 4. Cleanup

Move tickets with status "done" that are older than 24h to `~/claw/outbox/archive/`.

## 5. Log

Write a cycle summary to `~/claw/logs/heartbeat.jsonl`:
```json
{"ts": "ISO-8601", "tickets_processed": N, "tickets_created": N, "errors": N, "channels_checked": ["whatsapp", "gmail"]}
```

## Limits

- Do not process more than 10 tickets per cycle (configurable in `limits.max_tickets_per_heartbeat`)
- Wait `limits.message_delay_seconds` between browser actions
- If a ticket fails, mark as "error" and continue with the next one
