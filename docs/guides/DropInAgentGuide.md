# Drop-in Agent Guide: Using OpenAI Agents with Agent Gateway

## 1. Overview

The **Agent Gateway** is an OpenAI-compatible orchestration service that connects chat UIs (like Open WebUI or custom frontends) to both **local and cloud-based LLM backends** (OpenAI, LM Studio, Ollama, vLLM). It exposes a standard `/v1/chat/completions` endpoint, allowing SDK-defined agents to be used as if they were OpenAI models.

Agents are implemented using the **OpenAI Agents SDK** in Python. Each agent is defined as an `Agent` object with tools, instructions, and optional planning or sub-agent logic. The Gateway automatically discovers agents that follow its directory conventions and makes them available under `/v1/models`.

---

## 2. Prerequisites

* Python 3.10+ with the `openai-agents` package installed in the same environment as the gateway.
* Access to an upstream OpenAI-compatible LLM endpoint (OpenAI, LM Studio, Ollama, etc.).
* An API key configured in `src/config/security.yaml` or the `GATEWAY_API_KEY` environment variable.
* Optional: permission to modify `src/config/security.yaml` if you need to lock module/tool allowlists.

---

## 3. Discovery Model

The Agent Gateway uses a **drop-in discovery convention**:

* Each agent resides in `src/agents/<AgentName>/agent.py`
* The module **must export a top-level variable** named `agent`, which must be an instance of `Agent` from the OpenAI Agents SDK.
* Example path: `src/agents/weather/agent.py`

At runtime, the gateway recursively scans the directory defined by the environment variable `GATEWAY_AGENT_DISCOVERY_PATH` (default: `src/agents/`) to import these files. If the import fails (missing dependencies, syntax errors, etc.), the agent will not be registered and will not appear under `/v1/models`.

### Relevant Environment Variables

| Variable                       | Description                                               |
| ------------------------------ | --------------------------------------------------------- |
| `GATEWAY_AGENT_DISCOVERY_PATH` | Directory where agents are auto-discovered.               |
| `GATEWAY_AGENT_AUTO_RELOAD`    | Enables live reload when files change.                    |
| `GATEWAY_SECURITY_CONFIG`      | Path to `security.yaml` for tool and import whitelisting. |

Agents that pass discovery are registered into the internal registry (`src/registry/agents.py`) and exposed via the API routes `src/api/routes/models.py` and `src/api/routes/chat.py`.

---

## 4. Directory & Naming Conventions

```
src/
  agents/
    ResearchAgent/
      __init__.py
      agent.py
    WeatherAgent/
      agent.py
```

**Rules:**

1. Folder name → model ID: The subfolder acts as the agent’s base name. The gateway derives the model identifier as `<namespace>/<name>` where `namespace` defaults to the folder’s top-level directory (or `default` if none). Example: `src/agents/ResearchAgent/agent.py` becomes `default/researchagent`.
2. Module exports: Each `agent.py` must export an `Agent` instance, callable returning an `Agent`, or helper that orchestrates Runner execution.
3. Multiple agents per folder: Additional exports append attribute names to form unique IDs (`default/researchagent-secondary`).
4. Security allowlists: Managed via `security.yaml` (`dropin_module_allowlist` / `dropin_module_denylist`).

---

## 5. Creating a Minimal SDK Agent

```python
from agents import Agent, function_tool

@function_tool
def get_time() -> str:
    import datetime
    return datetime.datetime.now().isoformat()

agent = Agent(
    name="ExampleAgent",
    instructions="Respond to user queries and report current time.",
    tools=[get_time],
)
```

**Key Points:**

* Use `@function_tool` to expose callable functions.
* Export a top-level `agent` instance.
* Sub-agents may be invoked through `Runner.run(sub_agent, query)`.

---

## 6. How Gateway Exposes Agents

Once discovered, agents are registered using the `AgentRegistry` (`src/registry/agents.py`) and `sdk_adapter/adapter.py` bridges them to OpenAI-compatible REST schemas.

Agents appear in `/v1/models`:

```json
{
  "id": "example-agent",
  "object": "model",
  "owned_by": "agent-gateway",
  "permission": []
}
```

Requests to `/v1/chat/completions` route automatically to the agent’s `agent.run()`.

Handles:

* Streaming responses
* Tool invocation and sandboxing
* Observability via `sdk_adapter/context.py`

---

## 7. Gateway-Managed Tools

The gateway includes a **centralized tool registry** (`src/config/tools.yaml`) exposed via `sdk_adapter/gateway_tools.py`.

```python
from sdk_adapter.gateway_tools import gateway_tool

@gateway_tool
def ping(url: str) -> str:
    import requests
    return requests.get(url).text[:200]
```

Shared tools follow `security.yaml` allowlists. Example reuse:

```python
http_echo = gateway_tool("http_echo")
agent = Agent(name="EchoAgent", instructions="Call the HTTP echo tool.", tools=[http_echo])
```

---

## 8. Supported Runner Features

All core OpenAI Agents SDK features work natively:

* `AgentHooks` events
* `handoffs`, `as_tool`, `manager` patterns
* Guardrails (`InputGuardrail`, `GuardrailFunctionOutput`)
* Structured outputs and dynamic context

Multi-agent workflows may import and nest other agents; gateway does not rewrite SDK logic.

---

## 9. Testing & Hot Reload

1. Run `pytest tests/test_agent_discovery.py tests/test_sdk_adapter.py`.
2. Use fixture agents in `tests/fixtures/dropin_agents`.
3. Enable auto-reload: `GATEWAY_AGENT_AUTO_RELOAD=1`.
4. During dev, use `uvicorn api.main:app --reload`.

---

## 10. Troubleshooting

| Symptom          | Likely Cause                   | Resolution                                         |
| ---------------- | ------------------------------ | -------------------------------------------------- |
| Agent missing    | Import error or blocked module | Check logs, ensure allowlist includes module       |
| 403 tool errors  | Tool not in allowlist          | Edit `security.yaml` or use `@function_tool`       |
| One-chunk stream | Streaming disabled             | Ensure `stream: true` and inspect `sdk_agent` logs |
| SDK ImportError  | Missing dependency             | `pip install openai-agents`                        |

---

## 11. Example Workflow

1. Create `src/agents/<YourAgent>/agent.py` exporting an `Agent`.
2. Optionally add shared tools via `gateway_tool`.
3. Restart or reload the gateway.
4. Check `/v1/models` for registration.
5. Invoke via standard OpenAI client:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "example-agent", "messages": [{"role": "user", "content": "Hi!"}]}'
```

---

## 12. Summary

By following this **drop-in convention**, developers can author new SDK agents under `src/agents/`, and the Agent Gateway will auto-discover, register, and expose them as OpenAI-compatible models—no YAML edits required. The combination of auto-discovery, centralized tools, and strict security controls allows for rapid experimentation while preserving operational safety.
