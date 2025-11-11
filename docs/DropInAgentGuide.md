# Drop-in Agent Guide

This guide explains how to author OpenAI Agents SDK modules, drop them into the `agents/` folder, and serve them via the Agent Gateway without modifying YAML files or writing custom wrappers.

## 1. Prerequisites

- Python 3.10+ with the `openai-agents` package installed in the same environment as the gateway.
- Access to an upstream OpenAI-compatible LLM endpoint (OpenAI, LM Studio, Ollama, etc.).
- An API key configured in `config/security.yaml` or the `GATEWAY_API_KEY` environment variable.
- Optional: permission to modify `config/security.yaml` if you need to lock module/tool allowlists.

## 2. Directory & Naming Conventions

```
agents/
  ResearchAgent/
    __init__.py
    agent.py
  WeatherAgent/
    agent.py
```

Rules:

1. **Folder name → model ID**: The subfolder acts as the agent’s base name. The gateway derives the model identifier as `<namespace>/<name>` where `namespace` defaults to the folder’s top-level directory (or `default` if none). Example: `agents/ResearchAgent/agent.py` becomes `default/researchagent`.
2. **Module exports**: Each `agent.py` must export either:
   - An `Agent` instance (recommended).
   - A callable that returns an `Agent`.
   - A helper that already orchestrates Runner execution (e.g., `run_sync`), for legacy behavior.
   The loader inspects the module for these symbols automatically; no YAML entry required.
3. **Multiple agents per folder**: If you export multiple agents/functions, the gateway appends the attribute name to derive unique model IDs (e.g., `default/researchagent-secondary`).
4. **Security allowlists**: By default, all modules are allowed. Operators can restrict execution by editing `config/security.yaml` and adjusting `default.dropin_module_allowlist` / `dropin_module_denylist`. Blocked modules are logged with the `agent.dropin.blocked` event.

## 3. Creating an Agent

Example (`agents/ResearchAgent/agent.py`):

```py
from agents import Agent, function_tool

@function_tool
def web_summary(query: str) -> str:
    return f"Summarized: {query}"

agent = Agent(
    name="Research Agent",
    instructions="Perform deep research. Cite your findings.",
    tools=[web_summary],
)
```

After saving the file:

1. Start (or restart) the gateway: `uvicorn api.main:app --reload`.
2. Call `GET /v1/models` or `GET /admin/agents` using a valid API key. You should see `default/researchagent`.
3. Use the model via the OpenAI-compatible chat API:

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "x-api-key: dev-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default/researchagent",
    "messages": [{"role": "user", "content": "Summarize the FFT paper"}],
    "stream": true
  }'
```

The response streams Server-Sent Events (SSE) until a final `data: [DONE]` frame.

## 4. Using Gateway-managed Tools

SDK agents retain full control over their `@function_tool` implementations. If you would like to reuse tools defined in `config/tools.yaml` (HTTP, MCP, or local providers), opt into the helper:

```py
from sdk_adapter.gateway_tools import gateway_tool

http_echo = gateway_tool("http_echo")

agent = Agent(
    name="Echo Agent",
    instructions="Call the HTTP echo tool.",
    tools=[http_echo],
)
```

The helper enforces the same security policies as declarative agents:

- Tool allowlists (`default.local_tools_allowlist`) remain active.
- Permission errors propagate back to the agent as `PermissionError`.
- Invocations are logged and included in Prometheus metrics.

## 5. Supported Runner Features

All core OpenAI Agents SDK features work without modification:

- `AgentHooks` (start/end/tool/handoff events).
- `handoffs`, `as_tool`, manager patterns.
- `tool_use_behavior`, `tool_choice`, guardrails (`InputGuardrail`, `GuardrailFunctionOutput`).
- Structured outputs via `output_type`.
- Dynamic instructions receiving `RunContextWrapper`.

For multi-agent workflows, simply import additional agents/tools in the same module or nested packages. The gateway does not rewrite or normalize the SDK structures.

## 6. Testing Locally

1. Run `python -m pytest tests/test_agent_discovery.py tests/test_sdk_adapter.py` (install dependencies first).
2. Use the sample fixtures in `tests/fixtures/dropin_agents` to validate complex behaviors (handoffs, guardrails, hooks).
3. Smoke-test streaming via curl or any OpenAI-compatible UI by toggling `stream: true`.

## 7. Troubleshooting

| Symptom | Likely Cause | Resolution |
| --- | --- | --- |
| Agent missing from `/v1/models` | Module blocked by allowlist/denylist or import error | Check logs (`agent.dropin.blocked`) and ensure module path matches the allowlist. Run `python -m compileall agents/<Name>` to catch syntax errors. |
| 403 when invoking tool | Tool not in `local_tools_allowlist` or security policy | Update `config/security.yaml` allowlist or switch to an SDK-native `@function_tool`. |
| Streaming emits only one chunk | Agent returned a short response or streaming disabled | Ensure `stream: true` in the request and that the agent is producing incremental output; inspect logs for `sdk_agent` events. |
| ImportError for OpenAI Agents SDK | `pip install openai-agents` missing | Install the dependency inside the gateway environment. |

## 8. Hot Reload Tips

- Enable `GATEWAY_AGENT_AUTO_RELOAD=1` (YAML) and rely on filesystem watchers provided by the registry to pick up new modules.
- During development, run `uvicorn api.main:app --reload` to combine FastAPI reloads with discovery.

## 9. Example Repo Layout

```
.
├── agents/
│   ├── ResearchAgent/
│   │   └── agent.py
│   └── WeatherAgent/
│       └── agent.py
├── config/
│   ├── agents.yaml        # Legacy declarative entries (optional)
│   ├── security.yaml      # Tool + module allowlists
│   └── tools.yaml         # Gateway-managed HTTP/MCP/local tools
└── docs/
    └── DropInAgentGuide.md
```

With this structure you can iterate quickly: drop a new `agent.py`, refresh `/v1/models`, and the UI will treat it as a selectable model without editing config files.
