# Clawork Configuration Reference

Complete reference for every field in `config.yaml`.

---

## Table of Contents

1. [Agent Section](#agent-section)
2. [Channels Section](#channels-section)
3. [Routing Section](#routing-section)
4. [Heartbeat Section](#heartbeat-section)
5. [Paths Section](#paths-section)
6. [Limits Section](#limits-section)
7. [Examples](#examples)

---

## Agent Section

Top-level configuration about the agent itself.

```yaml
agent:
  name: "My Clawork Agent"
  soul: "./soul.md"
  language: "en"
  timezone: "America/New_York"
```

### `agent.name`
**Type**: String
**Required**: Yes
**Default**: "Clawork Agent"
**Description**: Display name of your agent. Used in logs and notifications.
**Example**: `"Alice's Personal Assistant"`, `"Company AI Agent"`

### `agent.soul`
**Type**: String (path)
**Required**: Yes
**Default**: `./soul.md`
**Description**: Path to your agent's personality file (system prompt). Can be absolute or relative to `config.yaml` location.
**Example**: `"./soul.md"`, `"/home/user/clawork/soul.md"`, `"~/claw/soul.md"`

**Important**: If this file doesn't exist, Clawork uses a default personality. Always customize it to match your needs.

### `agent.language`
**Type**: String (ISO 639-1 code)
**Required**: No
**Default**: `"en"`
**Description**: Primary language for the agent. Used for tone, phrasing, and response generation.
**Supported**: `"en"` (English), `"es"` (Spanish), `"pt"` (Portuguese), `"fr"` (French), and others supported by Claude
**Example**: `"es"`, `"en"`, `"pt-br"`

### `agent.timezone`
**Type**: String (IANA timezone)
**Required**: No
**Default**: `"UTC"`
**Description**: Timezone for timestamps in logs and tickets. Affects heartbeat scheduling.
**Format**: IANA timezone database names
**Example**: `"America/New_York"`, `"America/Los_Angeles"`, `"Europe/London"`
**Common values**:
- US: `"America/New_York"`, `"America/Los_Angeles"`, `"America/Chicago"`
- Europe: `"Europe/London"`, `"Europe/Paris"`, `"Europe/Berlin"`
- UTC: `"UTC"`

---

## Channels Section

Configuration for each communication channel Clawork can use.

```yaml
channels:
  whatsapp:
    enabled: true
    method: "browser"
    check_interval: "5m"
    url: "https://web.whatsapp.com"
    allowed_peers: []
    blocked_peers: []
    session_mode: "per-peer"
    auto_reply: true
    read_receipts: false

  telegram:
    enabled: false
    method: "browser"
    check_interval: "5m"
    url: "https://web.telegram.org/k/"
    allowed_groups: []
    session_mode: "per-peer"

  slack:
    enabled: false
    method: "connector"
    check_interval: "on-event"

  gmail:
    enabled: false
    method: "connector"
    check_interval: "15m"
    labels_to_watch:
      - "INBOX"

  calendar:
    enabled: false
    method: "connector"
    reminder_minutes: 15

  notion:
    enabled: false
    method: "connector"
    databases_to_watch: []
```

### Universal Fields (all channels)

#### `channels.{name}.enabled`
**Type**: Boolean
**Required**: No
**Default**: `false`
**Description**: Whether this channel is active. Disabled channels are skipped during heartbeat.
**Example**: `true`, `false`

#### `channels.{name}.method`
**Type**: String
**Required**: Yes if enabled
**Options**:
- `"browser"` — Control via Computer Use (WhatsApp Web, Telegram Web)
- `"connector"` — Use Cowork's native connector (Slack, Gmail, etc.)
- `"adb"` — Android Device Bridge (experimental, requires emulator)

#### `channels.{name}.check_interval`
**Type**: String
**Required**: No
**Default**: `"15m"`
**Description**: How often to check this channel for new messages.
**Options**: `"5m"`, `"15m"`, `"30m"`, `"1h"`, `"on-event"` (for connectors)
**Important**: More frequent checks use more resources. Balance freshness with efficiency.

### WhatsApp Configuration

#### `channels.whatsapp.url`
**Type**: String
**Required**: No
**Default**: `"https://web.whatsapp.com"`
**Description**: URL of WhatsApp Web. Usually doesn't change.

#### `channels.whatsapp.allowed_peers`
**Type**: Array of strings
**Required**: No
**Default**: `[]` (all peers allowed)
**Description**: Whitelist of phone numbers to respond to. Format: `+{country_code}{number}`
**Example**: `["+1555000100", "+1555000111"]`
**Behavior**: If empty, all peers are allowed. If populated, ONLY these peers' messages are processed.

#### `channels.whatsapp.blocked_peers`
**Type**: Array of strings
**Required**: No
**Default**: `[]`
**Description**: Blacklist of phone numbers to ignore. Takes priority over `allowed_peers`.
**Example**: `["+1555999999"]`
**Behavior**: Messages from these peers are never processed.

#### `channels.whatsapp.session_mode`
**Type**: String
**Required**: No
**Default**: `"per-peer"`
**Options**:
- `"per-peer"` — Separate conversation history for each contact
- `"per-channel"` — All WhatsApp conversations share one history
- `"shared"` — All channels and peers share one history (not recommended)

**Recommendation**: Use `"per-peer"` to keep conversations private.

#### `channels.whatsapp.auto_reply`
**Type**: Boolean
**Required**: No
**Default**: `true`
**Description**: Whether to automatically reply to messages. If false, you must reply via another method.

#### `channels.whatsapp.read_receipts`
**Type**: Boolean
**Required**: No
**Default**: `false`
**Description**: Whether to mark messages as read in WhatsApp after processing. If false, messages stay unread (allowing your agent to handle them without notification spam).

### Telegram Configuration

#### `channels.telegram.url`
**Type**: String
**Required**: No
**Default**: `"https://web.telegram.org/k/"`
**Description**: URL of Telegram Web. The `/k/` suffix indicates the newer "K" version (more stable than A).

#### `channels.telegram.allowed_groups`
**Type**: Array of strings
**Required**: No
**Default**: `[]`
**Description**: Whitelist of group names. If empty, all groups are processed.
**Example**: `["dev-team", "family"]`

#### `channels.telegram.session_mode`
**Type**: String
**Options**: `"per-peer"`, `"per-channel"`, `"shared"`
**Recommendation**: `"per-peer"`

### Slack Configuration

#### `channels.slack.check_interval`
**Type**: String
**Recommended**: `"on-event"`
**Description**: Slack connector delivers messages in real-time, so polling is unnecessary. Set to `"on-event"` for immediate delivery.

### Gmail Configuration

#### `channels.gmail.labels_to_watch`
**Type**: Array of strings
**Required**: No
**Default**: `["INBOX"]`
**Description**: Gmail labels to check for new emails.
**Examples**:
- `["INBOX"]` — Only new emails
- `["INBOX", "Urgent"]` — Inbox and custom "Urgent" label
- `["INBOX", "Work"]` — Inbox and work emails

**Note**: Gmail allows creating custom labels. Use these to organize which emails your agent handles.

### Calendar Configuration

#### `channels.calendar.reminder_minutes`
**Type**: Number
**Required**: No
**Default**: `15`
**Description**: How many minutes before an event to send a reminder.
**Example**: `15`, `30`, `60`

### Notion Configuration

#### `channels.notion.databases_to_watch`
**Type**: Array of strings
**Required**: No
**Default**: `[]`
**Description**: Notion database IDs to monitor for updates.
**Example**: `["abc123def456", "xyz789"]`

---

## Routing Section

Configuration for message routing logic.

```yaml
routing:
  rules:
    - match:
        channel: "whatsapp"
        peer: "+1555000100"
      action:
        skill: "clawork-soul"
        priority: "high"
        context_file: "./contexts/vip.md"

  default:
    skill: "clawork-soul"
    priority: "normal"
```

### Routing Rules

Rules are evaluated in order. The first matching rule wins. Use specificity to control precedence.

#### `routing.rules[].match` (all conditions are AND-ed)

##### `match.channel`
**Type**: String
**Required**: No (omit for any channel)
**Default**: `"*"` (any channel)
**Options**: `"whatsapp"`, `"telegram"`, `"slack"`, `"gmail"`, `"*"`
**Description**: Which channel this rule applies to.
**Example**: `"whatsapp"` matches only WhatsApp messages

##### `match.peer`
**Type**: String
**Required**: No
**Description**: Specific peer ID (phone number, email, username).
**Format**:
- WhatsApp: `"+1555000100"` (with country code)
- Telegram: `"user_123456"` or `"@username"`
- Gmail: `"sender@example.com"`
- Slack: `"@username"` or `"U12345"`

**Example**: `"+1555000100"` matches only this contact

##### `match.group`
**Type**: String
**Required**: No
**Description**: Specific group name (for group chats).
**Example**: `"dev-team"`, `"family"`

##### `match.content_contains`
**Type**: String or String array
**Required**: No
**Description**: Text to search for in the message.
**Behavior**:
- Case-insensitive
- Substring match (not whole word)
- Multiple keywords separated by `|` means OR

**Examples**:
- `"order"` — matches "Check my order" or "ORDER STATUS"
- `"urgent|ASAP|high-priority"` — matches any of these three

#### `routing.rules[].action`

##### `action.skill`
**Type**: String
**Required**: Yes
**Description**: Which skill to invoke to handle this ticket.
**Built-in skills**:
- `"clawork-soul"` — Default agent personality
- `"clawork-router"` — Routing engine (don't invoke directly)
- `"clawork-sessions"` — Session management (don't invoke directly)
- `"clawork-messenger"` — Send messages (invoked by soul)

**Custom skills**: Any skill name you've defined in your Cowork project.

##### `action.priority`
**Type**: String
**Required**: No
**Default**: `"normal"`
**Options**: `"critical"`, `"high"`, `"normal"`, `"low"`
**Description**: Priority for this ticket in the processing queue. Higher priority tickets are processed first.

##### `action.context_file`
**Type**: String (path)
**Required**: No
**Description**: Additional context file to load for this ticket.
**Example**: `"./contexts/vip.md"`, `"~/claw/contexts/team.md"`
**Use case**: Load special instructions for specific peers or groups.

### Default Routing

#### `routing.default`
**Type**: Object
**Required**: Yes
**Description**: What to do if no rules match.

**Common pattern**:
```yaml
routing:
  default:
    skill: "clawork-soul"
    priority: "normal"
```

This sends unmatched messages to your agent's personality.

---

## Heartbeat Section

Configuration for the scheduled task that drives Clawork.

```yaml
heartbeat:
  interval: "15m"
  actions:
    - check_inbox
    - check_channels
    - cleanup_old_tickets
```

### `heartbeat.interval`
**Type**: String
**Required**: No
**Default**: `"15m"`
**Options**: `"5m"`, `"15m"`, `"30m"`, `"1h"`
**Description**: How often the heartbeat runs.
**Trade-off**: Shorter intervals → faster response, more resource usage. Longer intervals → slower response, less load.

### `heartbeat.actions`
**Type**: Array of strings
**Required**: No
**Default**: `["check_inbox", "check_channels", "cleanup_old_tickets"]`
**Description**: What the heartbeat does each cycle.

**Available actions**:
- `"check_channels"` — Read new messages from enabled channels
- `"check_inbox"` — Process pending tickets with router
- `"cleanup_old_tickets"` — Archive completed tickets older than 24h
- `"compact_sessions"` — Manually trigger session compaction (optional)

---

## Paths Section

Configuration for where Clawork stores files.

```yaml
paths:
  inbox: "./inbox/"
  outbox: "./outbox/"
  sessions: "./sessions/"
  memory: "./memory/"
  logs: "./logs/"
  contexts: "./contexts/"
```

### `paths.inbox`
**Type**: String (directory path)
**Required**: No
**Default**: `"./inbox/"`
**Description**: Where incoming tickets are created.
**Note**: Change this only if you want tickets in a different location. Standard setup uses `~/claw/inbox/`.

### `paths.outbox`
**Type**: String (directory path)
**Required**: No
**Default**: `"./outbox/"`
**Description**: Where completed tickets are moved.

### `paths.sessions`
**Type**: String (directory path)
**Required**: No
**Default**: `"./sessions/"`
**Description**: Where conversation history is stored.

### `paths.memory`
**Type**: String (directory path)
**Required**: No
**Default**: `"./memory/"`
**Description**: Where long-term memory is stored (currently unused, reserved for future).

### `paths.logs`
**Type**: String (directory path)
**Required**: No
**Default**: `"./logs/"`
**Description**: Where activity logs are written.

### `paths.contexts`
**Type**: String (directory path)
**Required**: No
**Default**: `"./contexts/"`
**Description**: Where context files (referenced in routing rules) are stored.

---

## Limits Section

Configuration for resource and behavior limits.

```yaml
limits:
  max_tickets_per_heartbeat: 10
  session_context_lines: 50
  session_compact_threshold: 200
  message_delay_seconds: 3
  max_message_length: 4000
```

### `limits.max_tickets_per_heartbeat`
**Type**: Number
**Required**: No
**Default**: `10`
**Description**: Maximum number of tickets to process per heartbeat cycle.
**Rationale**: Prevents overwhelming a single heartbeat cycle. Remaining tickets wait for next cycle.
**Recommendation**: Keep at 10 for balanced processing.

### `limits.session_context_lines`
**Type**: Number
**Required**: No
**Default**: `50`
**Description**: How many previous messages to include in conversation context.
**Effect on tokens**: 50 lines ≈ 1-2k tokens typically. Increase for longer context, decrease to save tokens.
**Recommendation**: 50 is a good balance. Adjust based on your conversation complexity.

### `limits.session_compact_threshold`
**Type**: Number
**Required**: No
**Default**: `200`
**Description**: Compact a session file when it exceeds this many lines.
**Process**: Old messages are summarized, recent messages kept.
**Recommendation**: 200 lines = ~10-20 KB file. Adjust based on your storage/performance preferences.

### `limits.message_delay_seconds`
**Type**: Number
**Required**: No
**Default**: `3`
**Description**: Delay (in seconds) between actions when automating browser (WhatsApp Web, Telegram Web).
**Purpose**: Anti-bot measure. Too fast = WhatsApp/Telegram may detect automation and block.
**Recommendation**: Minimum 3 seconds. If you get "suspicious activity" warnings, increase to 5.

### `limits.max_message_length`
**Type**: Number
**Required**: No
**Default**: `4000`
**Description**: Maximum message length (in characters). Longer messages are truncated.
**Rationale**: WhatsApp and Telegram have message length limits.
**Recommendation**: 4000 is safe for all platforms.

---

## Examples

### Example 1: Basic Single-User Setup

```yaml
agent:
  name: "My Personal Agent"
  soul: "./soul.md"
  language: "en"
  timezone: "America/New_York"

channels:
  whatsapp:
    enabled: true
    method: "browser"
    check_interval: "5m"

routing:
  default:
    skill: "clawork-soul"
    priority: "normal"

heartbeat:
  interval: "5m"

paths:
  inbox: "./inbox/"
  outbox: "./outbox/"
  sessions: "./sessions/"
  logs: "./logs/"
  contexts: "./contexts/"

limits:
  max_tickets_per_heartbeat: 10
  session_context_lines: 50
```

**What this does**: Checks WhatsApp every 5 minutes, replies via agent personality.

### Example 2: Multi-Channel with Routing

```yaml
agent:
  name: "Company AI Agent"
  soul: "./soul.md"
  language: "en"
  timezone: "America/New_York"

channels:
  whatsapp:
    enabled: true
    method: "browser"
    check_interval: "5m"
    allowed_peers:
      - "+1555000100"
      - "+1555000111"

  slack:
    enabled: true
    method: "connector"
    check_interval: "on-event"

  gmail:
    enabled: true
    method: "connector"
    check_interval: "15m"
    labels_to_watch:
      - "INBOX"

routing:
  rules:
    - match:
        channel: "whatsapp"
        peer: "+1555000100"
      action:
        skill: "clawork-soul"
        priority: "high"

    - match:
        channel: "*"
        content_contains: "order|tracking"
      action:
        skill: "order-agent"
        priority: "normal"

    - match:
        channel: "slack"
        content_contains: "urgent|ASAP"
      action:
        skill: "clawork-soul"
        priority: "critical"

  default:
    skill: "clawork-soul"
    priority: "normal"

heartbeat:
  interval: "15m"

limits:
  max_tickets_per_heartbeat: 15
  session_context_lines: 50
```

**What this does**:
- Handles WhatsApp (only 2 specific people), Slack, and Gmail
- Routes "order" or "tracking" mentions to a specialized skill
- Gives VIP person high priority
- Treats urgent Slack messages as critical

### Example 3: Basic Multi-Channel Setup

```yaml
agent:
  name: "Multi-Channel Agent"
  soul: "./soul.md"
  language: "en"
  timezone: "America/New_York"

channels:
  whatsapp:
    enabled: true
    method: "browser"
    check_interval: "5m"
    allowed_peers: ["+1555000100"]
    session_mode: "per-peer"

  telegram:
    enabled: true
    method: "browser"
    check_interval: "5m"
    session_mode: "per-peer"

  slack:
    enabled: true
    method: "connector"
    check_interval: "on-event"

routing:
  rules:
    - match:
        channel: "whatsapp"
        peer: "+1555000100"
      action:
        skill: "clawork-soul"
        priority: "normal"

  default:
    skill: "clawork-soul"
    priority: "normal"

heartbeat:
  interval: "15m"
  actions:
    - check_inbox
    - check_channels
    - cleanup_old_tickets

paths:
  inbox: "./inbox/"
  outbox: "./outbox/"
  sessions: "./sessions/"
  memory: "./memory/"
  logs: "./logs/"
  contexts: "./contexts/"

limits:
  max_tickets_per_heartbeat: 10
  session_context_lines: 50
  session_compact_threshold: 200
  message_delay_seconds: 3
  max_message_length: 4000
```

---

## Tips & Best Practices

### Performance Tuning

1. **Heartbeat interval**:
   - Real-time chat: 5m
   - Background processing: 15-30m
   - Large inbox: 30-60m

2. **Session context**:
   - Short conversations: 30 lines
   - Medium conversations: 50 lines
   - Long/complex conversations: 100 lines

3. **Max tickets per heartbeat**:
   - Light load: 10
   - Heavy load: 20-30
   - Very heavy load: 50+ (monitor resource usage)

### Security

1. **Always specify `allowed_peers` for sensitive channels**
   - Don't leave it empty unless necessary

2. **Use `blocked_peers` for spam/test numbers**
   - Prevents accidental responses

3. **Keep `soul.md` private**
   - chmod 600 (user-only read/write)

4. **Rotate `max_message_length` if you see truncation issues**
   - But balance with platform limits

### Debugging

1. **Check logs**:
   ```bash
   tail -f ~/claw/logs/heartbeat.jsonl
   ```

2. **Inspect a ticket**:
   ```bash
   cat ~/claw/inbox/ticket_001.json | jq .
   ```

3. **View routing decisions**:
   ```bash
   cat ~/claw/logs/router.jsonl | jq '.'
   ```

4. **Test a config change**:
   - Edit config.yaml
   - Wait for next heartbeat
   - Check logs for impact

### Common Configurations

**"Just reply to WhatsApp" (simplest)**:
```yaml
channels:
  whatsapp:
    enabled: true
    method: "browser"
heartbeat:
  interval: "5m"
routing:
  default:
    skill: "clawork-soul"
```

**"Professional multi-channel"**:
- Enable: Slack, Gmail, WhatsApp
- Different routing for work vs. personal
- High priority for critical messages

**"Expert power user"**:
- Custom skills for specialized tasks
- Multiple routing rules with context files
- Frequent heartbeat (5m)
- Large context window (100+ lines)

---

## Validation

Before deploying a config change:

1. **Check YAML syntax**:
   ```bash
   python3 -m yaml ~/claw/config.yaml
   ```

2. **Verify paths exist**:
   ```bash
   ls -la ~/claw/inbox ~/claw/outbox ~/claw/sessions
   ```

3. **Test with a manual heartbeat**:
   - Trigger the heartbeat task
   - Check `~/claw/logs/heartbeat.jsonl`
   - Verify no errors

4. **Send a test message**:
   - Send a message via one of your enabled channels
   - Verify it appears in inbox within the check_interval
   - Verify response is received

---

This reference covers every configuration option in Clawork. For more context on specific features, see the main documentation in `docs/`.