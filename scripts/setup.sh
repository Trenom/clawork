#!/bin/bash
# Clawork — Setup Script
# Creates the directory structure needed for Clawork
set -e

CLAW_HOME="${CLAW_HOME:-$HOME/claw}"

echo "╔══════════════════════════════════════════╗"
echo "║         Clawork — Setup Script           ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Base directory: $CLAW_HOME"
echo ""

# Create structure
echo "Creating directory structure..."
mkdir -p "$CLAW_HOME"/{inbox,outbox/archive,outbox/orchestrator,sessions/{whatsapp,telegram,slack,gmail},memory,logs,contexts,skills}

echo "  ✓ inbox/"
echo "  ✓ outbox/ (+ archive/, orchestrator/)"
echo "  ✓ sessions/ (+ whatsapp/, telegram/, slack/, gmail/)"
echo "  ✓ memory/"
echo "  ✓ logs/"
echo "  ✓ contexts/"
echo "  ✓ skills/"

# Copy example config if it doesn't exist
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_SRC="$SCRIPT_DIR/../config/config.example.yaml"

if [ ! -f "$CLAW_HOME/config.yaml" ]; then
    if [ -f "$CONFIG_SRC" ]; then
        cp "$CONFIG_SRC" "$CLAW_HOME/config.yaml"
        echo ""
        echo "  ✓ config.yaml (copied from example)"
    else
        echo ""
        echo "  ⚠ config.example.yaml not found, create config.yaml manually"
    fi
else
    echo ""
    echo "  → config.yaml already exists, not overwriting"
fi

# Create default soul.md if it doesn't exist
if [ ! -f "$CLAW_HOME/soul.md" ]; then
    cat > "$CLAW_HOME/soul.md" << 'SOUL'
# Clawork Agent SOUL

You are an autonomous personal agent operating within Claude Cowork.
Your name and personality are configurable in config.yaml.

## Base Behavior

- You process tickets from the inbox autonomously
- You respond through the same channel you received the message
- You maintain context per peer (each person has their history)
- You use available tools (connectors, browser, filesystem)
- When you don't know something, you say so — you never make things up
- You follow user instructions over defaults

## Response Format

When processing a ticket:
1. Update ticket status to "processing"
2. Execute the task
3. Write the result in the ticket
4. Send the response to the source channel
5. Update status to "done"
SOUL
    echo "  ✓ soul.md (default)"
else
    echo "  → soul.md already exists, not overwriting"
fi

# Permissions
chmod 700 "$CLAW_HOME"
echo ""
echo "  ✓ Permissions: 700 (owner only)"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║         Setup Complete!                  ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. Edit $CLAW_HOME/config.yaml with your settings"
echo "  2. Edit $CLAW_HOME/soul.md with your personality"
echo "  3. Configure the heartbeat in Cowork (Scheduled Tasks)"
echo "  4. Open WhatsApp Web in Chrome if using WhatsApp"
echo ""
