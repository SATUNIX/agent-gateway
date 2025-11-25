# Drop-In Agent Guide

This guide explains how to drop OpenAI Agents SDK modules into the Agent Gateway and expose them automatically via `/v1/chat/completions`. The target UX is “copy an agent folder into `src/agents/<Name>` → run the gateway → chat immediately.”

---

## 1. Prerequisites

- Python 3.11+
- Agent Gateway checkout (this repository)
- Optional: [`watchfiles`](https://pypi.org/project/watchfiles/) for watch mode (`pip install "agent-gateway[watch]"`)
- Optional: `openai-agents` SDK (`pip install openai-agents`)

Environment variables used by the gateway:

| Variable | Purpose |
| --- | --- |
| `GATEWAY_SECURITY_CONFIG` | Path to security YAML |
| `GATEWAY_AGENT_CONFIG` | Path to declarative agents (legacy) |
| `GATEWAY_AGENT_DISCOVERY_PATH` | Folder scanned for drop-in agents (`src/agents` by default) |
| `GATEWAY_AGENT_WATCH` | Set to `1` to enable filesystem watch mode (requires `watchfiles`) |
| `GATEWAY_AGENT_AUTO_RELOAD` | Automatically reload YAML configs during development |

---

## 2. Repository Layout

```
src/
  agents/
    <DropInName>/
      __init__.py
      agent.py        # exports `agent = Agent(...)` or `build_agent()`
  api/                # FastAPI routes & schemas
  registry/           # Discovery + metadata
  tooling/            # Gateway-managed tools, MCP client
  security/           # API key manager & policy enforcement
docs/
  guides/
    DropInAgentGuide.md
    SDKOnboarding.md
    OperatorRunbook.md
```

Drop-in modules live under `src/agents/**`. Each folder maps to `default/<lowercase-name>` unless a nested namespace is provided (e.g., `src/agents/labs/ResearchAgent` → `labs/researchagent`).

---

## 3. Building a Drop-In Agent

1. **Create a folder** under `src/agents/<Name>` and add `agent.py`.
2. **Export** either:
   - `agent = Agent(...)`
   - `agent = SomeRunner(...)`
   - `def build_agent(...) -> Agent`
3. **Declare tools** using `@function_tool` or gateway-managed tools via `use_gateway_tool()`.
4. **Keep responses standard** — return `str`, `dict`, or `ChatCompletionResponse`.

Example:

```python
from agents import Agent, function_tool
from sdk_adapter.gateway_tools import use_gateway_tool

@function_tool
def summarize(text: str) -> str:
    return text[:120] + "..."

http_echo = use_gateway_tool("http_echo")

agent = Agent(
    name="SampleAgent",
    instructions="Summarize the message, call http_echo when debugging.",
    tools=[summarize, http_echo],
)
```

---

## 4. Managing Dependencies

Drop-in agents often need additional packages (SDK plugins, custom libs, etc.). Each agent folder may include its own `requirements.txt`. Use the helper script to install them:

```bash
python scripts/install_agent_deps.py --agent SampleAgent
# or install every requirements.txt under src/agents
python scripts/install_agent_deps.py
```

The discovery process checks for missing packages and reports dependency errors via `/admin/agents` diagnostics and `/admin/agents/errors`.

---

## 5. Watch Mode & Reloads

Watch mode eliminates the need to call `/agents/refresh`:

1. Install the optional dependency (`pip install "agent-gateway[watch]"`).
2. Set `GATEWAY_AGENT_WATCH=1`.
3. Run the gateway (`PYTHONPATH=src uvicorn api.main:app --reload`).

File changes under `src/agents/**` trigger incremental refreshes, including helper modules and `requirements.txt` next to your agent. If `watchfiles` is missing or the filesystem doesn’t support inotify, the gateway logs `agent.watch.disabled` and falls back to manual refresh.

---

## 6. Testing Drop-In Agents

1. **Unit tests:** Author regular pytest modules for agent utilities.
2. **Drop-in acceptance suite:** run `make test-acceptance`. The suite materializes fixtures under a temporary package and hits `/v1/models` + `/v1/chat/completions` using the FastAPI TestClient.
3. **Manual verification:** call `/admin/agents` and `/v1/models` or use curl:

```bash
curl -H "x-api-key: dev-secret" http://localhost:8000/v1/models

curl -X POST http://localhost:8000/v1/chat/completions \
  -H "x-api-key: dev-secret" \
  -H "Content-Type: application/json" \
  -d '{"model":"default/sampleagent","messages":[{"role":"user","content":"Hi"}]}'
```

---

## 7. Security Policies & Overrides

- API keys live in `src/config/security.yaml`.
- Namespace defaults (`default.namespace_defaults`) let you grant `labs/*` or `prod/*` automatically.
- Temporary overrides:
  - Preview: `POST /security/preview {"agent": "labs/sample"}`.
  - Override: `POST /security/override {"agent": "labs/sample", "ttl_seconds": 3600}`.
- Logs: `agent.security.decision`, `agent.security.override.created`, etc.
- Errors: `/admin/agents/errors` shows recent blocks (missing deps, module allowlist violations).

---

## 8. Common Workflows

| Task | Commands |
| --- | --- |
| Install deps | `python scripts/install_agent_deps.py --agent SampleAgent` |
| Enable watch mode | `pip install "agent-gateway[watch]" && export GATEWAY_AGENT_WATCH=1` |
| Refresh manually | `curl -X POST -H "x-api-key: admin" http://localhost:8000/admin/agents/refresh` |
| View diagnostics | `curl -H "x-api-key: admin" http://localhost:8000/admin/agents/errors` |
| Run acceptance suite | `make test-acceptance` |

---

## 9. Troubleshooting Quick Reference

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `ImportError` when loading agent | Missing dependency | Run `scripts/install_agent_deps.py`, restart or rely on watch mode |
| Agent missing from `/v1/models` | Security denylist, syntax error, discovery failure | Check `/admin/agents/errors`, view `agent.dropin.blocked` logs |
| 403 when invoking agent | API key not allowed | Use `/security/preview` then `/security/override` or update `security.yaml` |
| Watch mode does nothing | `watchfiles` not installed or unsupported filesystem | Install optional dependency or disable `GATEWAY_AGENT_WATCH` |
| Tool call blocked | Module not in `local_tools_allowlist` | Update `src/config/security.yaml` and `POST /security/refresh` |

For deeper diagnostics see `docs/guides/Troubleshooting.md`.

---

## 10. Next Steps

- Read `docs/guides/SDKOnboarding.md` for deeper onboarding guidance (fixtures, CI expectations).
- Consult `docs/guides/OperatorRunbook.md` for day-2 operations (overrides, metrics, watch mode).
- Keep the drop-in acceptance suite green (`make test-acceptance`) before merging changes.
