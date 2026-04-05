# Clawork — Transform Claude Cowork into an Autonomous Personal Agent

**Run Claude natively as a multi-channel autonomous agent without third-party dependencies, ToS violations, or OAuth hacks.**

Clawork is a skills kit and configuration system that transforms Anthropic's Claude Cowork into a fully autonomous personal agent. It ports the proven architecture of [OpenClaw](https://github.com/nicobailey/openclaw) to Cowork's native ecosystem, using only official Anthropic primitives: scheduled tasks, skills, computer use, projects, and connectors.

Born in the Argentine tech ecosystem, Clawork demonstrates how to build sophisticated agentic systems within platform boundaries.

---

## The Problem: Why Clawork Exists

Anthropics restricted third-party use of Claude subscriptions through OAuth and external gateways, prohibiting tools like OpenClaw from using Claude tokens as an autonomous agent backend. This left users without a way to run Claude as a true multi-channel autonomous agent.

However, **Cowork already provides all necessary primitives natively**. Clawork bridges that gap.

### Primitives Mapping

| Primitive | OpenClaw | Cowork Equivalent | Status |
|-----------|----------|-------------------|--------|
| Agent loop | Custom runtime | Cowork runtime | Native |
| Heartbeat scheduler | Cron service | Scheduled Tasks | Native |
| Channels (WhatsApp, Slack, etc.) | Custom gateways | Connectors + Computer Use | Partial |
| Session persistence | File-based state | Projects + filesystem | Native |
| Routing engine | Rules system | Skills-based dispatch | Requires skill |
| System prompt (SOUL) | `soul.json` | Project instructions | Native |
| Memory | Hybrid (JSON + DB) | Files + memory primitives | Native |
| Tool ecosystem | Integrations | Computer Use + connectors | Native |

**Clawork implements only what's missing.** Everything else is native Cowork.

---

## What Clawork Does

- **Receives and responds** to messages from WhatsApp, Telegram, Slack, Gmail autonomously
- **Maintains conversation history** per person and per channel (persistent sessions)
- **Routes intelligently** with a configurable rules engine (content-based, peer-based, channel-based)
- **Runs continuously** via a heartbeat scheduler that checks inbox every N minutes
- **Respects your personality** through a customizable SOUL file
- **Scales vertically** — add skills, routing rules, integrations without changing core

**All configured through a single `config.yaml` file** compatible with OpenClaw's configuration format.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│           Cowork Project: Clawork                    │
│                                                     │
│  Heartbeat (Scheduled Task)                         │
│  └─ Every 15 minutes (configurable)                 │
│     └─ Check inbox for pending tickets              │
│                                                     │
│  Router (clawork-router skill)                      │
│  └─ Read ticket, consult config.yaml rules          │
│     ├─ Native channel (Slack, Gmail)?               │
│     │  └─ Use Cowork connector directly             │
│     ├─ Browser channel (WhatsApp, Telegram)?        │
│     │  └─ Use clawork-messenger (Computer Use)      │
│     ├─ Complex task?                                │
│     │  └─ Route to specialized skill                │
│     └─ Default?                                     │
│        └─ Route to clawork-soul (agent personality) │
│                                                     │
│  Soul (clawork-soul skill)                          │
│  └─ Load personality from soul.md                   │
│     └─ Load conversation history                    │
│        └─ Process and respond                       │
│           └─ Save interaction to session            │
│              └─ Send reply to origin channel        │
│                                                     │
│  Sessions (clawork-sessions skill)                  │
│  └─ Manage conversation history (JSONL format)     │
│     ├─ Read context for replies                     │
│     ├─ Append new interactions                      │
│     └─ Compact on overflow                          │
│                                                     │
│  Filesystem (Inbox/Outbox)                          │
│  └─ ~/claw/inbox/      ← pending tickets (JSON)    │
│     ~/claw/outbox/     ← completed tickets          │
│     ~/claw/sessions/   ← conversation history       │
│     ~/claw/config.yaml ← configuration              │
│     ~/claw/soul.md     ← agent personality          │
└─────────────────────────────────────────────────────┘
```

---

## Features

### Intelligent Routing
- **Content-based routing**: Send messages mentioning "order" to a specialized skill
- **Peer-based routing**: Route messages from specific people to custom handlers
- **Channel-based routing**: Different rules for WhatsApp, Slack, Gmail, Telegram
- **Group-based routing**: Handle group chats with their own context and rules
- **Priority queuing**: Process critical tickets first

### Multi-Channel Support
- **Slack**: Native connector integration
- **Gmail**: Native connector integration
- **WhatsApp Web**: Browser-based via Computer Use
- **Telegram Web**: Browser-based via Computer Use
- **Calendar, Notion**: Optional connector integrations
- **Filesystem**: Direct file-based operations
- **Dispatch**: Ad-hoc tasks from Claude mobile app

### Persistent Conversation Context
- **Per-peer sessions**: Each person gets their own conversation history
- **Per-channel sessions**: Separate histories for WhatsApp, Slack, Gmail, etc.
- **Automatic compaction**: Sessions are summarized on overflow to reduce context size
- **Configurable context window**: Control how many previous messages are included

### Flexible Configuration
- **Single config.yaml file**: All settings in one place
- **OpenClaw-compatible format**: Easy migration from existing setups
- **Automatic setup**: `setup.sh` creates full project structure
- **Channel-specific options**: Enable/disable channels, set check intervals, manage whitelists

### Developer-Friendly
- **Modular skills**: Each component is an independent skill
- **JSONL session format**: Human-readable conversation logs
- **JSON ticket format**: Standard format for all messages
- **Markdown SOUL**: System prompt is just a Markdown file
- **Inspection-friendly**: Use `cat` to read tickets, sessions, and logs

---

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/anthropic-labs/clawork.git
cd clawork
```

