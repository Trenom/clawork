#!/usr/bin/env python3
"""
Clawork Integration Test Suite

Tests the full pipeline: ticket creation -> routing -> processing -> session management.
Requires: ~/claw/ directory structure (run scripts/setup.sh first)

Run with: python3 tests/test-integration.py
"""

import json
import os
import sys
import shutil
import glob
import re
from datetime import datetime, timezone, timedelta

# --- Setup ---

CLAW_HOME = os.environ.get("CLAW_HOME", os.path.expanduser("~/claw"))
TZ = timezone(timedelta(hours=-3))
ENGINE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "clawork-engine.py")

passed = 0
failed = 0
total = 0


def test(name, condition, detail=""):
    global passed, failed, total
    total += 1
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} — {detail}")


def clean_state():
    """Remove all test data from inbox/outbox/sessions."""
    for d in ["inbox", "outbox"]:
        for f in glob.glob(os.path.join(CLAW_HOME, d, "test_*.json")):
            os.remove(f)
        for f in glob.glob(os.path.join(CLAW_HOME, d, "hb_*.json")):
            os.remove(f)
    for root, dirs, files in os.walk(os.path.join(CLAW_HOME, "sessions")):
        for f in files:
            if "test" in f.lower() or "compaction" in f or "compact_test" in f:
                os.remove(os.path.join(root, f))


def create_ticket(ticket_id, channel, peer_id, peer_name, instruction, priority="normal", deadline=None):
    """Helper to create a test ticket."""
    ticket = {
        "id": ticket_id,
        "status": "pending",
        "created": datetime.now(TZ).isoformat(),
        "updated": None,
        "source": {
            "channel": channel,
            "peer_id": peer_id,
            "peer_name": peer_name,
            "group": None,
            "message_id": f"{channel}_{ticket_id}"
        },
        "instruction": instruction,
        "context": {"conversation_history": [], "attachments": [], "reply_to_ticket": None},
        "routing": {"target_skill": None, "priority": priority, "deadline": deadline},
        "result": {"status": None, "output": None, "files": [], "reply_sent": False, "completed_at": None}
    }
    path = os.path.join(CLAW_HOME, "inbox", f"{ticket_id}.json")
    with open(path, "w") as f:
        json.dump(ticket, f, indent=2, ensure_ascii=False)
    return ticket, path


# --- Import engine functions ---

import importlib.util
spec = importlib.util.spec_from_file_location("engine", ENGINE)
engine = importlib.util.module_from_spec(spec)

_real_argv = sys.argv
sys.argv = ["test"]
try:
    spec.loader.exec_module(engine)
except SystemExit:
    pass
sys.argv = _real_argv


# === TEST SUITE ===

print("Clawork Integration Test Suite")
print("=" * 40)
print()

clean_state()

# --- Test Group 1: Routing ---

print("=== 1. ROUTING RULES ===")

config = engine.load_config()

t1, _ = create_ticket("test_r01", "whatsapp", "+0000", "Default", "Hello, how are you?")
action, rule = engine.route_ticket(t1, config)
test("Default -> clawork-soul", action["skill"] == "clawork-soul", f"got {action['skill']}")

t2, _ = create_ticket("test_r02", "whatsapp", "+0001", "GDE", "I need document EX-2025-12345678")
action, rule = engine.route_ticket(t2, config)
test("EX- -> gde-agent", action["skill"] == "gde-agent", f"got {action['skill']}")

t3, _ = create_ticket("test_r03", "gmail", "user@example.com", "IF", "Send me IF-2025-00001")
action, rule = engine.route_ticket(t3, config)
test("IF- -> gde-agent", action["skill"] == "gde-agent", f"got {action['skill']}")

t4, _ = create_ticket("test_r04", "whatsapp", "+0002", "NO", "Document NO-2025-55555 has errors")
action, rule = engine.route_ticket(t4, config)
test("NO- -> gde-agent", action["skill"] == "gde-agent", f"got {action['skill']}")

print()

# --- Test Group 2: Priority ordering ---

print("=== 2. PRIORITY ORDERING ===")

clean_state()
create_ticket("test_p01", "whatsapp", "+0", "Low", "When you can...", priority="low")
create_ticket("test_p02", "gmail", "+1", "Critical", "URGENT!", priority="critical")
create_ticket("test_p03", "telegram", "+2", "Normal", "Query", priority="normal")
create_ticket("test_p04", "whatsapp", "+3", "High", "Need this soon", priority="high")

tickets = engine.load_pending_tickets()
priorities = [t[0]["routing"]["priority"] for t in tickets]
test("Critical first", priorities[0] == "critical", f"got {priorities[0]}")
test("High second", priorities[1] == "high", f"got {priorities[1]}")
test("Normal third", priorities[2] == "normal", f"got {priorities[2]}")
test("Low last", priorities[3] == "low", f"got {priorities[3]}")

print()

# --- Test Group 3: Ticket processing ---

print("=== 3. TICKET PROCESSING ===")

clean_state()
ticket, path = create_ticket("test_proc01", "whatsapp", "+0test", "Tester", "Hello test!")

skill, rule, response = engine.process_ticket(ticket, path, config)
test("Ticket routed", skill == "clawork-soul")
test("Response generated", len(response) > 0, "empty response")
test("Ticket removed from inbox", not os.path.exists(path))
test("Ticket in outbox", os.path.exists(os.path.join(CLAW_HOME, "outbox", "test_proc01.json")))

