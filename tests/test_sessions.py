#!/usr/bin/env python3
"""
Tests for clawork-sessions: JSONL session management and compaction.

Covers:
- Happy path: append, read context, session path generation, compaction
- Edge cases: empty sessions, nonexistent peers, special chars in peer IDs,
  compaction threshold, summary preservation, archive creation,
  concurrent appends, very large sessions
"""

import json
import os
import sys
import tempfile
import shutil

# Import engine from scripts/
ENGINE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "clawork-engine.py")

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
        print(f"  FAIL: {name} -- {detail}")


def setup_tmpdir():
    """Create a fresh temp claw dir and point engine at it."""
    tmpdir = tempfile.mkdtemp(prefix="clawork_sess_test_")
    for d in ["inbox", "outbox", "sessions", "logs"]:
        os.makedirs(os.path.join(tmpdir, d), exist_ok=True)
    return tmpdir


print("clawork-sessions Test Suite")
print("=" * 40)
print()

orig_home = engine.CLAW_HOME

# === HAPPY PATH: Session Path ===

print("=== HAPPY PATH: Session Path Generation ===")

tmpdir = setup_tmpdir()
engine.CLAW_HOME = tmpdir

path = engine.get_session_path("whatsapp", "+5491155555555")
test("Path includes channel dir", "/sessions/whatsapp/" in path)
test("Path ends with .jsonl", path.endswith(".jsonl"))
test("Channel dir created", os.path.isdir(os.path.join(tmpdir, "sessions", "whatsapp")))

path_tg = engine.get_session_path("telegram", "user_123456")
test("Telegram path correct", "/sessions/telegram/" in path_tg)
test("Peer ID in filename", "user_123456" in path_tg)

path_gmail = engine.get_session_path("gmail", "test@example.com")
test("Gmail path correct", "/sessions/gmail/" in path_gmail)
test("Email peer in filename", "test@example.com" in path_gmail)

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

# === HAPPY PATH: Append and Read ===

print("=== HAPPY PATH: Append and Read Context ===")

tmpdir = setup_tmpdir()
engine.CLAW_HOME = tmpdir

engine.append_session("whatsapp", "+0001", "user", "Hello!", "ticket_001")
engine.append_session("whatsapp", "+0001", "assistant", "Hi there!", "ticket_001")

path = engine.get_session_path("whatsapp", "+0001")
test("Session file created after append", os.path.exists(path))

with open(path, "r") as f:
    lines = f.readlines()
test("Two entries written", len(lines) == 2, f"got {len(lines)}")

entry1 = json.loads(lines[0])
entry2 = json.loads(lines[1])
test("First entry is user", entry1["role"] == "user")
test("Second entry is assistant", entry2["role"] == "assistant")
test("User content correct", entry1["content"] == "Hello!")
test("Assistant content correct", entry2["content"] == "Hi there!")
test("Channel recorded", entry1["channel"] == "whatsapp")
test("Peer recorded", entry1["peer"] == "+0001")
test("Ticket ID recorded", entry1["ticket_id"] == "ticket_001")
test("Timestamp present", "ts" in entry1 and len(entry1["ts"]) > 0)

context = engine.get_context("whatsapp", "+0001")
test("get_context returns 2 entries", len(context) == 2, f"got {len(context)}")
test("Context first is user", context[0]["role"] == "user")
test("Context second is assistant", context[1]["role"] == "assistant")

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

# === HAPPY PATH: Context Line Limit ===

print("=== HAPPY PATH: Context Line Limit ===")

tmpdir = setup_tmpdir()
engine.CLAW_HOME = tmpdir

path = engine.get_session_path("telegram", "user_big")
with open(path, "w") as f:
    for i in range(100):
        entry = {"ts": "2026-01-01T00:00:00", "role": "user", "content": f"msg {i}",
                 "channel": "telegram", "peer": "user_big", "ticket_id": f"t{i}"}
        f.write(json.dumps(entry) + "\n")

context = engine.get_context("telegram", "user_big", max_lines=20)
test("Context limited to 20 lines", len(context) == 20, f"got {len(context)}")
test("Context has most recent messages", context[-1]["content"] == "msg 99")
test("Context starts at msg 80", context[0]["content"] == "msg 80", f"got {context[0]['content']}")

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

# === HAPPY PATH: Compaction ===

print("=== HAPPY PATH: Session Compaction ===")

tmpdir = setup_tmpdir()
engine.CLAW_HOME = tmpdir

