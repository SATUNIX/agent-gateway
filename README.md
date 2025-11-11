# Agent Gateway

Agent Gateway is a modular, OpenAI-compatible service that plugs your chat UI into OpenAI Agents SDK modules and local/cloud LLM backends (LM Studio, Ollama, vLLM, OpenAI). Drop a standard SDK agent into `src/agents/<Name>/agent.py`, and the gateway exposes it as a `/v1/chat/completions` model with routing, tooling, observability, and security handled for you.

---

## Table of Contents
- [Highlights](#highlights)
- [Quick Start](#quick-start)
  - [Linux/macOS](#linuxmacos)
  - [Windows](#windows)
- [Drop-in Agent Workflow](#drop-in-agent-workflow)
- [Configuration & Documentation](#configuration--documentation)
- [Troubleshooting](#troubleshooting)
- [Make Targets](#make-targets)
- [API Surface](#api-surface)
- [Observability & Security](#observability--security)
- [Testing & Packaging](#testing--packaging)
- [Roadmap](#roadmap)

---

## Highlights
| Capability | Details |
| --- | --- |
| OpenAI-compatible API | `POST /v1/chat/completions` with streaming SSE, `GET /v1/models`, admin endpoints for agents/upstreams/tools/security. |
| Drop-in SDK agents | Filesystem discovery under `src/agents/**` exposes each module as a `model` without editing YAML; supports hooks, handoffs, guardrails, structured outputs. |
| Tooling | Central Tool/MCP manager for local Python, HTTP, MCP providers plus optional `gateway_tool()` shim so SDK agents can reuse gateway-managed tools. |
| Routing | Namespace-aware registries map models to upstream providers (OpenAI, LM Studio, Ollama, etc.) with per-agent execution policies. |
| Security | API keys with ACLs/rate limits, tool allowlists, drop-in module allow/deny lists, `/security/refresh`, nightly audit scripts. |
| Observability | Structured logs (request + `sdk_agent.*` events), Prometheus metrics, request IDs, dashboards (see `docs/systems/observability.md`). |
| Packaging | Multi-stage Dockerfile, docker-compose stack, SBOM + release scripts, CI pipeline, operator runbooks. |

---

## Quick Start

### Linux/macOS
```bash
git clone https://github.com/<org>/agent-gateway.git
cd agent-gateway
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp src/config/security.yaml src/config/security.local.yaml   # optional customization
export GATEWAY_SECURITY_CONFIG=src/config/security.yaml
export PYTHONPATH=src
uvicorn api.main:app --reload
```
Visit `http://127.0.0.1:8000/docs` for the OpenAPI explorer and `http://127.0.0.1:8000/v1/models` (with `x-api-key`) to see discovered agents.

### Windows
```powershell
git clone https://github.com/<org>/agent-gateway.git
cd agent-gateway
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
setx GATEWAY_SECURITY_CONFIG "%CD%\src\config\security.yaml"
set PYTHONPATH=%CD%\\src
uvicorn api.main:app --reload
```
Use `Invoke-WebRequest`/`curl` or an OpenAI-compatible UI (Open WebUI) pointed at `http://localhost:8000`.

> **Tip:** Set `GATEWAY_AGENT_AUTO_RELOAD=1` during development to hot-reload YAML and drop-in modules.

---

## Drop-in Agent Workflow
1. **Write an SDK agent** under `src/agents/<AgentName>/agent.py`. Example:
   ```py
   from agents import Agent, function_tool
   @function_tool
   def get_weather(city: str) -> str:
       return f"The weather in {city} is sunny"
   agent = Agent(name="Weather Agent", instructions="Always respond with weather.", tools=[get_weather])
   ```
2. **Start the gateway** (`PYTHONPATH=src uvicorn api.main:app --reload`). The registry scans `src/agents/**` and registers any exported `Agent` or factory automatically.
3. **List models** – `curl -H "x-api-key: dev-secret" http://localhost:8000/v1/models`.
4. **Chat** – POST to `/v1/chat/completions` with `{"model": "default/weatheragent", "messages": [...]}`. Set `stream:true` to receive SSE chunks.
5. **Optional gateway tools** – Use `from sdk_adapter.gateway_tools import gateway_tool` to wrap entries from `src/config/tools.yaml`, retaining SDK semantics while gaining centralized security/logging.

See `docs/guides/DropInAgentGuide.md` for conventions, sample fixtures, and troubleshooting (import errors, module allowlists, tool permissions).

---

## Configuration & Documentation
| File/Doc | Purpose |
| --- | --- |
| `src/config/agents.yaml` | Legacy declarative agents (still supported). |
| `src/config/upstreams.yaml` | Upstream LLM providers (base URL, key, health checks). |
| `src/config/tools.yaml` | Gateway-managed tools (local, HTTP, MCP). |
| `src/config/security.yaml` | API keys, namespace ACLs, tool allowlists, drop-in module allow/deny lists. |
| `docs/README.md` | Overview of documentation categories. |
| `docs/references/README.md` | Documentation index. |
| `docs/guides/DropInAgentGuide.md` | Step-by-step drop-in workflow, naming, troubleshooting. |
| `docs/plans/DropInAgents_TestPlan.md` | Acceptance criteria for SDK parity. |
| `docs/guides/OperatorRunbook.md` | Operations, incident response, config matrix. |
| `docs/guides/Troubleshooting.md` | Import issues, upstream failures, SSE debugging. |
| `docs/systems/tooling.md`, `docs/systems/security.md`, `docs/systems/observability.md`, `docs/systems/resiliency.md` | Deep dives for each subsystem. |

Environment overrides: `GATEWAY_AGENT_CONFIG`, `GATEWAY_UPSTREAM_CONFIG`, `GATEWAY_TOOL_CONFIG`, `GATEWAY_SECURITY_CONFIG`, `GATEWAY_AGENT_DISCOVERY_PATH`, `GATEWAY_AGENT_DISCOVERY_ALLOWLIST`, `GATEWAY_AGENT_DISCOVERY_DENYLIST`, `GATEWAY_AGENT_AUTO_RELOAD`, `GATEWAY_UPSTREAM_AUTO_RELOAD`, `GATEWAY_TOOL_AUTO_RELOAD`, `GATEWAY_LOG_LEVEL`, `GATEWAY_PROMETHEUS_ENABLED`, etc.

---

## Troubleshooting
| Issue | Resolution |
| --- | --- |
| Agent missing from `/v1/models` | Check logs for `agent.dropin.blocked` (module allowlist) or import errors; ensure the SDK module exports `agent`. |
| 403 when invoking gateway tool | Tool module not in `local_tools_allowlist`. Edit `src/config/security.yaml` or use a native SDK `@function_tool`. |
| Streaming stops after first chunk | The agent returned a complete response immediately. Verify `stream:true` and inspect logs for `sdk_agent.failure`. |
| `PermissionError` on import | Install `openai-agents` in the same environment (`pip install openai-agents`). |
| Rate limit exceeded (429) | Increase `rate_limit.per_minute` or spread requests across API keys. |

Detailed remediation steps live in `docs/guides/Troubleshooting.md`.

## Make Targets
| Target | Description |
| --- | --- |
| `make run` | Start FastAPI app with auto-reload. |
| `make fmt` / `make lint` | Format and lint via Ruff. |
| `make test` / `make coverage` | Pytest + coverage (api/agents/tooling/security). |
| `make smoke` | Run end-to-end smoke test (`tests/test_smoke_gateway.py`). |
| `make docker-build` | Build container image. |
| `make sbom` | Generate CycloneDX SBOM. |

---

## API Surface
- `POST /v1/chat/completions` – OpenAI payloads; `stream=true` for SSE chunks.
- `GET /v1/models` – Lists ACL-filtered models (YAML + drop-in) for UIs.
- `GET /agents`, `POST /agents/refresh` – Agent registry introspection.
- `GET /upstreams`, `POST /upstreams/refresh` – Upstream inventory.
- `GET /tools`, `POST /tools/refresh` – Tool metadata and reload.
- `POST /security/refresh` – Reload API-key config and return sanitized metadata.
- `GET /metrics` – JSON snapshot; `GET /metrics/prometheus` for Prometheus scraping.
- `GET /health` – Lightweight liveness probe.

All admin endpoints require `x-api-key`. ACL patterns control agent access; rate limiting returns HTTP 429; unauthorized agents return HTTP 403.

---

## Observability & Security
- Logs: structured JSON with request IDs, streaming events, `sdk_agent.start/success/failure`, tool invocations, upstream health.
- Metrics: `/metrics` JSON snapshot + `/metrics/prometheus` exporter (request latency, tool latency, upstream status).
- Security: API keys + ACLs in `src/config/security.yaml`, drop-in module allow/deny lists, tool allowlists, `/security/refresh`, nightly audit script, request rate limiting.

---

## Testing & Packaging
- `pytest` suites cover registries, SDK adapter, tool manager, security manager, streaming helpers, and API routes.
- `tests/fixtures/dropin_agents` house canonical SDK agent examples (handoffs, guardrails, hooks).
- `make smoke` runs `tests/test_smoke_gateway.py` for end-to-end coverage.
- `Dockerfile` builds slim images; `docker-compose.yaml` includes the gateway + mock upstream + observability stack.
- Release workflows produce signed images, SBOMs, and changelog entries (`RELEASE.md`, `scripts/release.sh`).

---

## Roadmap
Progress against the 10-step plan (drop-in SDK enablement, security, docs, packaging, launch-readiness) is tracked in `docs/plans/AgentGateway_10-Step_Development_Plan.md`. Refer there for current status and next milestones.
