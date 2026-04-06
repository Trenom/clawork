# Configuration Schema

Complete reference for every field in `config.yaml`.

## Basic Structure

```yaml
agent:
  name: "My Clawork Agent"
  soul: "./soul.md"
  language: "en"
  timezone: "America/New_York"

channels: { ... }
routing: { ... }
heartbeat: { ... }
external_orchestrator: { ... }
paths: { ... }
limits: { ... }
```

---

## Agent Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `agent.name` | String | Yes | `"Clawork Agent"` | Display name used in logs and notifications |
| `agent.soul` | String (path) | Yes | `./soul.md` | Path to the personality file (system prompt) |
| `agent.language` | String (ISO 639-1) | No | `"en"` | Primary language (`en`, `es`, `pt`, `fr`, etc.) |
| `agent.timezone` | String (IANA) | No | `"UTC"` | Timezone for timestamps and scheduling |

!!! warning
    If `agent.soul` points to a file that doesn't exist, Clawork uses a default personality. Always customize it.

---

## Channels Section

Each channel has its own configuration block under `channels`.

### WhatsApp

```yaml
channels:
  whatsapp:
    enabled: true
    method: "browser"           # "browser" | "adb" (experimental)
    check_interval: "5m"
    url: "https://web.whatsapp.com"
    allowed_peers: []            # Empty = all allowed
    blocked_peers: []            # Blacklist (takes priority)
    session_mode: "per-peer"     # per-peer | per-channel | shared
    auto_reply: true
    read_receipts: false
```

### Telegram

```yaml
channels:
  telegram:
    enabled: false
    method: "browser"
    check_interval: "5m"
    url: "https://web.telegram.org/k/"
    allowed_groups: []
    session_mode: "per-peer"
```

### Slack

```yaml
channels:
  slack:
    enabled: false
    method: "connector"          # Uses native Cowork connector
    check_interval: "on-event"   # Respond when message arrives
```

### Gmail

```yaml
channels:
  gmail:
    enabled: false
    method: "connector"
    check_interval: "15m"
    labels_to_watch:
      - "INBOX"
```

### Notion & Calendar

```yaml
channels:
  notion:
    enabled: false
    method: "connector"
    databases_to_watch: []

  calendar:
    enabled: false
    method: "connector"
    reminder_minutes: 15
```

### Channel Fields Reference

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | Boolean | Whether the channel is active |
| `method` | `"browser"` / `"connector"` / `"adb"` | How to interact with the channel |
| `check_interval` | String | Polling interval (`"5m"`, `"15m"`, `"on-event"`) |
| `allowed_peers` | Array | Whitelist of peer IDs. Empty = all |
| `blocked_peers` | Array | Blacklist of peer IDs (takes priority over allowed) |
| `session_mode` | `"per-peer"` / `"per-channel"` / `"shared"` | How conversation history is organized |
| `auto_reply` | Boolean | Whether to auto-respond to messages |

---

## Routing Section

```yaml
routing:
  rules:
    - match:
        channel: "*"              # "*" = any channel
        content_contains: "order"
      action:
        skill: "crm-skill"
        priority: "high"

    - match:
        channel: "whatsapp"
        peer: "+1555000100"
      action:
        skill: "clawork-soul"
        priority: "normal"
        context_file: "./contexts/vip.md"

  default:
    skill: "clawork-soul"
    priority: "normal"
```

### Rule Matching

Rules are evaluated in order. First match wins.

| Match Field | Type | Description |
|-------------|------|-------------|
| `channel` | String | Channel name or `"*"` for any |
| `peer` | String | Peer ID to match |
| `group` | String | Group name to match |
| `content_contains` | String | Case-insensitive text match. Supports OR with `\|` |

### Rule Actions

| Action Field | Type | Description |
|--------------|------|-------------|
| `skill` | String | Target skill to invoke |
| `priority` | String | `"critical"`, `"high"`, `"normal"`, `"low"` |
| `context_file` | String (path) | Additional context file to load |

---

## Heartbeat Section

```yaml
heartbeat:
  interval: "15m"                # 5m | 15m | 30m | 1h
  actions:
    - check_inbox
    - check_channels
    - cleanup_old_tickets
```

| Field | Type | Description |
|-------|------|-------------|
| `interval` | String | How often the heartbeat fires |
| `actions` | Array | Actions to perform each cycle |

Available actions:

- `check_inbox` — Process pending tickets
- `check_channels` — Read new messages from active channels
- `cleanup_old_tickets` — Archive done tickets older than 24h

See [Heartbeat Setup](heartbeat.md) for detailed instructions.

---

## External Orchestrator Section

```yaml
external_orchestrator:
  enabled: false
  api_url: "https://orchestrator.example.com/api"
  company_id: "your-company-id"
  agent_id: "your-agent-id"
  outbox_dir: "./outbox/orchestrator/"
```

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | Boolean | Enable bridge with external orchestrator |
| `api_url` | String | Orchestrator API endpoint |
| `company_id` | String | Company ID in the orchestrator |
| `agent_id` | String | Agent ID in the orchestrator |
| `outbox_dir` | String (path) | Directory for outbound orchestrator tickets |

---

## Paths Section

```yaml
paths:
  inbox: "./inbox/"
  outbox: "./outbox/"
  sessions: "./sessions/"
  memory: "./memory/"
  logs: "./logs/"
  contexts: "./contexts/"
```

All paths are relative to the Clawork base directory (`~/claw/` by default).

---

## Limits Section

```yaml
limits:
  max_tickets_per_heartbeat: 10
  session_context_lines: 50
  session_compact_threshold: 200
  message_delay_seconds: 3
  max_message_length: 4000
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_tickets_per_heartbeat` | Integer | 10 | Max tickets processed per cycle |
| `session_context_lines` | Integer | 50 | Lines of history included as context |
| `session_compact_threshold` | Integer | 200 | Compact session when it exceeds this |
| `message_delay_seconds` | Integer | 3 | Delay between browser actions (anti-bot) |
| `max_message_length` | Integer | 4000 | Truncate messages longer than this |
