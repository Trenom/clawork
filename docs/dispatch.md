# Skill Dispatch

The Clawork engine dispatches tickets to skills via a registry-based system. Each skill registered in the config maps to one of three handler types: **local** (Python callable), **mcp** (MCP tool on a Cowork server), or **webhook** (generic HTTP endpoint).

## Configuration

Skills can be defined in two places (entries in `skills.yaml` override same-name entries from `config.yaml`):

1. **`config.yaml`** — under the `skills` key
2. **`skills.yaml`** — standalone file in `CLAW_HOME`

### Local Skills

A local skill invokes a Python function in the repository or an installed package.

```yaml
skills:
  clawork-soul:
    type: local
    module: skills/clawork-soul/handler.py   # path relative to CLAW_HOME
    handler: handle                          # function name (default: handle)
```

The handler function must conform to:

```python
def handle(ticket: dict, context: list[dict]) -> str:
    """Process a ticket and return a text response."""
    ...
```

`module` accepts either:

- A **file path** relative to `CLAW_HOME` (ending in `.py` or containing `/`)
- A **dotted module path** that can be imported (e.g. `mypackage.skills.soul`)

### MCP Tools

An MCP skill calls a tool exposed by a Cowork MCP server via HTTP.

```yaml
skills:
  gde-agent:
    type: mcp
    server_url: http://localhost:8080
    tool_name: gde_lookup      # defaults to the skill name
    auth_header: "Bearer {env:MCP_TOKEN}"
    timeout: 30
```

The engine sends a `POST` to `{server_url}/tools/{tool_name}/invoke` with body:

```json
{
  "ticket": { ... },
  "context": [ ... ]
}
```

The response is parsed as JSON. The engine extracts text from MCP-standard `content` arrays, or falls back to `text`/`output` fields.

### Webhook

A webhook skill sends the ticket to any HTTP endpoint.

```yaml
skills:
  crm-agent:
    type: webhook
    url: https://crm.example.com/api/skill
    method: POST
    headers:
      Authorization: "Bearer {env:CRM_TOKEN}"
      X-Source: clawork
    timeout: 30
```

The request body is:

```json
{
  "skill": "crm-agent",
  "ticket": { ... },
  "context": [ ... ]
}
```

The response is parsed as JSON; the engine looks for `output`, `text`, or `response` fields. If parsing fails, the raw body is returned.

## Environment Variable Expansion

String values in skill definitions support `{env:VAR_NAME}` placeholders, which are replaced with the corresponding environment variable at dispatch time. This works in `url`, `auth_header`, and `headers` values.

## Fallback Behavior

If a skill referenced by a routing rule is **not registered** in the registry, the dispatcher returns a stub echo response. This allows the engine to run in test or development environments without any skill backends configured.

## Error Handling

All dispatch errors raise `SkillDispatchError` with a descriptive message. The engine's `process_ticket` function catches exceptions and records them in the ticket result. Errors include:

- Missing required configuration fields (`module`, `server_url`, `url`)
- Import failures for local skills
- HTTP errors from MCP/webhook endpoints
- Connection timeouts

## Registry Loading

The registry is initialized when `load_config()` is called (at engine startup). The load order is:

1. Read `skills` from `config.yaml`
2. Read `skills.yaml` (if it exists) — entries override step 1
3. Build a `SkillRegistry` with all collected entries

## Contract Summary

| Field | Local | MCP | Webhook |
|-------|-------|-----|---------|
| `type` | `local` | `mcp` | `webhook` |
| Required | `module` | `server_url` | `url` |
| Optional | `handler` | `tool_name`, `auth_header`, `timeout` | `method`, `headers`, `timeout` |

Handler input: `(ticket: dict, context: list[dict])`
Handler output: `str` (text response)
