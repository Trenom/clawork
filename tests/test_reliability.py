#!/usr/bin/env python3
"""
Tests for reliability hardening: structured logging, retries, poison queue, metrics.

Covers:
- Structured JSON logging output format
- Exponential-backoff retry on dispatch failures
- Poison queue for malformed tickets (invalid JSON, missing fields)
- Metrics recording (dispatch_ok, dispatch_retry, dispatch_failed, heartbeat, quarantine)
- Dead-letter behaviour on permanent dispatch failure
"""

import json
import os
import shutil
import sys
import tempfile

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


def make_ticket(instruction="Hello", tid="test_001"):
    return {
        "id": tid,
        "status": "pending",
        "source": {"channel": "whatsapp", "peer_id": "+0000", "peer_name": "Test"},
        "instruction": instruction,
        "routing": {"target_skill": None, "priority": "normal"},
    }


print("clawork-reliability Test Suite")
print("=" * 50)
print()

# ============================================================
# STRUCTURED LOGGING
# ============================================================

print("=== Structured Logging: JSON format ===")

import io
import logging

handler = logging.StreamHandler(io.StringIO())
handler.setFormatter(engine._JsonFormatter())
test_logger = logging.getLogger("clawork.test_reliability")
test_logger.addHandler(handler)
test_logger.setLevel(logging.DEBUG)

test_logger.info("test message with key=%s", "value")
output = handler.stream.getvalue().strip()
try:
    log_entry = json.loads(output)
    test("Log output is valid JSON", True)
    test("Log has ts field", "ts" in log_entry)
    test("Log has level=INFO", log_entry.get("level") == "INFO")
    test("Log has logger field", "clawork.test_reliability" in log_entry.get("logger", ""))
    test("Log has formatted msg", "key=value" in log_entry.get("msg", ""))
except json.JSONDecodeError:
    test("Log output is valid JSON", False, f"got: {output}")
    test("Log has ts field", False)
    test("Log has level=INFO", False)
    test("Log has logger field", False)
    test("Log has formatted msg", False)

test_logger.removeHandler(handler)
print()

# ============================================================
# POISON QUEUE
# ============================================================

print("=== Poison Queue: Invalid JSON ===")

tmpdir = tempfile.mkdtemp(prefix="clawork_test_poison_")
orig_home = engine.CLAW_HOME
engine.CLAW_HOME = tmpdir
os.makedirs(os.path.join(tmpdir, "inbox"))

# Write invalid JSON file
bad_path = os.path.join(tmpdir, "inbox", "bad.json")
with open(bad_path, "w") as f:
    f.write("{not valid json!!")

# Write valid ticket
good_path = os.path.join(tmpdir, "inbox", "good.json")
with open(good_path, "w") as f:
    json.dump(make_ticket("valid", "good_001"), f)

tickets = engine.load_pending_tickets()
test("Valid ticket loaded", len(tickets) == 1 and tickets[0][0]["id"] == "good_001", f"got {len(tickets)} tickets")
test("Bad file removed from inbox", not os.path.exists(bad_path))
test("Bad file in poison dir", os.path.exists(os.path.join(tmpdir, "poison", "bad.json")))
test("Reason sidecar exists", os.path.exists(os.path.join(tmpdir, "poison", "bad.json.reason")))

if os.path.exists(os.path.join(tmpdir, "poison", "bad.json.reason")):
    with open(os.path.join(tmpdir, "poison", "bad.json.reason")) as f:
        reason = json.load(f)
    test("Reason has quarantined_at", "quarantined_at" in reason)
    test("Reason mentions Invalid JSON", "Invalid JSON" in reason.get("reason", ""), f"got: {reason.get('reason')}")

print()

print("=== Poison Queue: Missing required fields ===")

incomplete_path = os.path.join(tmpdir, "inbox", "incomplete.json")
with open(incomplete_path, "w") as f:
    json.dump({"status": "pending"}, f)  # no id or source

tickets = engine.load_pending_tickets()
test("Incomplete ticket quarantined", os.path.exists(os.path.join(tmpdir, "poison", "incomplete.json")))
test("Incomplete removed from inbox", not os.path.exists(incomplete_path))

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)
print()

# ============================================================
# RETRY LOGIC
# ============================================================

print("=== Retry: Succeeds on first attempt ===")

tmpdir = tempfile.mkdtemp(prefix="clawork_test_retry_")
orig_home = engine.CLAW_HOME
engine.CLAW_HOME = tmpdir
os.makedirs(os.path.join(tmpdir, "metrics"), exist_ok=True)

# Set up a local skill that succeeds
os.makedirs(os.path.join(tmpdir, "skills"))
with open(os.path.join(tmpdir, "skills", "ok.py"), "w") as f:
    f.write('def handle(ticket, context): return "ok"\n')

orig_registry = engine._skill_registry
engine._skill_registry = engine.SkillRegistry({
    "ok-skill": {"type": "local", "module": "skills/ok.py", "handler": "handle"},
})

ticket = make_ticket("test retry")
sleep_calls = []
result = engine._dispatch_with_retry("ok-skill", ticket, [], _sleep_fn=lambda s: sleep_calls.append(s))
test("First attempt succeeds", result == "ok", f"got '{result}'")
test("No sleep on success", len(sleep_calls) == 0)

print()

print("=== Retry: Fails then succeeds ===")

# Skill that fails twice then succeeds
call_count = [0]
with open(os.path.join(tmpdir, "skills", "flaky.py"), "w") as f:
    f.write("""
_count = 0
def handle(ticket, context):
    global _count
    _count += 1
    if _count <= 2:
        raise ConnectionError(f"transient error attempt {_count}")
    return "recovered"
""")

