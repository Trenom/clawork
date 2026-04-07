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

Dependencies:
    - PyYAML (required) — install with `pip install pyyaml`
    - tzdata (recommended on Windows) — for IANA timezone names
"""

import json
import glob
import importlib
import importlib.util
import re
import os
import shutil
import sys
import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

try:
    from zoneinfo import ZoneInfo  # py>=3.9
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

# --- Config ---

CLAW_HOME = os.environ.get("CLAW_HOME", os.path.expanduser("~/claw"))
DEFAULT_TZ_NAME = "UTC"

# Resolved at load_config() time. Falls back to UTC if zoneinfo unavailable.
_RUNTIME_TZ: timezone = timezone.utc

# --- Structured Logging ---


class _JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(_RUNTIME_TZ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            entry["error"] = str(record.exc_info[1])
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(level_name: str = "INFO"):
    """Configure structured JSON logging to stderr."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger("clawork")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    return root


# Bootstrap with default level; load_config() may override.
_root_logger = setup_logging()


# --- Metrics ---


def _record_metric(metric_type: str, **fields):
    """Append a metric entry to ~/claw/metrics/engine.jsonl."""
    metrics_dir = os.path.join(CLAW_HOME, "metrics")
    os.makedirs(metrics_dir, exist_ok=True)
    entry = {"ts": now_iso(), "metric": metric_type, **fields}
    with open(os.path.join(metrics_dir, "engine.jsonl"), "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def now_iso() -> str:
    return datetime.now(_RUNTIME_TZ).isoformat()


def _resolve_timezone(name: str):
    """Resolve a timezone name to a tzinfo. Falls back to UTC on failure."""
    if not name:
        return timezone.utc
    if ZoneInfo is None:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except Exception:
        logging.getLogger("clawork").warning("Unknown timezone '%s', falling back to UTC", name)
        return timezone.utc


def load_config():
    """Load config.yaml and initialize the skill registry.

    PyYAML is required — fails loudly if missing.
    """
    global _RUNTIME_TZ, _skill_registry

    config_path = os.path.join(CLAW_HOME, "config.yaml")
    if not os.path.exists(config_path):
        print(f"ERROR: {config_path} not found")
        sys.exit(1)

    try:
        import yaml
    except ImportError:
        print("ERROR: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    with open(config_path, "r") as f:
        config = yaml.safe_load(f) or {}

    tz_name = (config.get("agent", {}) or {}).get("timezone") or DEFAULT_TZ_NAME
    _RUNTIME_TZ = _resolve_timezone(tz_name)

    # Reconfigure logging with level from config
    log_level = (config.get("agent", {}) or {}).get("log_level", "INFO")
    setup_logging(log_level)

    _skill_registry = load_skill_registry(config)
    if _skill_registry.names():
        logger.info("Skill registry loaded: %s", ", ".join(_skill_registry.names()))

    return config


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


def _quarantine_ticket(ticket_path: str, reason: str):
    """Move a malformed ticket to ~/claw/poison/ with a reason sidecar."""
    poison_dir = os.path.join(CLAW_HOME, "poison")
    os.makedirs(poison_dir, exist_ok=True)
    basename = os.path.basename(ticket_path)
    dest = os.path.join(poison_dir, basename)
    shutil.move(ticket_path, dest)
    reason_path = dest + ".reason"
    with open(reason_path, "w") as f:
        json.dump({"quarantined_at": now_iso(), "reason": str(reason)}, f, ensure_ascii=False)
    logger.warning("Quarantined malformed ticket %s: %s", basename, reason)
    _record_metric("ticket_quarantined", file=basename, reason=str(reason))


def load_pending_tickets():
    """Load all pending tickets from inbox, sorted by priority then creation time.

    Malformed tickets are moved to ~/claw/poison/ instead of silently skipping.
    """
    inbox = os.path.join(CLAW_HOME, "inbox")
    tickets = []

    for f in glob.glob(os.path.join(inbox, "*.json")):
        try:
            with open(f, "r") as fh:
                ticket = json.load(fh)
            # Validate required fields
            if not isinstance(ticket, dict) or "id" not in ticket or "source" not in ticket:
                _quarantine_ticket(f, "Missing required fields (id, source)")
                continue
            if ticket.get("status") == "pending":
                tickets.append((ticket, f))
        except json.JSONDecodeError as e:
            _quarantine_ticket(f, f"Invalid JSON: {e}")
        except (KeyError, TypeError) as e:
            _quarantine_ticket(f, f"Malformed structure: {e}")

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
    archive_name = f"{channel}_{peer_id}_{datetime.now(_RUNTIME_TZ).strftime('%Y%m%d_%H%M%S')}.jsonl"
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

    logger.info("Session compacted: channel=%s peer=%s old=%d recent=%d",
                channel, peer_id, len(old_lines), len(recent_lines))


# --- Ticket Processing ---

# Default retry settings for dispatch_to_skill
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_BASE = 1  # seconds; delays are 1s, 4s, 16s (base * 4^attempt)
RETRY_BACKOFF_MULTIPLIER = 4


def _dispatch_with_retry(skill: str, ticket: dict, context: list[dict],
                         max_attempts: int = RETRY_MAX_ATTEMPTS,
                         _sleep_fn=time.sleep) -> str:
    """Call dispatch_to_skill with exponential backoff on transient errors.

    Retries on SkillDispatchError (network/HTTP failures).  Permanent errors
    (SkillNotFoundError, ValueError) are raised immediately.
    """
    last_err = None
    for attempt in range(max_attempts):
        try:
            t0 = time.monotonic()
            result = dispatch_to_skill(skill, ticket, context)
            latency_ms = int((time.monotonic() - t0) * 1000)
            _record_metric("dispatch_ok", skill=skill, ticket_id=ticket.get("id", "?"),
                           attempt=attempt + 1, latency_ms=latency_ms)
            return result
        except SkillDispatchError as exc:
            last_err = exc
            delay = RETRY_BACKOFF_BASE * (RETRY_BACKOFF_MULTIPLIER ** attempt)
            logger.warning("Dispatch attempt %d/%d for skill '%s' failed: %s (retry in %ds)",
                           attempt + 1, max_attempts, skill, exc, delay)
            _record_metric("dispatch_retry", skill=skill, ticket_id=ticket.get("id", "?"),
                           attempt=attempt + 1, error=str(exc))
            if attempt < max_attempts - 1:
                _sleep_fn(delay)

    # All retries exhausted
    _record_metric("dispatch_failed", skill=skill, ticket_id=ticket.get("id", "?"),
                   attempts=max_attempts, error=str(last_err))
    raise last_err  # type: ignore[misc]


def process_ticket(ticket, ticket_path, config):
    """Process a single ticket: route, generate response, save session.

    Uses exponential-backoff retry for skill dispatch.  On permanent failure
    the ticket is moved to outbox with error status (dead-letter).
    """
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

    try:
        response = _dispatch_with_retry(skill, ticket, context)
    except (SkillDispatchError, SkillNotFoundError) as exc:
        # Dead-letter: write failed ticket to outbox with error status
        logger.error("Ticket %s failed after retries: %s", ticket_id, exc)
        ticket["status"] = "error"
        ticket["result"] = {
            "status": "error",
            "output": str(exc),
            "files": [],
            "reply_sent": False,
            "completed_at": now_iso(),
        }
        ticket["updated"] = now_iso()
        outbox_path = os.path.join(CLAW_HOME, "outbox", os.path.basename(ticket_path))
        os.makedirs(os.path.dirname(outbox_path), exist_ok=True)
        with open(outbox_path, "w") as f:
            json.dump(ticket, f, indent=2, ensure_ascii=False)
        os.remove(ticket_path)
        raise

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
    os.makedirs(os.path.dirname(outbox_path), exist_ok=True)
    with open(outbox_path, "w") as f:
        json.dump(ticket, f, indent=2, ensure_ascii=False)

    os.remove(ticket_path)
    return skill, rule, response


# --- Skill Registry & Dispatch ---

logger = logging.getLogger("clawork.dispatch")


class SkillNotFoundError(Exception):
    """Raised when a skill name is not in the registry."""


class SkillDispatchError(Exception):
    """Raised when a skill handler fails during execution."""


class SkillRegistry:
    """Registry that maps skill names to dispatch handlers.

    Loads skill definitions from either:
    - A standalone ``skills.yaml`` file in CLAW_HOME, or
    - The ``skills`` key inside the main ``config.yaml``.

    Each entry has a ``type`` (``local``, ``mcp``, or ``webhook``) and
    type-specific configuration.  See docs/dispatch.md for the full schema.
    """

    def __init__(self, skills_config: dict | None = None):
        self._handlers: dict[str, dict] = {}
        if skills_config:
            for name, defn in skills_config.items():
                self.register(name, defn)

    def register(self, name: str, defn: dict):
        """Register a skill definition."""
        if "type" not in defn:
            raise ValueError(f"Skill '{name}' is missing required field 'type'")
        if defn["type"] not in ("local", "mcp", "webhook"):
            raise ValueError(f"Skill '{name}' has unknown type '{defn['type']}'")
        self._handlers[name] = dict(defn)

    def get(self, name: str) -> dict | None:
        return self._handlers.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._handlers

    def names(self) -> list[str]:
        return list(self._handlers.keys())


def load_skill_registry(config: dict) -> SkillRegistry:
    """Build a SkillRegistry from config and/or a standalone skills.yaml file.

    Precedence: entries in ``skills.yaml`` override same-name entries from
    ``config.yaml["skills"]``.
    """
    skills_cfg: dict = dict(config.get("skills", {}) or {})

    skills_yaml_path = os.path.join(CLAW_HOME, "skills.yaml")
    if os.path.exists(skills_yaml_path):
        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML needed to load skills.yaml; skipping")
        else:
            with open(skills_yaml_path, "r") as f:
                extra = yaml.safe_load(f) or {}
            for name, defn in extra.items():
                skills_cfg[name] = defn

    return SkillRegistry(skills_cfg)


# ---- Dispatch handlers per type ----

def _dispatch_local(defn: dict, skill: str, ticket: dict, context: list[dict]) -> str:
    """Dispatch to a local Python handler.

    Definition fields:
        module : str  — dotted module path *or* file path relative to CLAW_HOME
        handler: str  — function name inside the module (default ``handle``)
    """
    module_ref = defn.get("module", "")
    handler_name = defn.get("handler", "handle")

    if not module_ref:
        raise SkillDispatchError(f"Local skill '{skill}' has no 'module' configured")

    # Support file-path references (relative to CLAW_HOME)
    if module_ref.endswith(".py") or os.sep in module_ref or "/" in module_ref:
        module_path = os.path.join(CLAW_HOME, module_ref)
        if not os.path.isfile(module_path):
            raise SkillDispatchError(f"Local skill '{skill}': module file not found: {module_path}")
        spec = importlib.util.spec_from_file_location(f"clawork_skill_{skill}", module_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    else:
        # Dotted module path
        try:
            mod = importlib.import_module(module_ref)
        except ImportError as exc:
            raise SkillDispatchError(f"Local skill '{skill}': cannot import module '{module_ref}': {exc}") from exc

    fn = getattr(mod, handler_name, None)
    if fn is None or not callable(fn):
        raise SkillDispatchError(f"Local skill '{skill}': handler '{handler_name}' not found in module")

    return fn(ticket, context)


def _dispatch_mcp(defn: dict, skill: str, ticket: dict, context: list[dict]) -> str:
    """Dispatch to an MCP tool exposed by the host Cowork server.

    Definition fields:
        server_url : str  — base URL of the MCP server (e.g. http://localhost:8080)
        tool_name  : str  — name of the MCP tool to invoke
        timeout    : int  — request timeout in seconds (default 30)
    """
    server_url = defn.get("server_url", "")
    tool_name = defn.get("tool_name", skill)
    timeout = int(defn.get("timeout", 30))

    if not server_url:
        raise SkillDispatchError(f"MCP skill '{skill}' has no 'server_url' configured")

    url = f"{server_url.rstrip('/')}/tools/{tool_name}/invoke"

    payload = json.dumps({
        "ticket": ticket,
        "context": context,
    }, ensure_ascii=False).encode("utf-8")

    req = Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")

    # Forward env-based auth if configured
    auth_header = defn.get("auth_header")
    if auth_header:
        req.add_header("Authorization", _expand_env_vars(auth_header))

    try:
        with urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raise SkillDispatchError(f"MCP skill '{skill}': HTTP {exc.code} from {url}") from exc
    except (URLError, OSError) as exc:
        raise SkillDispatchError(f"MCP skill '{skill}': connection error to {url}: {exc}") from exc

    # MCP tools return {content: [{type: "text", text: "..."}]} or similar
    if isinstance(body, dict):
        content = body.get("content")
        if isinstance(content, list):
            texts = [c.get("text", "") for c in content if isinstance(c, dict)]
            return "\n".join(texts)
        if "text" in body:
            return body["text"]
        if "output" in body:
            return str(body["output"])
    return json.dumps(body, ensure_ascii=False)


def _dispatch_webhook(defn: dict, skill: str, ticket: dict, context: list[dict]) -> str:
    """Dispatch to an HTTP webhook endpoint.

    Definition fields:
        url     : str           — webhook URL
        headers : dict[str,str] — extra headers (values support ``{env:VAR}`` expansion)
        method  : str           — HTTP method (default POST)
        timeout : int           — request timeout in seconds (default 30)
    """
    url = defn.get("url", "")
    timeout = int(defn.get("timeout", 30))
    method = defn.get("method", "POST").upper()
    extra_headers = defn.get("headers", {}) or {}

    if not url:
        raise SkillDispatchError(f"Webhook skill '{skill}' has no 'url' configured")

    payload = json.dumps({
        "skill": skill,
        "ticket": ticket,
        "context": context,
    }, ensure_ascii=False).encode("utf-8")

    req = Request(_expand_env_vars(url), data=payload, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in extra_headers.items():
        req.add_header(k, _expand_env_vars(str(v)))

    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except HTTPError as exc:
        raise SkillDispatchError(f"Webhook skill '{skill}': HTTP {exc.code} from {url}") from exc
    except (URLError, OSError) as exc:
        raise SkillDispatchError(f"Webhook skill '{skill}': connection error to {url}: {exc}") from exc

    # Try to extract a text response from JSON, fall back to raw body
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            return data.get("output") or data.get("text") or data.get("response") or body
        return body
    except (json.JSONDecodeError, ValueError):
        return body


def _expand_env_vars(value: str) -> str:
    """Expand ``{env:VAR_NAME}`` placeholders in a string."""
    def _replace(m):
        var = m.group(1)
        return os.environ.get(var, "")
    return re.sub(r"\{env:(\w+)\}", _replace, value)


# Dispatch type router
_DISPATCH_HANDLERS = {
    "local": _dispatch_local,
    "mcp": _dispatch_mcp,
    "webhook": _dispatch_webhook,
}

# Module-level registry, populated by load_config() or explicitly.
_skill_registry: SkillRegistry | None = None


def dispatch_to_skill(skill: str, ticket: dict, context: list[dict]) -> str:
    """Dispatch a ticket to a skill handler via the skill registry.

    Looks up the skill in the registry and delegates to the appropriate handler
    based on the skill type (local, mcp, or webhook).  If the skill is not
    registered, falls back to a stub echo response so the engine can still run
    in environments without any skill backends configured.

    Contract:
        skill   : str         — name of the destination skill (from routing rules)
        ticket  : dict        — ticket payload (see docs/ticket-protocol.md)
        context : list[dict]  — recent session entries for the same peer/channel

    Returns:
        str — the textual response that will be appended to the session and
              written to ticket.result.output.
    """
    global _skill_registry

    if _skill_registry is None:
        # Fallback: no registry loaded yet (e.g. called outside heartbeat)
        logger.warning("Skill registry not loaded; returning stub response")
        return _stub_response(skill, ticket, context)

    defn = _skill_registry.get(skill)
    if defn is None:
        logger.warning("Skill '%s' not found in registry; returning stub response", skill)
        return _stub_response(skill, ticket, context)

    handler = _DISPATCH_HANDLERS.get(defn["type"])
    if handler is None:
        raise SkillDispatchError(f"No handler for skill type '{defn['type']}'")

    logger.info("Dispatching ticket %s to skill '%s' (type=%s)",
                ticket.get("id", "?"), skill, defn["type"])

    return handler(defn, skill, ticket, context)


def _stub_response(skill: str, ticket: dict, context: list[dict]) -> str:
    """Fallback echo response when no real handler is available."""
    instruction = ticket.get("instruction", "")
    peer_name = ticket.get("source", {}).get("peer_name", "")
    ctx_size = len(context) if context else 0
    return f"[{skill}] (stub) replying to {peer_name or 'unknown'}: '{instruction[:80]}' (context: {ctx_size})"


# --- Heartbeat ---

def run_heartbeat():
    """Execute one heartbeat cycle."""
    config = load_config()
    start = datetime.now(_RUNTIME_TZ)
    max_tickets = config.get("limits", {}).get("max_tickets_per_heartbeat", 10)

    logger.info("Heartbeat started at %s", start.strftime('%Y-%m-%d %H:%M:%S %Z'))

    tickets = load_pending_tickets()
    logger.info("Pending tickets: %d", len(tickets))

    if not tickets:
        logger.info("Inbox empty, nothing to process")
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
            logger.info("OK ticket=%s skill=%s rule=%s", ticket["id"], skill, rule)
        except Exception as e:
            errors += 1
            logger.error("ERR ticket=%s error=%s", ticket.get("id", "?"), e)

    logger.info("Heartbeat complete: processed=%d errors=%d", processed, errors)

    log_heartbeat(start, len(tickets), processed, errors, routes)
    _record_metric("heartbeat", tickets_found=len(tickets),
                   tickets_processed=processed, errors=errors)
    cleanup_outbox()


def log_heartbeat(start, found, processed, errors, routes=None):
    """Write heartbeat execution log."""
    end = datetime.now(_RUNTIME_TZ)
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

    logger.info("Heartbeat log written: path=%s duration_ms=%d", log_path, duration_ms)


def cleanup_outbox(max_age_days=7):
    """Remove completed tickets older than max_age_days."""
    outbox = os.path.join(CLAW_HOME, "outbox")
    if not os.path.exists(outbox):
        return

    cutoff = datetime.now(_RUNTIME_TZ) - timedelta(days=max_age_days)
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
        logger.info("Cleanup: %d old tickets removed from outbox", removed)


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
        load_config()  # ensure timezone is set before any timestamp ops
        cleanup_outbox()
        print("Cleanup complete")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
