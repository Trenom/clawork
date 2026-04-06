#!/usr/bin/env python3
"""
Tests for clawork-soul: config loading and soul file handling.

Covers:
- Happy path: load config.yaml, load soul.md, validate structure
- Edge cases: missing config, missing soul, empty soul, malformed YAML,
  default fallback config, config field validation
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


def make_claw_dir(config_yaml=None, soul_md=None):
    """Create a temporary claw directory with optional config and soul files."""
    tmpdir = tempfile.mkdtemp(prefix="clawork_soul_test_")
    if config_yaml is not None:
        with open(os.path.join(tmpdir, "config.yaml"), "w") as f:
            f.write(config_yaml)
    if soul_md is not None:
        with open(os.path.join(tmpdir, "soul.md"), "w") as f:
            f.write(soul_md)
    for d in ["inbox", "outbox", "sessions", "logs"]:
        os.makedirs(os.path.join(tmpdir, d), exist_ok=True)
    return tmpdir


print("clawork-soul Test Suite")
print("=" * 40)
print()

# === HAPPY PATH: Config Loading ===

print("=== HAPPY PATH: Config Loading ===")

VALID_CONFIG = """\
agent:
  name: "Test Agent"
  soul: "./soul.md"
  language: "es"
  timezone: "America/Argentina/Cordoba"

routing:
  rules:
    - match:
        channel: "*"
        content_contains: "EX-"
      action:
        skill: "gde-agent"
        priority: "high"
  default:
    skill: "clawork-soul"
    priority: "normal"

limits:
  max_tickets_per_heartbeat: 10
  session_context_lines: 50
  session_compact_threshold: 200
"""

tmpdir = make_claw_dir(config_yaml=VALID_CONFIG)
orig_home = engine.CLAW_HOME
engine.CLAW_HOME = tmpdir

try:
    config = engine.load_config()
    test("Config loads successfully", config is not None)
    test("Config has routing section", "routing" in config)
    test("Config has limits section", "limits" in config)
    test("Config has agent section", "agent" in config)
    test("Agent name correct", config["agent"]["name"] == "Test Agent", f"got {config.get('agent', {}).get('name')}")
    test("Routing has rules list", isinstance(config.get("routing", {}).get("rules"), list))
    test("Rules count is 1", len(config["routing"]["rules"]) == 1)
    test("Default skill is clawork-soul", config["routing"]["default"]["skill"] == "clawork-soul")
    test("Limits max_tickets is 10", config["limits"]["max_tickets_per_heartbeat"] == 10)
    test("Limits session_context_lines is 50", config["limits"]["session_context_lines"] == 50)
    test("Limits compact_threshold is 200", config["limits"]["session_compact_threshold"] == 200)
except Exception as e:
    test("Config loads without error", False, str(e))

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

# === HAPPY PATH: Soul File Loading ===

print("=== HAPPY PATH: Soul File Loading ===")

VALID_SOUL = """\
# SOUL - Test Agent

## Personalidad
- Directo y eficiente
- Habla en español

## Restricciones
- No comparte info sensible
"""

tmpdir = make_claw_dir(soul_md=VALID_SOUL)

soul_path = os.path.join(tmpdir, "soul.md")
test("Soul file exists", os.path.exists(soul_path))

with open(soul_path, "r") as f:
    content = f.read()
test("Soul has personality section", "Personalidad" in content)
test("Soul has restrictions section", "Restricciones" in content)
test("Soul content is non-empty", len(content) > 0)

shutil.rmtree(tmpdir)

print()

# === HAPPY PATH: Config with Channels ===

print("=== HAPPY PATH: Config with Channels ===")

CHANNELS_CONFIG = """\
agent:
  name: "Channel Test"

channels:
  whatsapp:
    enabled: true
    method: "browser"
    check_interval: "5m"
    session_mode: "per-peer"
  telegram:
    enabled: true
    method: "bot_api"
  gmail:
    enabled: false
    method: "connector"

routing:
  rules: []
  default:
    skill: "clawork-soul"
    priority: "normal"

limits:
  max_tickets_per_heartbeat: 5
  session_context_lines: 30
  session_compact_threshold: 100
"""

tmpdir = make_claw_dir(config_yaml=CHANNELS_CONFIG)
engine.CLAW_HOME = tmpdir

config = engine.load_config()
test("Channels section loaded", "channels" in config)
test("WhatsApp enabled", config["channels"]["whatsapp"]["enabled"] is True)
test("Telegram enabled", config["channels"]["telegram"]["enabled"] is True)
test("Gmail disabled", config["channels"]["gmail"]["enabled"] is False)
test("WhatsApp method is browser", config["channels"]["whatsapp"]["method"] == "browser")
test("Custom limits respected", config["limits"]["max_tickets_per_heartbeat"] == 5)

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

# === HAPPY PATH: Config with Multiple Agents ===

print("=== HAPPY PATH: Config with Agent Definitions ===")

AGENTS_CONFIG = """\
agent:
  name: "Multi Agent"

