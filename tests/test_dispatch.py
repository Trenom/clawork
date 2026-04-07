#!/usr/bin/env python3
"""
Tests for the skill dispatch system: registry, local/mcp/webhook handlers.

Covers:
- SkillRegistry construction, registration, and lookup
- Local dispatch (file-path module, dotted module, missing module/handler)
- MCP dispatch (success, HTTP errors, response parsing)
- Webhook dispatch (success, HTTP errors, header expansion)
- dispatch_to_skill integration (registered, unregistered, no registry)
- Environment variable expansion in config values
"""

import json
import os
import sys
import tempfile
import shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

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


def make_ticket(instruction="Hello", channel="whatsapp", peer_id="+0000", peer_name="Test"):
    return {
        "id": "test_ticket",
        "status": "pending",
        "source": {"channel": channel, "peer_id": peer_id, "peer_name": peer_name},
        "instruction": instruction,
        "routing": {"target_skill": None, "priority": "normal"},
    }


print("clawork-dispatch Test Suite")
print("=" * 50)
print()

# ============================================================
# SKILL REGISTRY
# ============================================================

print("=== SkillRegistry: Construction ===")

reg = engine.SkillRegistry({
    "my-skill": {"type": "local", "module": "my_mod.py", "handler": "run"},
    "mcp-skill": {"type": "mcp", "server_url": "http://localhost:9999"},
})
test("Registry has my-skill", "my-skill" in reg)
test("Registry has mcp-skill", "mcp-skill" in reg)
test("Registry does not have unknown", "unknown" not in reg)
test("names() returns both", set(reg.names()) == {"my-skill", "mcp-skill"})

defn = reg.get("my-skill")
test("get() returns definition", defn is not None and defn["type"] == "local")
test("get() unknown returns None", reg.get("nope") is None)

print()

print("=== SkillRegistry: Validation ===")

try:
    engine.SkillRegistry({"bad": {"module": "x"}})
    test("Missing type raises ValueError", False, "no exception raised")
except ValueError as e:
    test("Missing type raises ValueError", "missing required field 'type'" in str(e))

try:
    engine.SkillRegistry({"bad": {"type": "ftp"}})
    test("Unknown type raises ValueError", False, "no exception raised")
except ValueError as e:
    test("Unknown type raises ValueError", "unknown type" in str(e))

print()

# ============================================================
# LOCAL DISPATCH
# ============================================================

print("=== Local Dispatch: File-path module ===")

tmpdir = tempfile.mkdtemp(prefix="clawork_test_dispatch_")
orig_home = engine.CLAW_HOME
engine.CLAW_HOME = tmpdir

# Create a handler module
handler_dir = os.path.join(tmpdir, "skills", "test-skill")
os.makedirs(handler_dir)
with open(os.path.join(handler_dir, "handler.py"), "w") as f:
    f.write("""
def handle(ticket, context):
    return f"local-ok: {ticket['instruction']}"
""")

defn_local = {"type": "local", "module": "skills/test-skill/handler.py", "handler": "handle"}
ticket = make_ticket("ping")
result = engine._dispatch_local(defn_local, "test-skill", ticket, [])
test("Local file dispatch returns response", result == "local-ok: ping", f"got '{result}'")

print()

print("=== Local Dispatch: Custom handler name ===")

with open(os.path.join(handler_dir, "alt_handler.py"), "w") as f:
    f.write("""
def my_custom_fn(ticket, context):
    return f"custom: {len(context)} ctx"
""")

defn_alt = {"type": "local", "module": "skills/test-skill/alt_handler.py", "handler": "my_custom_fn"}
result = engine._dispatch_local(defn_alt, "test-skill", ticket, [{"role": "user", "content": "hi"}])
test("Custom handler name works", result == "custom: 1 ctx", f"got '{result}'")

print()

print("=== Local Dispatch: Missing module ===")

defn_missing = {"type": "local", "module": "skills/nonexistent.py"}
try:
    engine._dispatch_local(defn_missing, "ghost", ticket, [])
    test("Missing module raises SkillDispatchError", False, "no exception")
except engine.SkillDispatchError as e:
    test("Missing module raises SkillDispatchError", "not found" in str(e))

print()

print("=== Local Dispatch: Missing handler function ===")

with open(os.path.join(handler_dir, "no_handle.py"), "w") as f:
    f.write("x = 42\n")

defn_no_fn = {"type": "local", "module": "skills/test-skill/no_handle.py"}
try:
    engine._dispatch_local(defn_no_fn, "test-skill", ticket, [])
    test("Missing handler fn raises SkillDispatchError", False, "no exception")
except engine.SkillDispatchError as e:
    test("Missing handler fn raises SkillDispatchError", "not found in module" in str(e))

print()

print("=== Local Dispatch: No module configured ===")

