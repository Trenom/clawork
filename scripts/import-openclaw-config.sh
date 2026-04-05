#!/bin/bash
# Clawork — Import OpenClaw Configuration
# Reads ~/.openclaw/openclaw.json and generates ~/claw/config.yaml compatible version
set -e

OPENCLAW_CONFIG="${OPENCLAW_CONFIG:-$HOME/.openclaw/openclaw.json}"
CLAW_HOME="${CLAW_HOME:-$HOME/claw}"

echo "╔══════════════════════════════════════════╗"
echo "║   Clawork — Import OpenClaw Config       ║"
echo "╚══════════════════════════════════════════╝"
echo ""

if [ ! -f "$OPENCLAW_CONFIG" ]; then
    echo "ERROR: $OPENCLAW_CONFIG not found"
    echo "Verify that OpenClaw is installed."
    exit 1
fi

echo "Reading: $OPENCLAW_CONFIG"
echo "Destination: $CLAW_HOME/config.yaml"
echo ""

python3 << PYEOF
import json, yaml, sys

# Read OpenClaw config
with open("$OPENCLAW_CONFIG", "r") as f:
    oc = json.load(f)

# Build Clawork config
config = {
    "agent": {
        "name": oc.get("agents", [{}])[0].get("name", "My Clawork Agent"),
        "soul": "./soul.md",
        "language": "en",
        "timezone": "America/New_York",
    },
    "channels": {},
    "routing": {
        "rules": [],
        "default": {"skill": "clawork-soul", "priority": "normal"}
    },
    "heartbeat": {
        "interval": "15m",
        "actions": ["check_inbox", "check_channels", "cleanup_old_tickets"]
    },
    "paths": {
        "inbox": "./inbox/",
        "outbox": "./outbox/",
        "sessions": "./sessions/",
        "memory": "./memory/",
        "logs": "./logs/",
        "contexts": "./contexts/",
    },
    "limits": {
        "max_tickets_per_heartbeat": 10,
        "session_context_lines": 50,
        "session_compact_threshold": 200,
        "message_delay_seconds": 3,
        "max_message_length": 4000,
    }
}

# Map channels from OpenClaw
channels_map = {
    "whatsapp": {"method": "browser", "check_interval": "5m", "url": "https://web.whatsapp.com"},
    "telegram": {"method": "browser", "check_interval": "5m", "url": "https://web.telegram.org/k/"},
    "slack": {"method": "connector", "check_interval": "on-event"},
    "gmail": {"method": "connector", "check_interval": "15m"},
}

oc_channels = oc.get("channels", {})
for ch_name, ch_defaults in channels_map.items():
    oc_ch = oc_channels.get(ch_name, {})
    enabled = oc_ch.get("enabled", False)
    channel_config = {
        "enabled": enabled,
        **ch_defaults,
        "session_mode": oc_ch.get("sessionMode", "per-peer"),
    }
    if "allowedPeers" in oc_ch:
        channel_config["allowed_peers"] = oc_ch["allowedPeers"]
    if "allowedGroups" in oc_ch:
        channel_config["allowed_groups"] = oc_ch["allowedGroups"]
    config["channels"][ch_name] = channel_config

# Map routing rules
oc_routing = oc.get("routing", {})
for rule in oc_routing.get("rules", []):
    clawork_rule = {"match": {}, "action": {}}
    if "channel" in rule.get("match", {}):
        clawork_rule["match"]["channel"] = rule["match"]["channel"]
    if "peer" in rule.get("match", {}):
        clawork_rule["match"]["peer"] = rule["match"]["peer"]
    if "contentContains" in rule.get("match", {}):
        clawork_rule["match"]["content_contains"] = rule["match"]["contentContains"]
    clawork_rule["action"]["skill"] = rule.get("action", {}).get("skill", "clawork-soul")
    clawork_rule["action"]["priority"] = rule.get("action", {}).get("priority", "normal")
    config["routing"]["rules"].append(clawork_rule)

# Write YAML
try:
    import yaml
    output = yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False)
except ImportError:
    # Fallback without PyYAML — generate manual YAML
    output = "# Clawork config — imported from OpenClaw\n"
    output += f"# Generated on $(date -I)\n"
    output += json.dumps(config, indent=2, ensure_ascii=False)
    output += "\n# NOTE: Install PyYAML for better formatting: pip install pyyaml\n"

with open("$CLAW_HOME/config.yaml", "w") as f:
    f.write(output)

print("Config imported successfully!")
print(f"Channels found: {list(config['channels'].keys())}")
print(f"Routing rules: {len(config['routing']['rules'])}")
PYEOF

echo ""
echo "Import complete."
echo "Review $CLAW_HOME/config.yaml and adjust as needed."
