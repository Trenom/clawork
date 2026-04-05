#!/usr/bin/env python3
"""
Clawork Engine — Core processing logic for routing and sessions.

This module provides the working implementation of:
- Ticket routing (matching rules from config.yaml)
- Session management (JSONL read/write/compact)
- Heartbeat execution (inbox scan + dispatch)
- Ticket lifecycle management

Usage:
    python3 clawork-engine.py heartbeat     # Run one heartbeat cycle
    python3 clawork-engine.py route <file>  # Route a single ticket
    python3 clawork-engine.py status        # Show system status
    python3 clawork-engine.py cleanup       # Cleanup old tickets
"""

import json
import glob
import re
import os
import sys
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

# --- Config ---

CLAW_HOME = os.environ.get("CLAW_HOME", os.path.expanduser("~/claw"))
TZ = timezone(timedelta(hours=-3))  # Default: America/Argentina/Cordoba


def now_iso():
    return datetime.now(TZ).isoformat()


def load_config():
    """Load config.yaml (supports PyYAML or falls back to built-in rules)."""
    config_path = os.path.join(CLAW_HOME, "config.yaml")
    if not os.path.exists(config_path):
        print(f"ERROR: {config_path} not found")
        sys.exit(1)

    try:
        import yaml
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except ImportError:
        pass

    # Manual fallback — provide example rules
    # Users should install PyYAML for full config support: pip install pyyaml
    return {
        "routing": {
            "rules": [],
            "default": {"skill": "clawork-soul", "priority": "normal"}
        },
        "limits": {
            "max_tickets_per_heartbeat": 10,
            "session_context_lines": 50,
            "session_compact_threshold": 200,
        }
    }


# --- Routing Engine ---

PRIORITY_ORDER = {"critical": 0, "high": 1, "normal": 2, "low": 3}


def route_ticket(ticket, config):
    """Apply routing rules to a ticket. Returns (action_dict, rule_description)."""
    rules = config.get("routing", {}).get("rules", [])
    default = config.get("routing", {}).get("default", {"skill": "clawork-soul", "priority": "normal"})
    instruction = ticket.get("instruction", "")
    channel = ticket.get("source", {}).get("channel", "")
    peer_id = ticket.get("source", {}).get("peer_id", "")

    for rule in rules:
        match = rule.get("match", {})

        # Channel match
        rule_channel = match.get("channel", "*")
        if rule_channel != "*" and rule_channel != channel:
            continue

        # Peer match
        if "peer" in match and match["peer"] != peer_id:
            continue

        # Content match
        if "content_contains" in match:
            pattern = match["content_contains"]
            if not re.search(pattern, instruction, re.IGNORECASE):
                continue

        # All conditions met
        return rule.get("action", default), f"rule:{match.get('content_contains', match.get('channel', '?'))[:40]}"

    return default, "default"


def load_pending_tickets():
    """Load all pending tickets from inbox, sorted by priority then creation time."""
    inbox = os.path.join(CLAW_HOME, "inbox")
    tickets = []

    for f in glob.glob(os.path.join(inbox, "*.json")):
        try:
            with open(f, "r") as fh:
                ticket = json.load(fh)
            if ticket.get("status") == "pending":
                tickets.append((ticket, f))
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  WARNING: Skipping malformed ticket {f}: {e}")

    tickets.sort(key=lambda x: (
        PRIORITY_ORDER.get(x[0].get("routing", {}).get("priority", "normal"), 2),
        x[0].get("created", "")
    ))

    return tickets


# --- Session Management ---

def get_session_path(channel, peer_id):
    """Get the session file path for a channel/peer combination."""
    safe_peer = re.sub(r'[^\w\-+@.]', '_', peer_id)
    session_dir = os.path.join(CLAW_HOME, "sessions", channel)
    os.makedirs(session_dir, exist_ok=True)
    return os.path.join(session_dir, f"{safe_peer}.jsonl")


def get_context(channel, peer_id, max_lines=50):
    """Read the last N lines of session history."""
    path = get_session_path(channel, peer_id)
    if not os.path.exists(path):
        return []

    with open(path, "r") as f:
        lines = f.readlines()

    context = []
    if lines and "[SUMMARY]" in lines[0]:
        context.append(json.loads(lines[0].strip()))
        lines = lines[1:]

    recent = lines[-max_lines:] if len(lines) > max_lines else lines
    for line in recent:
        line = line.strip()
        if line:
            try:
                context.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    return context


