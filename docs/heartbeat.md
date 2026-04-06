# Heartbeat Setup

The heartbeat is Clawork's execution loop. It runs as a Cowork Scheduled Task, waking the agent at regular intervals to process incoming messages and tickets.

## How It Works

```
┌─────────────────────────────────────────┐
│  Scheduled Task fires (every 15 min)    │
│  └─ Reads heartbeat-prompt.md           │
│     └─ Invokes clawork-router           │
│        ├─ check_channels (read new msgs)│
│        ├─ check_inbox (process tickets) │
│        └─ cleanup_old_tickets           │
└─────────────────────────────────────────┘
```

Each heartbeat cycle:

1. **check_channels** — The messenger skill reads new messages from browser-based channels (WhatsApp, Telegram) and creates tickets in `~/claw/inbox/`
2. **check_inbox** — The router reads pending tickets, applies routing rules, and dispatches to the appropriate skill
3. **cleanup_old_tickets** — Archives completed tickets older than 24 hours

## Setting Up in Cowork

### Step 1: Open Scheduled Tasks

Open the Claude Cowork desktop app and navigate to **Scheduled Tasks** in the sidebar.

### Step 2: Create a New Task

| Field | Value |
|-------|-------|
| **Name** | `Clawork Heartbeat` |
| **Frequency** | Every 15 minutes (recommended) |
| **Prompt** | Contents of `templates/heartbeat-prompt.md` |

### Step 3: Configure Frequency

Choose the interval that fits your needs:

| Interval | Use Case |
|----------|----------|
| `5m` | High-responsiveness — near real-time replies |
| `15m` | Balanced — good for most users |
| `30m` | Low priority — casual use |
| `1h` | Minimal — batch processing |

!!! tip
    Start with `15m` and adjust based on your message volume and responsiveness needs.

### Step 4: Enable the Task

Toggle the task to **enabled**. The first heartbeat will run at the next scheduled interval.

## Heartbeat Prompt Template

The heartbeat prompt (in `templates/heartbeat-prompt.md`) tells Cowork what to do on each cycle. It typically contains:

1. Load `config.yaml` from the Clawork directory
2. Run the router skill to check channels and process inbox
3. Handle errors gracefully
4. Log the cycle results

You can customize the prompt to add additional actions like:

- Checking external APIs
- Running maintenance tasks
- Sending daily summaries

## Configuration in config.yaml

```yaml
heartbeat:
  interval: "15m"
  actions:
    - check_inbox
    - check_channels
    - cleanup_old_tickets
```

### Available Actions

| Action | Description |
|--------|-------------|
| `check_inbox` | Process pending tickets in `~/claw/inbox/` |
| `check_channels` | Read new messages from browser-based channels |
| `cleanup_old_tickets` | Archive completed tickets older than 24h |

## Monitoring

Check heartbeat activity in the logs:

```bash
# View router log for recent cycles
tail -20 ~/claw/logs/router.jsonl

# Check for errors
grep '"error"' ~/claw/logs/router.jsonl

# View messenger activity
tail -20 ~/claw/logs/messenger.jsonl
```

## Troubleshooting

!!! warning "Heartbeat not firing"
    Verify the Scheduled Task is enabled in Cowork. Check the task history for errors.

!!! warning "Messages not being read"
    Ensure the browser tab for WhatsApp/Telegram is open and logged in. Run a `check_status` on the channel.

!!! warning "Tickets stuck in inbox"
    Check `~/claw/inbox/` for tickets with `status: "error"`. Review `retry_count` — tickets with more than 3 retries are permanently errored.