try:
    engine._dispatch_local({"type": "local"}, "empty", ticket, [])
    test("No module raises SkillDispatchError", False, "no exception")
except engine.SkillDispatchError as e:
    test("No module raises SkillDispatchError", "no 'module'" in str(e))

engine.CLAW_HOME = orig_home
shutil.rmtree(tmpdir)

print()

# ============================================================
# MCP DISPATCH (with test HTTP server)
# ============================================================

print("=== MCP Dispatch: Success ===")


class MCPHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/tools/test_tool/invoke":
            resp = {"content": [{"type": "text", "text": f"mcp-ok: {body['ticket']['instruction']}"}]}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())
        elif self.path == "/tools/error_tool/invoke":
            self.send_error(500, "Internal Server Error")
        elif self.path == "/tools/plain_tool/invoke":
            resp = {"text": "plain-text-response"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # suppress logs during tests


server = HTTPServer(("127.0.0.1", 0), MCPHandler)
port = server.server_address[1]
server_thread = threading.Thread(target=server.serve_forever, daemon=True)
server_thread.start()

try:
    defn_mcp = {"type": "mcp", "server_url": f"http://127.0.0.1:{port}", "tool_name": "test_tool"}
    ticket = make_ticket("hello mcp")
    result = engine._dispatch_mcp(defn_mcp, "test-mcp", ticket, [])
    test("MCP dispatch returns text from content array", result == "mcp-ok: hello mcp", f"got '{result}'")

    print()
    print("=== MCP Dispatch: Plain text response ===")

    defn_plain = {"type": "mcp", "server_url": f"http://127.0.0.1:{port}", "tool_name": "plain_tool"}
    result = engine._dispatch_mcp(defn_plain, "plain-mcp", ticket, [])
    test("MCP plain text field extracted", result == "plain-text-response", f"got '{result}'")

    print()
    print("=== MCP Dispatch: Server error ===")

    defn_err = {"type": "mcp", "server_url": f"http://127.0.0.1:{port}", "tool_name": "error_tool"}
    try:
        engine._dispatch_mcp(defn_err, "err-mcp", ticket, [])
        test("MCP server error raises SkillDispatchError", False, "no exception")
    except engine.SkillDispatchError as e:
        test("MCP server error raises SkillDispatchError", "HTTP 500" in str(e))

    print()
    print("=== MCP Dispatch: Missing server_url ===")

    try:
        engine._dispatch_mcp({"type": "mcp"}, "no-url", ticket, [])
        test("Missing server_url raises error", False, "no exception")
    except engine.SkillDispatchError as e:
        test("Missing server_url raises error", "no 'server_url'" in str(e))

finally:
    server.shutdown()

print()

# ============================================================
# WEBHOOK DISPATCH (with test HTTP server)
# ============================================================

print("=== Webhook Dispatch: Success ===")


class WebhookHandler(BaseHTTPRequestHandler):
    last_headers = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        WebhookHandler.last_headers = dict(self.headers)

        if self.path == "/api/skill":
            resp = {"output": f"webhook-ok: {body['ticket']['instruction']}"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())
        elif self.path == "/api/error":
            self.send_error(502, "Bad Gateway")
        elif self.path == "/api/raw":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"raw-text-body")
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


wh_server = HTTPServer(("127.0.0.1", 0), WebhookHandler)
wh_port = wh_server.server_address[1]
wh_thread = threading.Thread(target=wh_server.serve_forever, daemon=True)
wh_thread.start()

try:
    defn_wh = {"type": "webhook", "url": f"http://127.0.0.1:{wh_port}/api/skill"}
    ticket = make_ticket("hello webhook")
    result = engine._dispatch_webhook(defn_wh, "test-wh", ticket, [])
    test("Webhook dispatch returns output field", result == "webhook-ok: hello webhook", f"got '{result}'")

    print()
    print("=== Webhook Dispatch: Custom headers with env expansion ===")

    os.environ["TEST_WH_TOKEN"] = "secret123"
    defn_wh_headers = {
        "type": "webhook",
        "url": f"http://127.0.0.1:{wh_port}/api/skill",
        "headers": {"Authorization": "Bearer {env:TEST_WH_TOKEN}", "X-Custom": "static-val"},
    }
    result = engine._dispatch_webhook(defn_wh_headers, "test-wh", ticket, [])
    test("Webhook with headers works", result == "webhook-ok: hello webhook", f"got '{result}'")
    test("Auth header expanded", WebhookHandler.last_headers.get("Authorization") == "Bearer secret123",
         f"got '{WebhookHandler.last_headers.get('Authorization')}'")
    test("Custom header passed", WebhookHandler.last_headers.get("X-Custom") == "static-val")
    del os.environ["TEST_WH_TOKEN"]

    print()
    print("=== Webhook Dispatch: Raw text response ===")

    defn_raw = {"type": "webhook", "url": f"http://127.0.0.1:{wh_port}/api/raw"}
    result = engine._dispatch_webhook(defn_raw, "raw-wh", ticket, [])
    test("Webhook raw text fallback", result == "raw-text-body", f"got '{result}'")

    print()
    print("=== Webhook Dispatch: Server error ===")

    defn_wh_err = {"type": "webhook", "url": f"http://127.0.0.1:{wh_port}/api/error"}
    try:
        engine._dispatch_webhook(defn_wh_err, "err-wh", ticket, [])
        test("Webhook server error raises SkillDispatchError", False, "no exception")
    except engine.SkillDispatchError as e:
        test("Webhook server error raises SkillDispatchError", "HTTP 502" in str(e))

    print()
    print("=== Webhook Dispatch: Missing url ===")

    try:
        engine._dispatch_webhook({"type": "webhook"}, "no-url", ticket, [])
        test("Missing url raises error", False, "no exception")
    except engine.SkillDispatchError as e:
        test("Missing url raises error", "no 'url'" in str(e))

