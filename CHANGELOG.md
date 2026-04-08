# Changelog

All notable changes to Clawork are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Planned for Phase 2

- `clawork-messenger` skill for WhatsApp Web automation
- `clawork-messenger` skill for Telegram Web automation
- Enhanced error handling and retry logic
- Session compaction with automatic summarization
- Multi-agent coordination
- Integration test suite

### Planned for Phase 3

- Conversation history migration tool from OpenClaw
- Performance optimizations
- Analytics and metrics dashboard
- Extended channel support

### Planned for Phase 4 (Experimental)

- Native Android app control via device automation
- Cloud-based heartbeat scheduling
- Web UI for configuration management
- Agent-to-agent (A2A) communication protocol

---

## [0.1.0-beta] - 2026-04-07

> First published beta. CI pipeline is green (pytest + ruff), `dispatch_to_skill`
> is now registry-based with local/MCP/webhook paths, the package is pip-installable
> via `pyproject.toml`, and the engine has structured logging, retries, a poison
> queue, and a JSONL metrics stream. See the release notes on GitHub for the
> full Phase 2.5 summary.

### Initial Beta

This is the first beta cut of Clawork, featuring the core functionality
necessary to operate Claude Cowork as an autonomous personal agent. The
APIs are stable enough to build against; reliability features are still
being layered on.

#### Added

**Core Components**:
- `clawork-soul` skill — Agent personality and response generation
- `clawork-router` skill — Intelligent message routing engine
- `clawork-sessions` skill — Persistent conversation history management
- Ticket protocol specification (JSON format for all inter-component communication)
- Configuration system (`config.yaml`) compatible with OpenClaw

**Features**:
- Multi-channel message handling:
  - WhatsApp Web (via Computer Use, best-effort)
  - Telegram Web (via Computer Use, best-effort)
  - Slack (native connector)
  - Gmail (native connector)
- Conversation history per peer per channel
- Configurable routing rules (by channel, peer, content)
- Priority-based ticket processing
- Session compaction with automatic summarization
- Scheduled task heartbeat (configurable intervals)
- Comprehensive logging and auditability

**Setup & Migration**:
- `setup.sh` — Automated directory structure creation
- `import-openclaw-config.sh` — Configuration migration from OpenClaw
- `import-openclaw-sessions.sh` — Conversation history import tool
- Soul.md customization template

**Documentation**:
- README.md with quick start guide and Limitations section
- Architecture documentation with system design diagrams
- Complete configuration reference (`docs/config-reference.md`)
- Ticket protocol specification (`docs/ticket-protocol.md`)
- Migration guide from OpenClaw (`docs/migration-from-openclaw.md`)
- Step-by-step setup guide (`docs/setup-guide.md`)
- Contributing guidelines (`CONTRIBUTING.md`)

**Templates & Examples**:
- Example ticket JSON format
- Example session JSONL format
- Heartbeat scheduled task prompt
- Example configuration files

#### Features

**Routing Engine**:
- Channel-based routing (route different channels to different skills)
- Peer-based routing (special handling for specific people)
- Group-based routing (separate logic for group chats)
- Content-based routing (keywords trigger specialized skills)
- Priority levels (critical, high, normal, low)
- Context file injection for routing rules

**Session Management**:
- Per-peer conversation history (privacy by default)
- Configurable context window (how many previous messages to include)
- Automatic session compaction when exceeding threshold size
- Summarization of old messages preserving recent interactions
- Session backup on compaction for audit trail

**Configuration**:
- Single `config.yaml` for all settings
- Channel-specific options (enabled, method, interval, etc.)
- Routing rules with flexible matching logic
- Per-skill context files
- Configurable resource limits
- Timezone (IANA, defaults to UTC) and language selection

**Heartbeat Scheduler**:
- Configurable intervals (5m, 15m, 30m, 1h)
- Multiple actions per cycle:
  - Check enabled channels for new messages
  - Process inbox tickets
  - Cleanup old completed tickets
- Comprehensive logging of heartbeat execution

**Message Handling**:
- Multi-channel normalization (different channels → same ticket format)
- Attachment support (file metadata and paths)
- Conversation threading (reply context preservation)
- Message metadata (sender, timestamp, channel, group)
- Error handling and retry logic (up to 3 retries)

#### Technical Foundation