engine._skill_registry = engine.SkillRegistry({
    "flaky-skill": {"type": "local", "module": "skills/flaky.py", "handler": "handle"},
})

# Flaky local skill raises generic exceptions, not SkillDispatchError, so
# we need a skill that raises SkillDispatchError. Let's use a webhook pointing nowhere.
# Actually, local skills raise their own exceptions wrapped, but _dispatch_local doesn't
# catch ConnectionError — it propagates. Let me use a different approach:
# Register a wrapper that throws SkillDispatchError.

attempt_counter = [0]
def _mock_dispatch(skill, ticket, context):
    attempt_counter[0] += 1
    if attempt_counter[0] <= 2:
        raise engine.SkillDispatchError(f"transient error attempt {attempt_counter[0]}")
    return "recovered-after-retries"

# Temporarily replace dispatch_to_skill
orig_dispatch = engine.dispatch_to_skill
engine.dispatch_to_skill = _mock_dispatch

sleep_calls = []
result = engine._dispatch_with_retry("any-skill", ticket, [], _sleep_fn=lambda s: sleep_calls.append(s))
test("Recovered after retries", result == "recovered-after-retries", f"got '{result}'")
test("Slept twice (2 retries)", len(sleep_calls) == 2, f"got {len(sleep_calls)} sleeps")
test("First backoff is 1s", sleep_calls[0] == 1 if len(sleep_calls) >= 1 else False, f"got {sleep_calls}")
test("Second backoff is 4s", sleep_calls[1] == 4 if len(sleep_calls) >= 2 else False, f"got {sleep_calls}")

engine.dispatch_to_skill = orig_dispatch
print()

print("=== Retry: All attempts fail ===")

def _always_fail(skill, ticket, context):
    raise engine.SkillDispatchError("permanent failure")

engine.dispatch_to_skill = _always_fail
sleep_calls = []
try:
    engine._dispatch_with_retry("fail-skill", ticket, [], _sleep_fn=lambda s: sleep_calls.append(s))
    test("All retries exhausted raises", False, "no exception raised")
except engine.SkillDispatchError as e:
    test("All retries exhausted raises SkillDispatchError", "permanent failure" in str(e))
    test("Slept between attempts", len(sleep_calls) == 2, f"got {len(sleep_calls)} sleeps")

engine.dispatch_to_skill = orig_dispatch
engine._skill_registry = orig_registry
engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

# ============================================================
# METRICS
# ============================================================

print("=== Metrics: _record_metric writes to JSONL ===")

tmpdir = tempfile.mkdtemp(prefix="clawork_test_metrics_")
orig_home = engine.CLAW_HOME
engine.CLAW_HOME = tmpdir

engine._record_metric("test_metric", foo="bar", count=42)
engine._record_metric("test_metric", foo="baz", count=99)

metrics_path = os.path.join(tmpdir, "metrics", "engine.jsonl")
test("Metrics file created", os.path.exists(metrics_path))

if os.path.exists(metrics_path):
    with open(metrics_path) as f:
        lines = [json.loads(ln) for ln in f if ln.strip()]
    test("Two metric entries written", len(lines) == 2, f"got {len(lines)}")
    test("Metric has ts", "ts" in lines[0])
    test("Metric has type", lines[0]["metric"] == "test_metric")
    test("Metric has custom fields", lines[0]["foo"] == "bar" and lines[0]["count"] == 42)

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

# ============================================================
# DEAD-LETTER (process_ticket with failing dispatch)
# ============================================================

print("=== Dead-Letter: Failed ticket goes to outbox with error status ===")

tmpdir = tempfile.mkdtemp(prefix="clawork_test_deadletter_")
orig_home = engine.CLAW_HOME
engine.CLAW_HOME = tmpdir
os.makedirs(os.path.join(tmpdir, "inbox"))
os.makedirs(os.path.join(tmpdir, "outbox"))
os.makedirs(os.path.join(tmpdir, "sessions", "whatsapp"), exist_ok=True)
os.makedirs(os.path.join(tmpdir, "metrics"), exist_ok=True)

ticket = make_ticket("will fail", "dead_001")
ticket_path = os.path.join(tmpdir, "inbox", "dead_001.json")
with open(ticket_path, "w") as f:
    json.dump(ticket, f)

# Set up registry with a skill that always fails
orig_registry = engine._skill_registry
engine._skill_registry = engine.SkillRegistry({
    "clawork-soul": {"type": "webhook", "url": "http://127.0.0.1:1/nonexistent"},
})

config = {"routing": {"default": {"skill": "clawork-soul", "priority": "normal"}}}

try:
    engine.process_ticket(ticket, ticket_path, config)
    test("process_ticket raises on failure", False, "no exception")
except (engine.SkillDispatchError, Exception):
    test("process_ticket raises on failure", True)

# Check dead-letter in outbox
outbox_file = os.path.join(tmpdir, "outbox", "dead_001.json")
test("Dead-letter ticket in outbox", os.path.exists(outbox_file))
if os.path.exists(outbox_file):
    with open(outbox_file) as f:
        dead = json.load(f)
    test("Dead-letter status is error", dead["status"] == "error")
    test("Dead-letter result has error output", dead["result"]["status"] == "error")
test("Original removed from inbox", not os.path.exists(ticket_path))

engine._skill_registry = orig_registry
engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

# ============================================================
# RESULTS
# ============================================================

print("=" * 50)
print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
print("=" * 50)

if failed > 0:
    print(f"\n  {failed} TESTS FAILED")
    sys.exit(1)
else:
    print(f"\n  ALL {total} TESTS PASSED")
    sys.exit(0)
