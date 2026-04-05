# Clawork Heartbeat — Scheduled Task Prompt

This is the prompt template for the Clawork heartbeat scheduled task.
Configure it as a recurring task in your Cowork environment.

## Recommended Schedule

- Every 15 minutes for active use
- Every 30 minutes for low-traffic periods
- Every 5 minutes for high-priority monitoring

## Prompt

```
You are Clawork's heartbeat — the autonomous loop that keeps the personal agent running.

Every cycle:

1. Check ~/claw/inbox/ for pending tickets (status: "pending")
2. Sort by priority: critical > high > normal > low
3. For each ticket (up to 10 per cycle):
   a. Apply routing rules from ~/claw/config.yaml
   b. Dispatch to the matched skill (or default clawork-soul)
   c. Save the interaction to ~/claw/sessions/{channel}/{peer_id}.jsonl
   d. Move completed ticket from inbox/ to outbox/
4. Log the heartbeat to ~/claw/logs/heartbeat.jsonl
5. Clean up outbox tickets older than 7 days

If the inbox is empty, just log the heartbeat and exit.
Never process more than 10 tickets in one cycle.
Always process critical/high priority tickets first.
```

## Setup with Cowork Scheduled Tasks

Use the `/schedule` command in Cowork to create the task:

- **Task ID**: `clawork-heartbeat`
- **Schedule**: `*/15 * * * *` (every 15 minutes)
- **Prompt**: Copy the prompt above

## First Run

After creating the scheduled task, click "Run now" to:
1. Verify the task works correctly
2. Pre-approve any tool permissions it needs
3. Check that logs are being written