finally:
    wh_server.shutdown()

print()

# ============================================================
# ENV EXPANSION
# ============================================================

print("=== Environment Variable Expansion ===")

os.environ["TEST_VAR_A"] = "alpha"
os.environ["TEST_VAR_B"] = "beta"

test("Single var expanded", engine._expand_env_vars("pre-{env:TEST_VAR_A}-post") == "pre-alpha-post")
test("Multiple vars expanded", engine._expand_env_vars("{env:TEST_VAR_A}/{env:TEST_VAR_B}") == "alpha/beta")
test("Missing var becomes empty", engine._expand_env_vars("{env:NONEXISTENT_VAR_XYZ}") == "")
test("No placeholders unchanged", engine._expand_env_vars("plain-string") == "plain-string")

del os.environ["TEST_VAR_A"]
del os.environ["TEST_VAR_B"]

print()

# ============================================================
# DISPATCH_TO_SKILL INTEGRATION
# ============================================================

print("=== dispatch_to_skill: Stub fallback (no registry) ===")

orig_registry = engine._skill_registry
engine._skill_registry = None

ticket = make_ticket("test-inst", peer_name="Alice")
result = engine.dispatch_to_skill("some-skill", ticket, [])
test("No registry -> stub response", "(stub)" in result and "Alice" in result, f"got '{result}'")

print()

print("=== dispatch_to_skill: Unregistered skill ===")

engine._skill_registry = engine.SkillRegistry({})
result = engine.dispatch_to_skill("unknown-skill", ticket, [{"role": "user", "content": "x"}])
test("Unregistered skill -> stub response", "(stub)" in result, f"got '{result}'")

print()

print("=== dispatch_to_skill: Registered local skill ===")

tmpdir = tempfile.mkdtemp(prefix="clawork_test_int_")
orig_home = engine.CLAW_HOME
engine.CLAW_HOME = tmpdir

os.makedirs(os.path.join(tmpdir, "skills"))
with open(os.path.join(tmpdir, "skills", "echo.py"), "w") as f:
    f.write("""
def handle(ticket, context):
    return "integrated-ok"
""")

engine._skill_registry = engine.SkillRegistry({
    "echo-skill": {"type": "local", "module": "skills/echo.py", "handler": "handle"},
})

result = engine.dispatch_to_skill("echo-skill", ticket, [])
test("Registered local skill dispatches correctly", result == "integrated-ok", f"got '{result}'")

engine.CLAW_HOME = orig_home
engine._skill_registry = orig_registry
shutil.rmtree(tmpdir)

print()

# ============================================================
# LOAD SKILL REGISTRY
# ============================================================

print("=== load_skill_registry: From config ===")

reg = engine.load_skill_registry({
    "skills": {
        "a": {"type": "local", "module": "a.py"},
        "b": {"type": "webhook", "url": "http://example.com"},
    }
})
test("Config skills loaded", set(reg.names()) == {"a", "b"})

print()

print("=== load_skill_registry: skills.yaml override ===")

tmpdir = tempfile.mkdtemp(prefix="clawork_test_reg_")
orig_home = engine.CLAW_HOME
engine.CLAW_HOME = tmpdir

try:
    import yaml
    with open(os.path.join(tmpdir, "skills.yaml"), "w") as f:
        yaml.dump({"c": {"type": "mcp", "server_url": "http://localhost:1234"}}, f)

    reg = engine.load_skill_registry({"skills": {"a": {"type": "local", "module": "a.py"}}})
    test("skills.yaml entries merged", "c" in reg)
    test("config.yaml entries preserved", "a" in reg)
except ImportError:
    test("skills.yaml test skipped (no PyYAML)", True)

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