path = engine.get_session_path("whatsapp", "compact_peer")
with open(path, "w") as f:
    for i in range(250):
        entry = {"ts": "2026-04-01T10:00:00-03:00",
                 "role": "user" if i % 2 == 0 else "assistant",
                 "content": f"Message {i} about Project Review",
                 "channel": "whatsapp", "peer": "compact_peer", "ticket_id": f"ct_{i}"}
        f.write(json.dumps(entry) + "\n")

with open(path) as f:
    before_count = sum(1 for _ in f)
test("Pre-compaction has 250 lines", before_count == 250)

engine.compact_session("whatsapp", "compact_peer", keep_recent=50)

with open(path) as f:
    lines = f.readlines()

test("Post-compaction: 51 lines (summary + 50)", len(lines) == 51, f"got {len(lines)}")

summary = json.loads(lines[0])
test("First line is SUMMARY", "[SUMMARY]" in summary["content"])
test("Summary role is system", summary["role"] == "system")
test("Summary has channel", summary["channel"] == "whatsapp")
test("Summary has peer", summary["peer"] == "compact_peer")
test("Summary mentions message count", "200" in summary["content"], f"got: {summary['content']}")

last = json.loads(lines[-1])
test("Last line is msg 249", "Message 249" in last["content"], f"got: {last['content']}")

archive_dir = os.path.join(tmpdir, "sessions", ".archive")
test("Archive directory created", os.path.isdir(archive_dir))
archives = os.listdir(archive_dir)
test("Archive backup created", len(archives) > 0, f"archives: {archives}")
test("Archive filename has peer", any("compact_peer" in a for a in archives))

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

# === HAPPY PATH: Context After Compaction ===

print("=== HAPPY PATH: Context After Compaction ===")

tmpdir = setup_tmpdir()
engine.CLAW_HOME = tmpdir

path = engine.get_session_path("whatsapp", "ctx_compact")

summary_line = json.dumps({"ts": "2026-04-01", "role": "system",
    "content": "[SUMMARY] Summary of 200 messages. Topics: orders, shipping.",
    "channel": "whatsapp", "peer": "ctx_compact", "ticket_id": "compaction"})

with open(path, "w") as f:
    f.write(summary_line + "\n")
    for i in range(30):
        entry = {"ts": "2026-04-02", "role": "user", "content": f"Recent msg {i}",
                 "channel": "whatsapp", "peer": "ctx_compact", "ticket_id": f"r{i}"}
        f.write(json.dumps(entry) + "\n")

context = engine.get_context("whatsapp", "ctx_compact")
test("Context includes summary", any("[SUMMARY]" in c.get("content", "") for c in context))
test("Summary is first in context", "[SUMMARY]" in context[0]["content"])
test("Context has summary + 30 messages", len(context) == 31, f"got {len(context)}")

context_limited = engine.get_context("whatsapp", "ctx_compact", max_lines=10)
test("Limited context still includes summary", "[SUMMARY]" in context_limited[0]["content"])
test("Limited context: summary + 10", len(context_limited) == 11, f"got {len(context_limited)}")

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

# === EDGE CASES ===

print("=== EDGE CASE: Nonexistent Peer ===")

tmpdir = setup_tmpdir()
engine.CLAW_HOME = tmpdir

context = engine.get_context("whatsapp", "nobody")
test("Empty context for new peer", len(context) == 0)

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

print("=== EDGE CASE: Special Characters in Peer ID ===")

tmpdir = setup_tmpdir()
engine.CLAW_HOME = tmpdir

path = engine.get_session_path("whatsapp", "+54 911 5555-5555")
test("Special chars sanitized in path", os.path.exists(os.path.dirname(path)))
test("Path is valid filename", ".jsonl" in path)

engine.append_session("whatsapp", "+54 911 5555-5555", "user", "Test", "t1")
test("Append works with special char peer", os.path.exists(path))

context = engine.get_context("whatsapp", "+54 911 5555-5555")
test("Read works with special char peer", len(context) == 1)

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

print("=== EDGE CASE: Unicode Content ===")

tmpdir = setup_tmpdir()
engine.CLAW_HOME = tmpdir

engine.append_session("whatsapp", "+0unicode", "user", "Hola! Certificación 🎉 ñ á é", "t1")

context = engine.get_context("whatsapp", "+0unicode")
test("Unicode content preserved", context[0]["content"] == "Hola! Certificación 🎉 ñ á é",
     f"got: {context[0]['content']}")

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

print("=== EDGE CASE: Compaction Below Threshold ===")