### 2. Run Setup
```bash
bash scripts/setup.sh
```

This creates the directory structure at `~/claw/` and copies example configuration files.

### 3. Edit Configuration
```bash
nano ~/claw/config.yaml
```

Configure which channels to enable, set routing rules, adjust heartbeat interval, and customize paths.

### 4. Customize Your Agent's Personality
```bash
nano ~/claw/soul.md
```

Define how your agent should behave, what tone to use, what information to keep private, and what priorities to follow. See `soul.example.md` for a template.

### 5. Set Up Communication Channels

**For WhatsApp Web:**
```bash
# Open Chrome and navigate to WhatsApp Web
open -a "Google Chrome" "https://web.whatsapp.com"
# Scan QR code to log in
# Keep this tab open — Clawork will control it
```

**For Telegram Web:**
```bash
# Open Chrome and navigate to Telegram Web
open -a "Google Chrome" "https://web.telegram.org/k/"
# Log in with your phone number
# Keep this tab open — Clawork will control it
```

**For Slack/Gmail:**
- Already configured if you're logged into Claude Cowork
- Clawork will use native connectors

### 6. Configure Heartbeat in Cowork

1. Open Claude Cowork desktop app
2. Navigate to Scheduled Tasks
3. Create a new task:
   - **Name**: "Clawork Heartbeat"
   - **Frequency**: Every 15 minutes (or your preference)
   - **Prompt**: Copy the contents of `templates/heartbeat-prompt.md`

4. Enable the task

### 7. Test It

Send a message to one of your configured channels. It should appear in `~/claw/inbox/` within seconds of the next heartbeat. Your agent will process it and send a reply.

---

## Ticket Protocol Specification

All messages in Clawork flow through a standard ticket format (JSON):

```json
{
  "id": "ticket_20260405_001",
  "status": "pending",
  "created": "2026-04-05T10:30:00-03:00",
  "updated": null,

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

### Ticket Lifecycle

```
pending          → processing         → done
                                        (or) error
                                        (or) waiting_input
```

**Status values:**
- `pending`: Waiting to be processed
- `processing`: Currently being handled by a skill
- `done`: Completed successfully, reply sent
- `error`: Failed processing, will retry or be archived
- `waiting_input`: Paused, waiting for user input or external data

---

## Configuration Reference

### Basic Structure

```yaml
agent:
  name: "My Clawork Agent"
  soul: "./soul.md"                    # Path to personality file
  language: "en"                       # Language (en, es, pt, etc.)
  timezone: "America/New_York"

