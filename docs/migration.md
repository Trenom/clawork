# Migrating from OpenClaw

If you're already running OpenClaw, migration to Clawork is straightforward. Your SOUL, configuration, and conversation history can all be preserved.

## Step 1: Copy Your SOUL

The SOUL file is your agent's personality. It transfers directly — no adaptation required.

=== "Separate soul.md"

    ```bash
    cp ~/.openclaw/soul.md ~/claw/soul.md
    ```

=== "Extract from openclaw.json"

    ```bash
    jq -r '.agents[0].systemPrompt' ~/.openclaw/openclaw.json > ~/claw/soul.md
    ```

!!! note "The SOUL is sacred"
    Clawork preserves the same philosophy as OpenClaw — your agent's personality file is loaded as-is with zero modifications.

## Step 2: Migrate Configuration

```bash
bash scripts/import-openclaw-config.sh
```

This reads `~/.openclaw/openclaw.json` and generates a compatible `config.yaml`. Review and adjust as needed.

The script maps:

| OpenClaw Field | Clawork Equivalent |
|----------------|-------------------|
| `agents[0].systemPrompt` | `agent.soul` |
| `channels` | `channels` section |
| `routing` | `routing.rules` |
| `schedule.interval` | `heartbeat.interval` |
| `limits` | `limits` section |

## Step 3: Migrate Conversation History (Optional)

```bash
bash scripts/import-openclaw-sessions.sh
```

This imports your existing conversation sessions into Clawork's JSONL format:

1. Reads session files from `~/.openclaw/state/sessions/`
2. Extracts compatible fields (`ts`, `role`, `content`)
3. Adds `channel` and `peer` inferred from filename
4. Writes in Clawork JSONL format to `~/claw/sessions/`

## What's Preserved

- **Agent personality (SOUL)** — zero changes required
- **Channel configuration** — WhatsApp, Telegram, Slack, Gmail
- **Routing rules and priorities**
- **Conversation history** (if migrated)
- **Timezone and language settings**

## What's New

| Feature | OpenClaw | Clawork |
|---------|----------|---------|
| Scheduler | External cron | Native Cowork Scheduled Tasks |
| Connectors | OAuth workarounds | Official Anthropic connectors |
| Browser automation | Puppeteer | Computer Use (Claude in Chrome) |
| Memory & persistence | Custom state files | Cowork Projects |
| Runtime | Custom agent loop | Cowork native runtime |

## Verification Checklist

After migration, verify:

- [ ] `~/claw/soul.md` exists and contains your personality
- [ ] `~/claw/config.yaml` has correct channel settings
- [ ] Heartbeat Scheduled Task is configured and enabled
- [ ] Browser tabs are open for WhatsApp/Telegram (if used)
- [ ] Send a test message and verify it appears in `~/claw/inbox/`
- [ ] Check `~/claw/logs/router.jsonl` for successful processing
