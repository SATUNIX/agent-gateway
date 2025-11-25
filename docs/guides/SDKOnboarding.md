# SDK Agent Onboarding Guide

This guide targets developers who maintain OpenAI Agents SDK modules that will run inside the Agent Gateway. It covers environment setup, authoring, dependency management, testing, and operational expectations.

---

## 1. Environment Setup

1. Clone the repository and create a virtual environment.
2. Install base dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. If you plan to use watch mode:
   ```bash
   pip install "agent-gateway[watch]"
   export GATEWAY_AGENT_WATCH=1
   ```
4. Export security config for your environment:
   ```bash
   export GATEWAY_SECURITY_CONFIG=src/config/security.yaml
   ```

Optional but recommended:

```bash
pip install openai-agents
python scripts/install_agent_deps.py --agent SampleAgent
```

---

## 2. Authoring SDK Agents

### File Structure

```
src/agents/
  LabsPlanner/
    __init__.py
    agent.py
```

Within `agent.py` export `agent` or `build_agent()`:

```python
from agents import Agent, function_tool
from sdk_adapter.gateway_tools import use_gateway_tool

@function_tool
def summarize(text: str) -> str:
    return text[:120] + "..."

http_echo = use_gateway_tool("http_echo")

agent = Agent(
    name="Labs Planner",
    instructions="Summarize the plan and call http_echo when debugging.",
    tools=[summarize, http_echo],
)
```

### Tooling

- Prefer SDK-native `@function_tool` for agent-specific logic. Native tools are now auto-instrumented for security/metrics (source="sdk").
- Use `use_gateway_tool("name")` for centrally managed tools (benefits: shared observability, ACLs, retries). Gateway-managed tools remain the recommended option for shared utilities.

### Metadata Overrides

Add optional `__gateway__` metadata to control defaults:

```python
__gateway__ = {
    "namespace": "labs",
    "display_name": "Labs Planner",
    "description": "Auto-generated plans for labs team",
    "model": "gpt-4o-mini",
    "upstream": "lmstudio",
}
```

---

## 3. Dependency Management

If your agent requires additional packages, place a `requirements.txt` next to `agent.py`. Use the helper script to install them:

```bash
python scripts/install_agent_deps.py --agent LabsPlanner
```

Discovery verifies dependencies during import. Missing packages surface in:

- `/admin/agents` (diagnostic entries)
- `/admin/agents/errors`
- Prometheus `agent_gateway_dropin_failures_total{kind="discovery_dependency"}`

---

## 4. Local Testing

### Unit Tests

Add pytest modules under `tests/` for agent-specific utilities. Use `pytest -k labs_planner` to iterate.

### Drop-In Acceptance Suite

Before committing, run:

```bash
make test-acceptance
```

This suite materializes fixtures under a temporary package, hits `/v1/models`, `/v1/chat/completions` (both streaming and non), and validates gateway tool usage.

### Manual Verification

Run the gateway (`PYTHONPATH=src uvicorn api.main:app --reload`) and call:

```bash
curl -H "x-api-key: dev-secret" http://localhost:8000/v1/models
curl -H "x-api-key: dev-secret" -H "Content-Type: application/json" \
     -d '{"model":"labs/labsplanner","messages":[{"role":"user","content":"Plan launch"}]}' \
     http://localhost:8000/v1/chat/completions
```

---

## 5. Security & Overrides

- API key policies and namespace defaults live in `src/config/security.yaml`.
- Use `/security/preview` to troubleshoot access, `/security/override` for TTL-based overrides.
- Logs: `agent.security.decision`, `agent.security.override.created`, etc.
- `/admin/agents/errors` summarizes recent deny events (missing deps, allowlist issues, guardrail blocks).
- Pattern matching supports wildcards (fnmatch): `labs/*`, `alpha/demo*`, or `*planner*` can be used in allow/deny lists.

---

## 6. Operational Best Practices

| Area | Recommendation |
| --- | --- |
| Watch mode | Enable locally for fast iteration; disable in prod unless needed. |
| Dependencies | Keep `requirements.txt` scoped per agent; install via helper script. |
| Tooling | Prefer gateway-managed tools for shared infrastructure, fallback to native tools for agent-specific logic. |
| Metrics | Monitor Prometheus metrics (`agent_gateway_tool_invocations_total`, `agent_gateway_dropin_failures_total`) for regressions. |
| Doc updates | Update `docs/guides/DropInAgentGuide.md` and `docs/guides/Troubleshooting.md` when adding new workflows or known issues. |

---

## 7. Release Readiness Checklist

Before merging:

1. `make lint`
2. `make test` and `make test-acceptance`
3. `python scripts/install_agent_deps.py` (if dependencies changed)
4. Confirm `/admin/agents` shows the new agent and `/admin/agents/errors` is clear
5. Update documentation if the workflow changed

This ensures the drop-in UX remains “copy → run → chat” without manual configuration.