with open(os.path.join(CLAW_HOME, "outbox", "test_proc01.json")) as f:
    done_ticket = json.load(f)
test("Status is done", done_ticket["status"] == "done")
test("Result status is done", done_ticket["result"]["status"] == "done")
test("Has output", done_ticket["result"]["output"] is not None and len(done_ticket["result"]["output"]) > 0)
test("Has completed_at", done_ticket["result"]["completed_at"] is not None)
test("Routing target set", done_ticket["routing"]["target_skill"] == "clawork-soul")

print()

# --- Test Group 4: Session management ---

print("=== 4. SESSION MANAGEMENT ===")

session_path = engine.get_session_path("whatsapp", "+0test")
test("Session file created", os.path.exists(session_path))

with open(session_path) as f:
    lines = f.readlines()
test("Session has 2 entries (user + assistant)", len(lines) == 2, f"got {len(lines)}")

entries = [json.loads(l) for l in lines]
test("First entry is user", entries[0]["role"] == "user")
test("Second entry is assistant", entries[1]["role"] == "assistant")
test("User content matches", entries[0]["content"] == "Hello test!")
test("Ticket ID tracked", entries[0]["ticket_id"] == "test_proc01")

context = engine.get_context("whatsapp", "+0test")
test("get_context returns entries", len(context) == 2)

empty = engine.get_context("whatsapp", "nonexistent_peer")
test("Empty context for new peer", len(empty) == 0)

print()

# --- Test Group 5: Session compaction ---

print("=== 5. SESSION COMPACTION ===")

compact_path = engine.get_session_path("whatsapp", "compact_test_peer")
with open(compact_path, "w") as f:
    for i in range(250):
        entry = {"ts": "2026-04-01T10:00:00-03:00", "role": "user" if i % 2 == 0 else "assistant",
                 "content": f"Message {i} about project review", "channel": "whatsapp",
                 "peer": "compact_test_peer", "ticket_id": f"ct_{i}"}
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

with open(compact_path) as f:
    before = sum(1 for _ in f)
test("Pre-compaction has 250 lines", before == 250)

engine.compact_session("whatsapp", "compact_test_peer", keep_recent=50)

with open(compact_path) as f:
    lines = f.readlines()
test("Post-compaction: 51 lines (summary + 50)", len(lines) == 51, f"got {len(lines)}")

first = json.loads(lines[0])
test("First line is SUMMARY", "[SUMMARY]" in first["content"])
test("Summary is system role", first["role"] == "system")

archive_dir = os.path.join(CLAW_HOME, "sessions", ".archive")
archives = [f for f in os.listdir(archive_dir) if "compact_test" in f] if os.path.exists(archive_dir) else []
test("Archive backup created", len(archives) > 0)

context = engine.get_context("whatsapp", "compact_test_peer")
test("Context includes summary", any("[SUMMARY]" in c.get("content", "") for c in context))

print()

# --- Test Group 6: Full heartbeat cycle ---

print("=== 6. FULL HEARTBEAT CYCLE ===")

clean_state()
create_ticket("test_hb01", "whatsapp", "+0hb1", "User1", "Hello!", priority="normal")
create_ticket("test_hb02", "gmail", "urgent@example.com", "Director", "IF-2025-99999 URGENT", priority="critical")
create_ticket("test_hb03", "telegram", "user_tg", "Inspector", "Project status update", priority="high")

engine.run_heartbeat()

inbox_remaining = glob.glob(os.path.join(CLAW_HOME, "inbox", "test_hb*.json"))
outbox_done = glob.glob(os.path.join(CLAW_HOME, "outbox", "test_hb*.json"))
test("Inbox cleared", len(inbox_remaining) == 0, f"{len(inbox_remaining)} remaining")
test("Outbox has 3 tickets", len(outbox_done) == 3, f"got {len(outbox_done)}")

log_path = os.path.join(CLAW_HOME, "logs", "heartbeat.jsonl")
test("Heartbeat log exists", os.path.exists(log_path))
with open(log_path) as f:
    last_log = json.loads(f.readlines()[-1])
test("Log shows 3 processed", last_log["tickets_processed"] == 3, f"got {last_log['tickets_processed']}")
test("Log shows 0 errors", last_log["errors"] == 0)

print()

# --- Test Group 7: Edge cases ---

print("=== 7. EDGE CASES ===")

clean_state()
engine.run_heartbeat()
test("Empty inbox heartbeat OK", True)

malformed_path = os.path.join(CLAW_HOME, "inbox", "test_malformed.json")
with open(malformed_path, "w") as f:
    f.write("{invalid json")
tickets = engine.load_pending_tickets()
test("Malformed ticket skipped gracefully", True)
os.remove(malformed_path)

clean_state()
long_msg = "x" * 5000
t_long, p_long = create_ticket("test_long", "whatsapp", "+0long", "Long", long_msg)
skill, rule, resp = engine.process_ticket(t_long, p_long, config)
test("Long message processed", skill == "clawork-soul")

print()

# === RESULTS ===

clean_state()

print("=" * 40)
print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
print("=" * 40)

if failed > 0:
    print(f"\n  {failed} TESTS FAILED")
    sys.exit(1)
else:
    print(f"\n  ALL {total} TESTS PASSED")
    sys.exit(0)