channels:
  whatsapp:
    enabled: true
    method: "browser"                  # browser | adb (experimental)
    check_interval: "5m"
    allowed_peers: []                  # Empty = all peers allowed
    blocked_peers: []                  # Blacklist (takes priority)
    session_mode: "per-peer"           # per-peer | per-channel | shared
    auto_reply: true
    read_receipts: false

  slack:
    enabled: false
    method: "connector"                # Native Cowork connector
    check_interval: "on-event"         # Respond immediately

  gmail:
    enabled: false
    method: "connector"
    check_interval: "15m"
    labels_to_watch:
      - "INBOX"

routing:
  rules:
    # Route messages mentioning orders to crm-skill
    - match:
        channel: "*"
        content_contains: "order"
      action:
        skill: "crm-skill"
        priority: "high"

    # Route messages from specific peer to soul
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
  interval: "15m"                      # 5m | 15m | 30m | 1h
  actions:
    - check_inbox
    - check_channels
    - cleanup_old_tickets

limits:
  max_tickets_per_heartbeat: 10        # Process max 10 tickets per cycle
  session_context_lines: 50            # How many previous messages to include
  session_compact_threshold: 200       # Compact session when it exceeds this
  message_delay_seconds: 3             # Anti-bot delay between actions
  max_message_length: 4000             # Truncate longer messages
```

See `docs/config-reference.md` for complete field documentation.

---

## Skill Ecosystem

### Core Skills

| Skill | Purpose | Phase |
|-------|---------|-------|
| `clawork-soul` | Agent personality and response generation | Phase 1 |
| `clawork-router` | Ticket routing and dispatch | Phase 1 |
| `clawork-sessions` | Conversation history management | Phase 1 |
| `clawork-messenger` | WhatsApp Web / Telegram Web integration | Phase 2 |

### Integration Points

Clawork integrates seamlessly with other skills:
- Custom business logic skills
- Data retrieval skills (databases, APIs)
- File processing skills
- System administration skills

Configure which skills to route to in `config.yaml` routing rules.

---

## Migrating from OpenClaw

If you're already running OpenClaw, migration is straightforward:

### Step 1: Copy Your SOUL
```bash
# If you have a separate soul.md file
cp ~/.openclaw/soul.md ~/claw/soul.md