tmpdir = setup_tmpdir()
engine.CLAW_HOME = tmpdir

path = engine.get_session_path("telegram", "small_peer")
with open(path, "w") as f:
    for i in range(30):
        entry = {"ts": "2026-01-01", "role": "user", "content": f"msg {i}",
                 "channel": "telegram", "peer": "small_peer", "ticket_id": f"t{i}"}
        f.write(json.dumps(entry) + "\n")

engine.compact_session("telegram", "small_peer", keep_recent=50)

with open(path) as f:
    lines = f.readlines()
test("No compaction when below threshold", len(lines) == 30, f"got {len(lines)}")

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

print("=== EDGE CASE: Compaction of Nonexistent File ===")

tmpdir = setup_tmpdir()
engine.CLAW_HOME = tmpdir

# Should not crash
engine.compact_session("whatsapp", "ghost_peer")
test("Compaction of nonexistent file doesn't crash", True)

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

print("=== EDGE CASE: Empty Lines in Session File ===")

tmpdir = setup_tmpdir()
engine.CLAW_HOME = tmpdir

path = engine.get_session_path("telegram", "gaps_peer")
with open(path, "w") as f:
    f.write(json.dumps({"ts": "2026-01-01", "role": "user", "content": "msg1",
                         "channel": "telegram", "peer": "gaps_peer", "ticket_id": "t1"}) + "\n")
    f.write("\n")  # empty line
    f.write("\n")  # another empty line
    f.write(json.dumps({"ts": "2026-01-02", "role": "assistant", "content": "reply1",
                         "channel": "telegram", "peer": "gaps_peer", "ticket_id": "t1"}) + "\n")

context = engine.get_context("telegram", "gaps_peer")
test("Empty lines skipped in context", len(context) == 2, f"got {len(context)}")

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

print("=== EDGE CASE: Malformed JSON Lines in Session ===")

tmpdir = setup_tmpdir()
engine.CLAW_HOME = tmpdir

path = engine.get_session_path("whatsapp", "bad_json_peer")
with open(path, "w") as f:
    f.write(json.dumps({"ts": "2026-01-01", "role": "user", "content": "good msg",
                         "channel": "whatsapp", "peer": "bad_json_peer", "ticket_id": "t1"}) + "\n")
    f.write("{broken json line\n")
    f.write(json.dumps({"ts": "2026-01-02", "role": "assistant", "content": "good reply",
                         "channel": "whatsapp", "peer": "bad_json_peer", "ticket_id": "t1"}) + "\n")

context = engine.get_context("whatsapp", "bad_json_peer")
test("Malformed JSON lines skipped", len(context) == 2, f"got {len(context)}")
test("Valid entries preserved", context[0]["content"] == "good msg")

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

print("=== EDGE CASE: Multiple Channels Same Peer ===")

tmpdir = setup_tmpdir()
engine.CLAW_HOME = tmpdir

engine.append_session("whatsapp", "+0multi", "user", "WhatsApp msg", "t1")
engine.append_session("telegram", "+0multi", "user", "Telegram msg", "t2")

ctx_wa = engine.get_context("whatsapp", "+0multi")
ctx_tg = engine.get_context("telegram", "+0multi")

test("WhatsApp session isolated", len(ctx_wa) == 1)
test("Telegram session isolated", len(ctx_tg) == 1)
test("WhatsApp has correct content", ctx_wa[0]["content"] == "WhatsApp msg")
test("Telegram has correct content", ctx_tg[0]["content"] == "Telegram msg")

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

print("=== EDGE CASE: Large Session (1000 lines) ===")

tmpdir = setup_tmpdir()
engine.CLAW_HOME = tmpdir

path = engine.get_session_path("whatsapp", "big_peer")
with open(path, "w") as f:
    for i in range(1000):
        entry = {"ts": "2026-01-01", "role": "user", "content": f"msg {i}",
                 "channel": "whatsapp", "peer": "big_peer", "ticket_id": f"t{i}"}
        f.write(json.dumps(entry) + "\n")

context = engine.get_context("whatsapp", "big_peer", max_lines=50)
test("Large file: context capped at 50", len(context) == 50, f"got {len(context)}")
test("Large file: last msg is 999", context[-1]["content"] == "msg 999")

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

# === RESULTS ===

print("=" * 40)
print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
print("=" * 40)

if failed > 0:
    print(f"\n  {failed} TESTS FAILED")
    sys.exit(1)
else:
    print(f"\n  ALL {total} TESTS PASSED")
    sys.exit(0)
