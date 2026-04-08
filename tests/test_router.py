#!/usr/bin/env python3
"""
Tests for clawork-router: ticket routing rule matching.

Covers:
- Happy path: content_contains matching, channel filtering, default fallback
- Edge cases: empty rules, overlapping rules, case insensitivity, special chars,
  wildcard channels, peer filtering, first-match-wins behavior
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


def make_ticket(instruction, channel="whatsapp", peer_id="+0000", peer_name="Test"):
    return {
        "id": "test_ticket",
        "status": "pending",
        "source": {"channel": channel, "peer_id": peer_id, "peer_name": peer_name},
        "instruction": instruction,
        "routing": {"target_skill": None, "priority": "normal"},
    }


# --- Standard config with routing rules ---

STANDARD_CONFIG = {
    "routing": {
        "rules": [
            {
                "match": {"channel": "*", "content_contains": "expediente|EX-|IF-|NO-|PV-|RE-"},
                "action": {"skill": "gde-agent", "priority": "high"},
            },
            {
                "match": {"channel": "*", "content_contains": "SUGOP|obra|certificación|redeterminación"},
                "action": {"skill": "sugop-agent", "priority": "normal"},
            },
            {
                "match": {"channel": "*", "content_contains": "openclaw|OpenClaw|agente local"},
                "action": {"skill": "openclaw-bridge", "priority": "normal"},
            },
        ],
        "default": {"skill": "clawork-soul", "priority": "normal"},
    }
}

print("clawork-router Test Suite")
print("=" * 40)
print()

# === HAPPY PATH ===

print("=== HAPPY PATH: Content Matching ===")

t = make_ticket("Necesito el expediente EX-2025-12345")
action, rule = engine.route_ticket(t, STANDARD_CONFIG)
test("EX- keyword routes to gde-agent", action["skill"] == "gde-agent", f"got {action['skill']}")
test("EX- priority is high", action["priority"] == "high", f"got {action['priority']}")

t = make_ticket("Consulta sobre IF-2025-00001")
action, rule = engine.route_ticket(t, STANDARD_CONFIG)
test("IF- keyword routes to gde-agent", action["skill"] == "gde-agent", f"got {action['skill']}")

t = make_ticket("Estado de la obra SUGOP-123")
action, rule = engine.route_ticket(t, STANDARD_CONFIG)
test("SUGOP keyword routes to sugop-agent", action["skill"] == "sugop-agent", f"got {action['skill']}")

t = make_ticket("Consultar certificación de obra")
action, rule = engine.route_ticket(t, STANDARD_CONFIG)
test("certificación routes to sugop-agent", action["skill"] == "sugop-agent", f"got {action['skill']}")

t = make_ticket("Conectar con OpenClaw")
action, rule = engine.route_ticket(t, STANDARD_CONFIG)
test("OpenClaw routes to openclaw-bridge", action["skill"] == "openclaw-bridge", f"got {action['skill']}")

t = make_ticket("Hola, cómo estás?")
action, rule = engine.route_ticket(t, STANDARD_CONFIG)
test("Generic message falls to default", action["skill"] == "clawork-soul", f"got {action['skill']}")
test("Default rule description", rule == "default", f"got {rule}")

print()

# === HAPPY PATH: Channel Filtering ===

print("=== HAPPY PATH: Channel Filtering ===")

channel_config = {
    "routing": {
        "rules": [
            {
                "match": {"channel": "telegram", "content_contains": "urgent"},
                "action": {"skill": "urgent-handler", "priority": "critical"},
            },
            {
                "match": {"channel": "*", "content_contains": "urgent"},
                "action": {"skill": "general-urgent", "priority": "high"},
            },
        ],
        "default": {"skill": "clawork-soul", "priority": "normal"},
    }
}

t = make_ticket("This is urgent!", channel="telegram")
action, _ = engine.route_ticket(t, channel_config)
test("Telegram urgent -> urgent-handler", action["skill"] == "urgent-handler", f"got {action['skill']}")

t = make_ticket("This is urgent!", channel="whatsapp")
action, _ = engine.route_ticket(t, channel_config)
test("WhatsApp urgent -> general-urgent (channel mismatch)", action["skill"] == "general-urgent", f"got {action['skill']}")

t = make_ticket("This is urgent!", channel="gmail")
action, _ = engine.route_ticket(t, channel_config)
test("Gmail urgent -> general-urgent", action["skill"] == "general-urgent", f"got {action['skill']}")

print()

# === HAPPY PATH: Peer Filtering ===

print("=== HAPPY PATH: Peer Filtering ===")

peer_config = {
    "routing": {
        "rules": [
            {
                "match": {"channel": "*", "peer": "+5491155555555"},
                "action": {"skill": "vip-handler", "priority": "high"},
            },
        ],
        "default": {"skill": "clawork-soul", "priority": "normal"},
    }
}

t = make_ticket("Hello", peer_id="+5491155555555")
action, _ = engine.route_ticket(t, peer_config)
test("VIP peer routes to vip-handler", action["skill"] == "vip-handler", f"got {action['skill']}")

t = make_ticket("Hello", peer_id="+0000000000")
action, _ = engine.route_ticket(t, peer_config)
test("Non-VIP peer falls to default", action["skill"] == "clawork-soul", f"got {action['skill']}")

print()

# === HAPPY PATH: Priority Ordering ===

print("=== HAPPY PATH: Priority Ordering ===")

tmpdir = tempfile.mkdtemp(prefix="clawork_test_")
orig_home = engine.CLAW_HOME
engine.CLAW_HOME = tmpdir

os.makedirs(os.path.join(tmpdir, "inbox"))

def write_ticket(tid, priority, created="2026-04-01T10:00:00"):
    ticket = {
        "id": tid, "status": "pending", "created": created,
        "source": {"channel": "whatsapp", "peer_id": "+0", "peer_name": "T"},
        "instruction": "test", "routing": {"priority": priority},
    }
    with open(os.path.join(tmpdir, "inbox", f"{tid}.json"), "w") as f:
        json.dump(ticket, f)

write_ticket("t_low", "low")
write_ticket("t_crit", "critical")
write_ticket("t_norm", "normal")
write_ticket("t_high", "high")

tickets = engine.load_pending_tickets()
prios = [t[0]["routing"]["priority"] for t in tickets]
test("Critical first in queue", prios[0] == "critical", f"got {prios}")
test("High second in queue", prios[1] == "high", f"got {prios}")
test("Normal third in queue", prios[2] == "normal", f"got {prios}")
test("Low last in queue", prios[3] == "low", f"got {prios}")

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

# === EDGE CASES ===

print("=== EDGE CASE: Empty Rules ===")

empty_config = {"routing": {"rules": [], "default": {"skill": "clawork-soul", "priority": "normal"}}}
t = make_ticket("Anything at all")
action, rule = engine.route_ticket(t, empty_config)
test("Empty rules -> default", action["skill"] == "clawork-soul", f"got {action['skill']}")
test("Rule desc is 'default'", rule == "default", f"got {rule}")

print()

print("=== EDGE CASE: Case Insensitivity ===")

t = make_ticket("tengo un EXPEDIENTE para consultar")
action, _ = engine.route_ticket(t, STANDARD_CONFIG)
test("EXPEDIENTE (uppercase) matches", action["skill"] == "gde-agent", f"got {action['skill']}")

t = make_ticket("necesito ver el ex-2025-99999")
action, _ = engine.route_ticket(t, STANDARD_CONFIG)
test("ex- (lowercase) matches EX-", action["skill"] == "gde-agent", f"got {action['skill']}")

t = make_ticket("consultar Sugop estado")
action, _ = engine.route_ticket(t, STANDARD_CONFIG)
test("Sugop (mixed case) matches SUGOP", action["skill"] == "sugop-agent", f"got {action['skill']}")

print()

print("=== EDGE CASE: First Match Wins ===")

overlap_config = {
    "routing": {
        "rules": [
            {"match": {"channel": "*", "content_contains": "EX-"}, "action": {"skill": "first-skill"}},
            {"match": {"channel": "*", "content_contains": "EX-"}, "action": {"skill": "second-skill"}},
        ],
        "default": {"skill": "clawork-soul", "priority": "normal"},
    }
}

t = make_ticket("Document EX-2025-001")
action, _ = engine.route_ticket(t, overlap_config)
test("First matching rule wins", action["skill"] == "first-skill", f"got {action['skill']}")

print()

print("=== EDGE CASE: Empty Instruction ===")

t = make_ticket("")
action, rule = engine.route_ticket(t, STANDARD_CONFIG)
test("Empty instruction -> default", action["skill"] == "clawork-soul", f"got {action['skill']}")

print()

print("=== EDGE CASE: Special Characters in Content ===")

t = make_ticket("EX-2025-12345!@#$%^&*()")
action, _ = engine.route_ticket(t, STANDARD_CONFIG)
test("Special chars don't break matching", action["skill"] == "gde-agent", f"got {action['skill']}")

t = make_ticket("Consulta sobre redeterminación (precio ajustado)")
action, _ = engine.route_ticket(t, STANDARD_CONFIG)
test("Accented chars match", action["skill"] == "sugop-agent", f"got {action['skill']}")

print()

print("=== EDGE CASE: Missing Config Fields ===")

minimal_config = {"routing": {}}
t = make_ticket("Hello")
action, rule = engine.route_ticket(t, minimal_config)
test("Missing rules key -> default fallback", action["skill"] == "clawork-soul", f"got {action['skill']}")

no_routing_config = {}
t = make_ticket("Hello")
action, rule = engine.route_ticket(t, no_routing_config)
test("Missing routing key -> default fallback", action["skill"] == "clawork-soul", f"got {action['skill']}")

print()

print("=== EDGE CASE: Malformed Ticket in Inbox ===")

tmpdir = tempfile.mkdtemp(prefix="clawork_test_")
orig_home = engine.CLAW_HOME
engine.CLAW_HOME = tmpdir

os.makedirs(os.path.join(tmpdir, "inbox"))

with open(os.path.join(tmpdir, "inbox", "bad.json"), "w") as f:
    f.write("{not valid json!!")

with open(os.path.join(tmpdir, "inbox", "good.json"), "w") as f:
    json.dump({"id": "good", "status": "pending", "created": "2026-01-01", "routing": {"priority": "normal"},
               "source": {"channel": "whatsapp", "peer_id": "+0", "peer_name": "T"}}, f)

tickets = engine.load_pending_tickets()
test("Malformed ticket skipped, valid loaded", len(tickets) == 1, f"got {len(tickets)}")
test("Valid ticket loaded correctly", tickets[0][0]["id"] == "good" if tickets else False)

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

print("=== EDGE CASE: Very Long Instruction ===")

t = make_ticket("EX-2025-00001 " + "x" * 10000)
action, _ = engine.route_ticket(t, STANDARD_CONFIG)
test("Long instruction still matches", action["skill"] == "gde-agent", f"got {action['skill']}")

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