# If your SOUL is in openclaw.json
jq -r '.agents[0].systemPrompt' ~/.openclaw/openclaw.json > ~/claw/soul.md
```

### Step 2: Migrate Configuration
```bash
bash scripts/import-openclaw-config.sh
```

This reads `~/.openclaw/openclaw.json` and generates a compatible `config.yaml`. Review and adjust as needed.

### Step 3: Optional — Migrate Conversation History
```bash
bash scripts/import-openclaw-sessions.sh
```

This imports your existing conversation sessions into Clawork's JSONL format.

### What's Preserved

- Your agent's personality (SOUL) — zero changes required
- Channel configuration (WhatsApp, Telegram, Slack, Gmail)
- Routing rules and priorities
- Conversation history (if migrated)
- Timezone and language settings

### What's New

- Native Cowork scheduler (no external cron needed)
- Official Anthropic connectors (no OAuth workarounds)
- Computer Use for browser automation (instead of Puppeteer)
- Cowork Projects for memory and persistence

---

## Roadmap

### Phase 1: Core Engine (Weeks 1-2)
- [x] Skill: `clawork-soul` — personality and response generation
- [x] Skill: `clawork-router` — intelligent ticket routing
- [x] Skill: `clawork-sessions` — persistent conversation history
- [x] Ticket protocol specification
- [x] Configuration system
- [x] Setup automation script
- [x] OpenClaw migration tools
- [x] Documentation

**Status**: Production ready

### Phase 2: Messaging Tier (Weeks 3-4)
- [ ] Skill: `clawork-messenger` — WhatsApp Web automation
- [ ] Skill: `clawork-messenger` — Telegram Web automation
- [ ] Error handling (session loss, rate limits, network issues)
- [ ] Message normalization (text, images, documents)
- [ ] Reply threading
- [ ] Troubleshooting guide

**Status**: In development

### Phase 3: Robustness & Scale (Weeks 5-6)
- [ ] Session compaction (summarize on overflow)
- [ ] Multi-agent coordination
- [ ] Integration with user skills
- [ ] Session history migration tool
- [ ] End-to-end test suite
- [ ] Performance benchmarks

**Status**: Planned

### Phase 4: Advanced Capabilities (Weeks 7+)
- [ ] ADB Gateway — Android app automation (experimental)
- [ ] Cloud scheduling (heartbeat without local desktop)
- [ ] A2A protocol — agent-to-agent communication
- [ ] Web interface for management
- [ ] Analytics and logging dashboard

**Status**: Experimental / optional modules

---

## Project Structure

```
clawork/
├── README.md                          ← You are here
├── LICENSE                            ← MIT
├── CONTRIBUTING.md
├── CHANGELOG.md
│
├── docs/
│   ├── architecture.md                ← System design and data flow
│   ├── config-reference.md            ← Complete config.yaml documentation
│   ├── ticket-protocol.md             ← Ticket format specification
│   ├── migration.md                   ← Migration from OpenClaw
│   ├── setup-guide.md                 ← Step-by-step setup with details
│   └── troubleshooting.md             ← Common issues and solutions
│
├── skills/
│   ├── clawork-soul/
│   │   ├── SKILL.md                   ← Skill definition
│   │   └── soul.example.md            ← Example personality file
│   │
│   ├── clawork-router/
│   │   └── SKILL.md                   ← Routing engine skill
│   │
│   ├── clawork-sessions/
│   │   └── SKILL.md                   ← Session management skill
│   │
│   └── clawork-messenger/             (Phase 2)
│       ├── SKILL.md
│       ├── whatsapp-web.md
│       └── telegram-web.md
│
├── config/
│   └── config.example.yaml            ← Example configuration
│
├── scripts/
│   ├── setup.sh                       ← Initial setup
│   ├── import-openclaw-config.sh
│   └── import-openclaw-sessions.sh
│
├── templates/
│   ├── ticket.example.json
│   ├── session.example.jsonl
│   └── heartbeat-prompt.md            ← Prompt for scheduled task
│
└── tests/
    └── test-scenarios.md              ← Manual test cases
```

---

## Getting Help

### Documentation
- **Architecture**: See `docs/architecture.md` for system design details
- **Configuration**: See `docs/config-reference.md` for all config options
- **Troubleshooting**: See `docs/troubleshooting.md` for common issues
- **Migration**: See `docs/migration.md` if coming from OpenClaw

### Community
- **Issues**: GitHub issues for bugs and feature requests
- **Discussions**: GitHub discussions for general questions
- **Contributing**: See `CONTRIBUTING.md` to contribute

---

## Design Philosophy

Clawork adheres to these principles:

1. **No external dependencies** — Use only native Cowork primitives
2. **Configuration over code** — Everything configurable via YAML
3. **The SOUL is sacred** — Respect your agent's personality
4. **Fail gracefully** — Errors create tickets, not silent failures
5. **Local-first** — Filesystem as the bus, not cloud services
6. **Human-readable** — Inspect everything with standard tools
7. **Portable** — Run anywhere Cowork runs

---

## License

MIT License — See LICENSE file for details.

Copyright (c) 2026 Clawork Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

---

## Acknowledgments

Clawork is built on the proven architecture of [OpenClaw](https://github.com/nicobailey/openclaw) by Nico Bailey. It reimplements core concepts using Anthropic's native Cowork platform to demonstrate how sophisticated agentic systems can be built within platform boundaries.

The project originated in the Argentine tech ecosystem, built by teams working on document management and workflow automation.

Developed with support from the Anthropic Cowork community.

---

**Ready to get started?** See [Quick Start](#quick-start) above or read `docs/setup-guide.md` for detailed instructions.

**Coming from OpenClaw?** See `docs/migration.md` for step-by-step migration.

**Want to contribute?** See `CONTRIBUTING.md`.