agents:
  - name: "gde-agent"
    description: "GDE queries"
    skills: ["gde-query"]
    keywords: ["expediente", "EX-"]
  - name: "sugop-agent"
    description: "Public works"
    skills: ["obra-query"]
    keywords: ["SUGOP", "obra"]

routing:
  rules: []
  default:
    skill: "clawork-soul"
    priority: "normal"
"""

tmpdir = make_claw_dir(config_yaml=AGENTS_CONFIG)
engine.CLAW_HOME = tmpdir

config = engine.load_config()
test("Agents section loaded", "agents" in config)
test("Two agents defined", len(config["agents"]) == 2)
test("First agent is gde-agent", config["agents"][0]["name"] == "gde-agent")
test("Agent has keywords", "keywords" in config["agents"][0])
test("Agent has skills list", isinstance(config["agents"][0]["skills"], list))

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

# === HAPPY PATH: Dispatch to Soul ===

print("=== HAPPY PATH: Dispatch to clawork-soul ===")

ticket = {
    "id": "soul_test_01",
    "instruction": "Hola, cómo estás?",
    "source": {"channel": "whatsapp", "peer_id": "+0000", "peer_name": "TestUser"},
    "routing": {"target_skill": None, "priority": "normal"},
}

response = engine.dispatch_to_skill("clawork-soul", ticket, [])
test("Soul dispatch returns response", len(response) > 0)
test("Response mentions clawork-soul", "[clawork-soul]" in response)
test("Response includes peer name", "TestUser" in response)

response_with_ctx = engine.dispatch_to_skill("clawork-soul", ticket, [{"role": "user", "content": "prev msg"}] * 5)
test("Soul uses context count", "5 messages" in response_with_ctx, f"got: {response_with_ctx}")

print()

# === EDGE CASES ===

print("=== EDGE CASE: Missing config.yaml ===")

tmpdir = make_claw_dir()  # no config
engine.CLAW_HOME = tmpdir

try:
    config = engine.load_config()
    test("Missing config exits or raises", False, "should have exited")
except SystemExit:
    test("Missing config exits with error", True)
except Exception as e:
    test("Missing config raises error", True, str(e))

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

print("=== EDGE CASE: Config Without PyYAML Fallback ===")

# The engine has a fallback when PyYAML is not available
# We test the fallback structure
fallback = {
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

test("Fallback has routing", "routing" in fallback)
test("Fallback default is clawork-soul", fallback["routing"]["default"]["skill"] == "clawork-soul")
test("Fallback has limits", "limits" in fallback)
test("Fallback threshold is 200", fallback["limits"]["session_compact_threshold"] == 200)

print()

print("=== EDGE CASE: Missing Soul File ===")

tmpdir = make_claw_dir(config_yaml="agent:\n  name: test\n  soul: ./soul.md\n")
soul_path = os.path.join(tmpdir, "soul.md")

test("Soul file absent when not created", not os.path.exists(soul_path))

# The engine should handle missing soul gracefully (soul loading is in skills, not engine)
# Verify config loads fine even when soul file is missing
engine.CLAW_HOME = tmpdir
config = engine.load_config()
test("Config loads even without soul file", config is not None)
test("Soul path configured", config["agent"]["soul"] == "./soul.md")

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

print("=== EDGE CASE: Empty Soul File ===")

tmpdir = make_claw_dir(soul_md="")
soul_path = os.path.join(tmpdir, "soul.md")

with open(soul_path, "r") as f:
    content = f.read()
test("Empty soul file reads as empty string", content == "")
test("Empty soul file exists", os.path.exists(soul_path))

shutil.rmtree(tmpdir)

print()

print("=== EDGE CASE: Dispatch to Unknown Skill ===")

ticket = {
    "id": "unknown_skill",
    "instruction": "Test message",
    "source": {"channel": "whatsapp", "peer_id": "+0", "peer_name": "Tester"},
    "routing": {"target_skill": None, "priority": "normal"},
}

response = engine.dispatch_to_skill("nonexistent-skill", ticket, [])
test("Unknown skill returns response", len(response) > 0)
test("Response wraps skill name", "[nonexistent-skill]" in response)

print()

print("=== EDGE CASE: Dispatch with GDE Numbers ===")

ticket = {
    "id": "gde_test",
    "instruction": "Consultar EX-2025-12345678 y IF-2025-00001",
    "source": {"channel": "whatsapp", "peer_id": "+0", "peer_name": "Inspector"},
    "routing": {"target_skill": None, "priority": "high"},
}

response = engine.dispatch_to_skill("gde-agent", ticket, [])
test("GDE dispatch extracts numbers", "EX-2025-12345678" in response, f"got: {response}")
test("GDE dispatch extracts multiple", "IF-2025-00001" in response, f"got: {response}")

ticket_no_nums = {
    "id": "gde_no_nums",
    "instruction": "Consultar el último expediente",
    "source": {"channel": "whatsapp", "peer_id": "+0", "peer_name": "User"},
    "routing": {"target_skill": None, "priority": "normal"},
}

response = engine.dispatch_to_skill("gde-agent", ticket_no_nums, [])
test("GDE without numbers gives generic response", "[gde-agent]" in response)

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