def append_session(channel, peer_id, role, content, ticket_id):
    """Append an interaction to the session file."""
    path = get_session_path(channel, peer_id)
    entry = {
        "ts": now_iso(),
        "role": role,
        "content": content,
        "channel": channel,
        "peer": peer_id,
        "ticket_id": ticket_id,
    }
    with open(path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    with open(path, "r") as f:
        line_count = sum(1 for _ in f)

    threshold = 200
    if line_count > threshold:
        compact_session(channel, peer_id)


def compact_session(channel, peer_id, keep_recent=50):
    """Compact a session file by summarizing old messages."""
    path = get_session_path(channel, peer_id)
    if not os.path.exists(path):
        return

    with open(path, "r") as f:
        lines = f.readlines()

    if len(lines) <= keep_recent:
        return

    archive_dir = os.path.join(CLAW_HOME, "sessions", ".archive")
    os.makedirs(archive_dir, exist_ok=True)
    archive_name = f"{channel}_{peer_id}_{datetime.now(TZ).strftime('%Y%m%d_%H%M%S')}.jsonl"
    with open(os.path.join(archive_dir, archive_name), "w") as f:
        f.writelines(lines)

    old_lines = lines[:-keep_recent]
    recent_lines = lines[-keep_recent:]

    topics = set()
    msg_count = 0
    for line in old_lines:
        try:
            entry = json.loads(line.strip())
            msg_count += 1
            words = entry.get("content", "").split()
            for w in words:
                if len(w) > 6 and w[0].isupper():
                    topics.add(w)
        except json.JSONDecodeError:
            pass

    summary = {
        "ts": now_iso(),
        "role": "system",
        "content": f"[SUMMARY] Summary of {msg_count} previous messages with {peer_id} on {channel}. "
                   f"Topics mentioned: {', '.join(list(topics)[:10]) if topics else 'general conversation'}.",
        "channel": channel,
        "peer": peer_id,
        "ticket_id": "compaction",
    }

    with open(path, "w") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")
        f.writelines(recent_lines)

    print(f"  Session compacted: {channel}/{peer_id} ({len(old_lines)} old -> summary + {len(recent_lines)} recent)")


# --- Ticket Processing ---

def process_ticket(ticket, ticket_path, config):
    """Process a single ticket: route, generate response, save session."""
    ticket_id = ticket["id"]
    channel = ticket["source"]["channel"]
    peer_id = ticket["source"]["peer_id"]
    instruction = ticket["instruction"]

    action, rule = route_ticket(ticket, config)
    skill = action["skill"]

    ticket["routing"]["target_skill"] = skill
    ticket["status"] = "processing"
    ticket["updated"] = now_iso()

    context = get_context(channel, peer_id)
    response = dispatch_to_skill(skill, ticket, context)

    append_session(channel, peer_id, "user", instruction, ticket_id)
    append_session(channel, peer_id, "assistant", response, ticket_id)

    ticket["status"] = "done"
    ticket["result"] = {
        "status": "done",
        "output": response,
        "files": [],
        "reply_sent": False,
        "completed_at": now_iso(),
    }
    ticket["updated"] = now_iso()

    outbox_path = os.path.join(CLAW_HOME, "outbox", os.path.basename(ticket_path))
    with open(outbox_path, "w") as f:
        json.dump(ticket, f, indent=2, ensure_ascii=False)

    os.remove(ticket_path)
    return skill, rule, response


def dispatch_to_skill(skill, ticket, context):
    """Dispatch ticket to appropriate skill and get response.

    In production, this invokes actual Cowork skills.
    Override this function to integrate with your skill implementations.
    """
    instruction = ticket["instruction"]
    peer_name = ticket["source"].get("peer_name", "")

    if skill == "clawork-soul":
        context_summary = ""
        if context:
            context_summary = f" (context: {len(context)} messages)"
        return f"[clawork-soul] Response to {peer_name}: processing '{instruction[:80]}'{context_summary}"

    elif skill == "gde-agent":
        numbers = re.findall(r'(?:EX|IF|NO|PV|RE)-\d{4}-\d+', instruction)
        if numbers:
            return f"[gde-agent] Querying GDE for: {', '.join(numbers)}"
        return f"[gde-agent] Processing document query: {instruction[:80]}"

    elif skill == "sugop-agent":
        return f"[sugop-agent] Querying SUGOP: {instruction[:80]}"

    elif skill == "openclaw-bridge":
        return f"[openclaw-bridge] Delegating to OpenClaw: {instruction[:80]}"

    else:
        return f"[{skill}] Processing: {instruction[:80]}"


# --- Heartbeat ---

def run_heartbeat():
    """Execute one heartbeat cycle."""
    start = datetime.now(TZ)
    config = load_config()
    max_tickets = config.get("limits", {}).get("max_tickets_per_heartbeat", 10)

    print(f"Clawork Heartbeat — {start.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print()

    tickets = load_pending_tickets()
    print(f"Pending tickets: {len(tickets)}")

    if not tickets:
        print("  (inbox empty, nothing to process)")
        log_heartbeat(start, 0, 0, 0)
        return

    processed = 0
    errors = 0
    routes = []

    for ticket, path in tickets[:max_tickets]:
        try:
            skill, rule, response = process_ticket(ticket, path, config)
            processed += 1
            routes.append({
                "id": ticket["id"],
                "skill": skill,
                "rule": rule,
                "priority": ticket["routing"]["priority"],
            })
            print(f"  OK {ticket['id']:15s} -> {skill:20s} ({rule})")
        except Exception as e:
            errors += 1
            print(f"  ERR {ticket.get('id', '?'):15s} — {e}")

    print()
    print(f"Processed: {processed} | Errors: {errors}")

    log_heartbeat(start, len(tickets), processed, errors, routes)
    cleanup_outbox()


def log_heartbeat(start, found, processed, errors, routes=None):
    """Write heartbeat execution log."""
    end = datetime.now(TZ)
    duration_ms = int((end - start).total_seconds() * 1000)

    log_entry = {
        "ts": now_iso(),
        "tickets_found": found,
        "tickets_processed": processed,
        "errors": errors,
        "duration_ms": duration_ms,
        "routes": routes or [],
    }

    log_path = os.path.join(CLAW_HOME, "logs", "heartbeat.jsonl")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    print(f"Log: {log_path} (duration: {duration_ms}ms)")


def cleanup_outbox(max_age_days=7):
    """Remove completed tickets older than max_age_days."""
    outbox = os.path.join(CLAW_HOME, "outbox")
    if not os.path.exists(outbox):
        return

    cutoff = datetime.now(TZ) - timedelta(days=max_age_days)
    removed = 0

    for f in glob.glob(os.path.join(outbox, "*.json")):
        try:
            with open(f, "r") as fh:
                ticket = json.load(fh)
            completed_at = ticket.get("result", {}).get("completed_at")
            if completed_at:
                completed = datetime.fromisoformat(completed_at)
                if completed < cutoff:
                    os.remove(f)
                    removed += 1
        except (json.JSONDecodeError, ValueError):
            pass

    if removed:
        print(f"Cleanup: {removed} old tickets removed from outbox")


# --- Status ---

def show_status():
    """Show current system status."""
    print("Clawork — System Status")
    print()

    inbox_files = glob.glob(os.path.join(CLAW_HOME, "inbox", "*.json"))
    pending = sum(1 for f in inbox_files if json.load(open(f)).get("status") == "pending")
    print(f"Inbox: {len(inbox_files)} tickets ({pending} pending)")

    outbox_files = glob.glob(os.path.join(CLAW_HOME, "outbox", "*.json"))
    print(f"Outbox: {len(outbox_files)} completed tickets")

    session_files = []
    for root, dirs, files in os.walk(os.path.join(CLAW_HOME, "sessions")):
        for f in files:
            if f.endswith(".jsonl") and ".archive" not in root:
                session_files.append(os.path.join(root, f))
    print(f"Sessions: {len(session_files)} active conversations")

    hb_log = os.path.join(CLAW_HOME, "logs", "heartbeat.jsonl")
    if os.path.exists(hb_log):
        with open(hb_log, "r") as f:
            lines = f.readlines()
        if lines:
            last = json.loads(lines[-1])
            print(f"Last heartbeat: {last['ts']} ({last['tickets_processed']} processed)")
    else:
        print("No heartbeat logs yet")

    config_path = os.path.join(CLAW_HOME, "config.yaml")
    print(f"Config: {'exists' if os.path.exists(config_path) else 'MISSING'}")

    soul_path = os.path.join(CLAW_HOME, "soul.md")
    print(f"Soul: {'exists' if os.path.exists(soul_path) else 'MISSING'}")


# --- CLI ---

def main():
    if len(sys.argv) < 2:
        print("Usage: clawork-engine.py <command>")
        print("Commands: heartbeat, route <file>, status, cleanup")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "heartbeat":
        run_heartbeat()
    elif cmd == "route" and len(sys.argv) > 2:
        config = load_config()
        with open(sys.argv[2], "r") as f:
            ticket = json.load(f)
        action, rule = route_ticket(ticket, config)
        print(f"Ticket: {ticket['id']}")
        print(f"Route: {action['skill']} (rule: {rule})")
    elif cmd == "status":
        show_status()
    elif cmd == "cleanup":
        cleanup_outbox()
        print("Cleanup complete")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