- **Message Bus**: Filesystem-based (JSON files in inbox/outbox)
- **Persistence**: Local filesystem (no third-party gateway services)
- **Connectors**: Cowork native connectors for Slack and Gmail
- **Browser Automation**: Computer Use for WhatsApp Web and Telegram Web
- **Scheduling**: Cowork Scheduled Tasks
- **Runtime dependencies**: Python 3 + PyYAML (and `tzdata` on Windows
  if a non-UTC `agent.timezone` is configured)

#### Compatibility

- Backward compatibility with OpenClaw configurations
- OpenClaw SOUL files work without modification
- Session format compatible (with migration helper)
- Configuration conversion tool (openclaw.json → config.yaml)

#### Known Limitations

1. **WhatsApp/Telegram Web**:
   - Requires keeping browser tabs open
   - Sensitive to UI changes in WhatsApp/Telegram Web
   - Subject to rate limiting if checking too frequently
   - Should be treated as best-effort, not transactional

2. **Reliability engineering is unproven at scale**:
   - No CI pipeline yet
   - No soak tests or production telemetry
   - Retry / structured-logging story is still being implemented

3. **`dispatch_to_skill` ships as a stub** — real deployments must
   override it to wire in their own skill registry, MCP tools, or
   external services.

4. **Session Compaction**:
   - Current implementation is basic (simple summarization)
   - May lose fine details during compression

5. **Native Android Apps**:
   - Not yet supported (experimental Android automation planned for Phase 4)
   - Workaround: Use WhatsApp Web / Telegram Web

6. **Cloud Heartbeat**:
   - Currently requires local Cowork project
   - Cloud-based heartbeat planned for Phase 4

#### Design Targets (not benchmarks)

The numbers below are intended throughput, not measured production metrics.
A real benchmarking pass is tracked in the Phase 3 backlog.

- Target throughput: ~40 messages/hour with default settings
- Target use cases: personal assistant and small team
- Target session size: under 500 KB with automatic compaction
- Target inbox/outbox capacity: thousands of tickets

#### Security Notes

- Conversation history stored locally (not in cloud)
- Per-peer session isolation
- No credentials stored in Clawork files
- Browser session security depends on Chrome/Cowork

#### Migration Notes

Users coming from OpenClaw:
- SOUL files can be copied directly (zero modification)
- Configuration can be auto-imported with high fidelity
- Session history can be migrated to Clawork format
- Cowork provides native support for Slack/Gmail (no custom gateways)

---

## Development Timeline

### Phase 1 (2026-04-05)
**Status**: Beta — core functionality implemented, hardening in progress

- Skills framework
- Routing engine
- Session management
- Configuration system
- OpenClaw migration tools
- Documentation

### Phase 2 (2026-04 to 2026-05)
**Status**: In Progress

Messaging capabilities:
- WhatsApp Web browser automation
- Telegram Web browser automation
- Enhanced error handling
- Rate limiting and anti-bot measures

### Phase 3 (2026-05 to 2026-06)
**Status**: Planned

Robustness and scale:
- Session history migration
- Multi-agent coordination
- Test suite
- Performance optimization

### Phase 4 (2026-06+)
**Status**: Experimental/Optional

Advanced capabilities:
- Android automation
- Cloud scheduling
- A2A protocol
- Web UI

---

## Versioning

Clawork follows semantic versioning:

- **Major** (X.0.0): Breaking changes, major architecture updates
- **Minor** (0.X.0): New features, backward compatible
- **Patch** (0.0.X): Bug fixes, documentation updates

---

## Upgrade Guide

When new versions are released, upgrade steps will be documented here.

---

## Support

- **Issues**: Report bugs on GitHub Issues
- **Questions**: Ask in GitHub Discussions
- **Documentation**: See docs/ directory
- **Contributing**: See CONTRIBUTING.md

---

## Credits

**Clawork** is inspired by and based on the architecture of [OpenClaw](https://github.com/nicobailey/openclaw) by Nico Bailey.

Clawork reimplements core concepts using Anthropic's native Cowork platform, demonstrating how sophisticated agentic systems can be built within platform boundaries.

**Maintained by**: Trenom and contributors. Thanks to the Cowork community
for early feedback.

---

## License

Clawork is released under the MIT License. See LICENSE file for details.

---

**Last Updated**: 2026-04-07

For the latest version and updates, visit: https://github.com/Trenom/clawork
