# Clawork

**Transform Claude Cowork into an Autonomous Personal Agent**

Run Claude natively as a multi-channel autonomous agent without third-party dependencies, ToS violations, or OAuth hacks.

Clawork is a skills kit and configuration system that transforms Anthropic's Claude Cowork into a fully autonomous personal agent. It ports the proven architecture of [OpenClaw](https://github.com/nicobailey/openclaw) to Cowork's native ecosystem, using only official Anthropic primitives: scheduled tasks, skills, computer use, projects, and connectors.

---

## Why Clawork?

Anthropic restricted third-party use of Claude subscriptions through OAuth and external gateways, prohibiting tools like OpenClaw from using Claude tokens as an autonomous agent backend.

However, **Cowork already provides all necessary primitives natively**. Clawork bridges that gap.

## What It Does

- **Receives and responds** to messages from WhatsApp, Telegram, Slack, Gmail autonomously
- **Maintains conversation history** per person and per channel (persistent sessions)
- **Routes intelligently** with a configurable rules engine
- **Runs continuously** via a heartbeat scheduler
- **Respects your personality** through a customizable SOUL file
- **Scales vertically** — add skills, routing rules, integrations without changing core

**All configured through a single `config.yaml` file.**

## Primitives Mapping

| Primitive | OpenClaw | Cowork Equivalent |
|-----------|----------|-------------------|
| Agent loop | Custom runtime | Cowork runtime |
| Heartbeat scheduler | Cron service | Scheduled Tasks |
| Channels | Custom gateways | Connectors + Computer Use |
| Session persistence | File-based state | Projects + filesystem |
| Routing engine | Rules system | Skills-based dispatch |
| System prompt (SOUL) | `soul.json` | Project instructions |
| Memory | Hybrid (JSON + DB) | Files + memory primitives |
| Tool ecosystem | Integrations | Computer Use + connectors |

## Design Philosophy

1. **No external dependencies** — Use only native Cowork primitives
2. **Configuration over code** — Everything configurable via YAML
3. **The SOUL is sacred** — Respect your agent's personality
4. **Fail gracefully** — Errors create tickets, not silent failures
5. **Local-first** — Filesystem as the bus, not cloud services
6. **Human-readable** — Inspect everything with standard tools
7. **Portable** — Run anywhere Cowork runs

## Next Steps

- [Quick Start](quickstart.md) — Get running in 5 minutes
- [Skills Reference](skills.md) — Explore the skill ecosystem
- [Configuration Schema](config-schema.md) — Full config.yaml reference
- [Migrating from OpenClaw](migration.md) — Seamless transition guide
