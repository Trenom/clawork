# Quick Start

Get Clawork running in 5 minutes.

## 1. Clone the Repository

```bash
git clone https://github.com/Trenom/clawork.git
cd clawork
```

## 2. Run Setup

```bash
bash scripts/setup.sh
```

This creates the directory structure at `~/claw/` and copies example configuration files:

```
~/claw/
├── inbox/          ← pending tickets (JSON)
├── outbox/         ← completed tickets
├── sessions/       ← conversation history
├── memory/         ← persistent memory
├── logs/           ← runtime logs
├── contexts/       ← additional context files
├── config.yaml     ← configuration
└── soul.md         ← agent personality
```

## 3. Edit Configuration

```bash
nano ~/claw/config.yaml
```

Configure which channels to enable, set routing rules, adjust heartbeat interval, and customize paths. See the [Configuration Schema](config-schema.md) for all available options.

## 4. Customize Your Agent's Personality

```bash
nano ~/claw/soul.md
```

Define how your agent should behave, what tone to use, what information to keep private, and what priorities to follow. See `skills/clawork-soul/soul.example.md` for a template.

## 5. Set Up Communication Channels

=== "WhatsApp Web"

    ```bash
    # Open Chrome and navigate to WhatsApp Web
    open -a "Google Chrome" "https://web.whatsapp.com"
    # Scan QR code to log in
    # Keep this tab open — Clawork will control it
    ```

=== "Telegram Web"

    ```bash
    # Open Chrome and navigate to Telegram Web
    open -a "Google Chrome" "https://web.telegram.org/k/"
    # Log in with your phone number
    # Keep this tab open — Clawork will control it
    ```

=== "Slack / Gmail"

    Already configured if you're logged into Claude Cowork. Clawork uses native connectors — no extra setup needed.

## 6. Configure Heartbeat in Cowork

1. Open Claude Cowork desktop app
2. Navigate to **Scheduled Tasks**
3. Create a new task:
    - **Name**: `Clawork Heartbeat`
    - **Frequency**: Every 15 minutes (or your preference)
    - **Prompt**: Copy the contents of `templates/heartbeat-prompt.md`
4. Enable the task

See [Heartbeat Setup](heartbeat.md) for detailed configuration options.

## 7. Test It

Send a message to one of your configured channels. It should appear in `~/claw/inbox/` within seconds of the next heartbeat. Your agent will process it and send a reply.

!!! tip "Verify the flow"
    Check `~/claw/logs/router.jsonl` to see routing decisions and `~/claw/sessions/` for conversation history.

## Project Structure

```
clawork/
├── README.md
├── LICENSE (MIT)
├── CONTRIBUTING.md
├── CHANGELOG.md
├── docs/                    ← Documentation (this site)
├── skills/
│   ├── clawork-soul/        ← Agent personality
│   ├── clawork-router/      ← Ticket routing engine
│   ├── clawork-sessions/    ← Session history management
│   └── clawork-messenger/   ← Browser-based messaging
├── config/
│   └── config.example.yaml  ← Example configuration
├── scripts/
│   ├── setup.sh
│   ├── import-openclaw-config.sh
│   └── import-openclaw-sessions.sh
├── templates/
│   ├── ticket.example.json
│   ├── session.example.jsonl
│   └── heartbeat-prompt.md
└── tests/
    └── test-scenarios.md
```
