# clawork-router — Ticket Routing Engine

This skill reads tickets from the inbox, consults routing rules in `config.yaml`, and dispatches each ticket to the appropriate skill.

## Activation

This skill is invoked from the heartbeat (scheduled task) on each cycle. It is NOT invoked directly by the user.

## Execution Logic

### Step 1: Read Inbox

```
List all .json files in ~/claw/inbox/
Filter those with status: "pending"
Sort by: priority (critical > high > normal > low), then by created (oldest first)
Limit to max_tickets_per_heartbeat (default: 10)
```

### Step 2: Apply Routing for Each Ticket

Read `~/claw/config.yaml` → section `routing.rules`. For each rule, in order:

```
IF ticket.source.channel matches rule.match.channel (or channel is "*")
  AND (no rule.match.peer OR ticket.source.peer_id matches rule.match.peer)
  AND (no rule.match.group OR ticket.source.group matches rule.match.group)
  AND (no rule.match.content_contains OR ticket.instruction contains the text)
THEN:
  → Apply rule.action (skill, priority, context_file)
  → STOP (first matching rule wins)
```

If no rule matches → use `routing.default`.

### Step 3: Execute Skill

Once the target skill is determined:

1. If `ticket.routing.target_skill` is already set (explicit routing from the ticket), respect that value
2. If not, use the skill determined by the rules
3. Set `ticket.routing.target_skill` to the chosen skill
4. If the rule has `context_file`, read that file and add it as context
5. Invoke the corresponding skill with the ticket

### Step 4: Handle Result

After the skill processes the ticket:

- If `ticket.status == "done"` → move file from `inbox/` to `outbox/`
- If `ticket.status == "error"` → leave in inbox, increment retry_count
- If `ticket.status == "waiting_input"` → leave in inbox, wait for next cycle
- If a ticket has more than 3 retries → mark as "error" permanently and notify

### Step 5: Log

Write cycle summary to `~/claw/logs/router.jsonl`:

```json
{
  "ts": "2026-04-05T10:30:00-04:00",
  "tickets_routed": 3,
  "routes": [
    {"ticket_id": "ticket_001", "skill": "clawork-soul", "rule": "default"},
    {"ticket_id": "ticket_002", "skill": "crm-agent", "rule": "content_contains:order"},
    {"ticket_id": "ticket_003", "skill": "clawork-soul", "rule": "peer:+1555000100"}
  ]
}
```

## Advanced Routing Rules

### Content-based Routing

The `content_contains` field performs case-insensitive matching against `ticket.instruction`. Supports:
- Simple string: `"order"`
- Multiple keywords (OR): `"order|invoice|shipping"`

### Routing to External Orchestrator

If a rule has `action.skill: "external-orchestrator-bridge"`, the ticket is written to `~/claw/outbox/orchestrator/` instead of executing a local skill. The external orchestrator system picks it up.

### Conditional Routing

If the ticket has attachments (images, PDFs), the router can add additional instructions to context. For example: "The user sent an attached image, process it before responding."

## Available Skills for Routing

| Skill | When to Use |
|-------|----------|
| `clawork-soul` | Default — general conversational response |
| `clawork-messenger` | Send messages to browser channels |
| `clawork-sessions` | Manage history (invoked internally) |
| `crm-agent` | CRM queries and customer lookups |
| `inventory-agent` | Inventory status and order tracking |
| `external-orchestrator-bridge` | Communication with external orchestrator |
| `weather-skill` | Weather queries and forecasts |