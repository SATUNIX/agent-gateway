# AGENTS.md — Codebase Orientation For Automation

This document equips autonomous agents (and humans) with a consistent mental model of the Agent Gateway repository so they can plan, reason, and act safely across the project.

---

## 1. Project Overview

- **Repository:** `agent-gateway`
- **Primary Language:** Python 3.11 (FastAPI stack)
- **Purpose:** Provide an OpenAI-compatible gateway that exposes drop-in SDK agents, routes traffic to upstream model providers (LM Studio, OpenAI, Ollama, etc.), orchestrates tool executions, and enforces security/observability policies.
- **Core Objectives:**
  - Auto-discover OpenAI Agents SDK modules dropped under `src/agents/**` and expose them as `/v1/chat/completions` models.
  - Centralize tool invocation (local Python, HTTP, MCP) with consistent auditing and security controls.
  - Offer production-grade operations (Docker, Prometheus, security hot reloads, admin APIs).
- **Key Features:**
  - FastAPI application with OpenAI-compatible routes (`/v1/chat/completions`, `/v1/models`, `/admin/**`).
  - Agent registry supporting YAML declarative specs plus filesystem SDK discovery.
  - Tool/MCP manager with metrics and structured logging.
  - Configurable upstream registry and security manager (API keys, rate limiting, allowlists).

---

## 2. Architecture Map

```
[Clients / Open WebUI / SDKs]
        |
        v
[FastAPI Gateway (src/api/main.py)]
        |
        +--> Middleware (logging, auth, request context)
        +--> Routes (/v1/chat, /v1/models, admin endpoints)
                |
                v
      [Agent Executor (src/agents/executor.py)]
                |
        +-------+-------+
        |               |
[Tooling Manager]   [Upstream Registry]
(src/tooling/*)     (src/registry/upstreams.py)
        |               |
[Local/MCP/HTTP]   [OpenAI/LM Studio/etc.]
```

**Components Summary**

| Module                             | Description                                        | Language | Key deps                  |
| ---------------------------------- | -------------------------------------------------- | -------- | ------------------------- |
| `src/api/`                         | FastAPI app, routes, middleware, models            | Python   | FastAPI, Pydantic         |
| `src/agents/`                      | Agent executor, policies, SDK examples             | Python   | OpenAI Agents SDK         |
| `src/registry/`                    | Agent/upstream discovery + models                  | Python   | Pydantic, importlib       |
| `src/tooling/`                     | Tool manager, local tools, MCP client              | Python   | httpx, asyncio, SSE libs  |
| `src/security/`                    | Security manager, ACLs, rate limiting              | Python   | Pydantic                  |
| `src/observability/`               | Logging helpers, context propagation               | Python   | structlog / logging       |
| `examples/mock_upstream/`          | Reference upstream container                       | Python   | FastAPI                   |

---

## 3. Entry Points & Execution Flow

- **Primary entry:** `uvicorn api.main:app --reload`.
- **Control flow:** `src/api/main.py` loads settings (`src/config/settings.py`), attaches middleware for logging/auth, registers routes under `/v1` and `/admin`, and mounts Prometheus metrics if enabled.
- **Request lifecycle (chat completion):**
  1. Middleware injects request context and enforces API-key auth.
  2. `src/api/routes/chat.py` validates payload via Pydantic models.
  3. `src/agents/executor.py` resolves the target agent (YAML or drop-in), prepares the message stack, and manages the loop.
  4. Tool calls dispatch via `src/tooling/manager.py`; upstream LLM calls via `src/registry/upstreams.py`.
  5. Streaming responses are chunked using `src/api/services/streaming.py`.
- **Async model:** FastAPI/Uvicorn asynchronous request handling; tool + upstream calls rely on asyncio coroutines.

---

## 4. Directory & Module Breakdown

| Path                        | Purpose                                                         | Agent Notes                                           |
| --------------------------- | --------------------------------------------------------------- | ----------------------------------------------------- |
| `src/api/`                  | FastAPI app, middleware, route handlers, Pydantic schemas       | Start here to understand request/response shapes.     |
| `src/agents/`               | Agent executor, policies, sample SDK integrations               | Key logic for orchestration + policy enforcement.     |
| `src/registry/`             | Agent discovery (YAML + filesystem), upstream registry          | Controls model catalog and provider clients.          |
| `src/tooling/`              | Tool manager, MCP client, local tool adapters                   | Central point for tool invocation semantics.          |
| `src/security/`             | Security models + manager (API keys, allowlists, rate limits)   | Gatekeeper for admin endpoints and agent policies.    |
| `src/config/`               | YAML configs (agents, upstreams, tools, security) + settings    | Default paths assume `src/config/*.yaml`.             |
| `observability/`            | Logging context, instrumentation utilities                      | Helps trace request IDs and event logs.               |
| `tests/`                    | Pytest suites for registry, tooling, security, streaming, etc.  | Use to confirm assumptions or locate fixtures.        |
| `docs/`                     | Organized documentation (guides, plans, systems, references)    | `docs/README.md` explains the new hierarchy.          |
| `examples/mock_upstream/`   | Sample upstream service used by tests/compose                   | Useful for e2e simulations.                           |

---

## 5. Configuration & Environment

- **Config files:** `src/config/agents.yaml`, `upstreams.yaml`, `tools.yaml`, `security.yaml`.
- **Environment variables (via `src/config/settings.py`):**
  - `GATEWAY_AGENT_CONFIG`, `GATEWAY_UPSTREAM_CONFIG`, `GATEWAY_TOOL_CONFIG`, `GATEWAY_SECURITY_CONFIG`
  - `GATEWAY_AGENT_DISCOVERY_PATH`, `GATEWAY_AGENT_DISCOVERY_PACKAGE`
  - `GATEWAY_LOG_LEVEL`, `GATEWAY_PROMETHEUS_ENABLED`, `GATEWAY_AGENT_AUTO_RELOAD`, etc.
- **Secrets:** Typically supplied via env vars or mounted YAML with hashed API keys.
- **Dynamic behavior:** `/agents/refresh`, `/tools/refresh`, `/upstreams/refresh`, `/security/refresh` endpoints reload configs at runtime.

---

## 6. Data Models & Schemas

| Model                          | File                             | Description                                               | Relations / Notes                                  |
| ------------------------------ | -------------------------------- | --------------------------------------------------------- | -------------------------------------------------- |
| `ChatCompletionRequest/Response` | `src/api/models/chat.py`        | OpenAI-compatible payloads for `/v1/chat/completions`     | Consumed by routes, executor, streaming services.  |
| `AgentSpec`                    | `src/registry/models.py`         | Declarative agent definition (YAML)                       | Referenced by registry + executor.                 |
| `DiscoveredAgentExport`        | `src/registry/discovery.py`      | Metadata for drop-in SDK modules                          | Drives filesystem discovery flow.                  |
| `ToolDefinition`               | `src/tooling/manager.py`         | Representation of local/HTTP/MCP tools                    | Used by tool loader and execution pipeline.        |
| `SecurityConfig`               | `src/security/models.py`         | API keys, ACLs, allow/deny lists, rate limits             | Security manager enforces policies per request.    |

Agents should inspect these Pydantic models to understand validation rules and cross-component contracts.

---

## 7. Tooling & Dependencies

- **Dependency manifests:** `requirements.txt` (runtime) and `pyproject.toml` (package metadata + dev extras).
- **Notable libraries:**
  - `fastapi`, `uvicorn[standard]` — HTTP server + async runtime.
  - `openai` — Upstream client interface.
  - `pyyaml`, `pydantic` — Config parsing + validation.
  - `prometheus-client` — Metrics exposure.
  - `ruff`, `pytest`, `pytest-cov` — Dev tooling.
- **Tool adapters:** See `src/tooling/manager.py` (local python), `src/tooling/mcp_client.py` (MCP over HTTP/SSE), plus the `use_gateway_tool()` helper in `sdk_adapter/gateway_tools.py` so SDK agents can reuse gateway-managed tools alongside native `@function_tool`s.

Example combo:

```python
from agents import Agent, function_tool
from sdk_adapter.gateway_tools import use_gateway_tool

@function_tool
def summarize(text: str) -> str:
    return text[:100] + "..."

agent = Agent(
    name="SampleAgent",
    instructions="Summarize locally, call http_echo via the gateway when debugging.",
    tools=[summarize, use_gateway_tool("http_echo")],
)
```

---

## 8. Task Flow / Pipelines

**Chat completion pipeline**
```
HTTP Request -> Middleware (auth/logging) -> Chat route -> Agent executor
  -> (optional) Tool Manager -> Upstream LLM -> Streaming service -> HTTP Response
```

**Admin refresh pipeline**
```
Admin Route -> Security Manager validation -> Registry/Manager reload -> Response summary
```

**Tool invocation pipeline**
```
Agent -> Tooling Manager -> Provider adapter (local/http/mcp) -> Result -> Agent executor
```

Agents should respect these flows when inserting instrumentation or automations.

---

## 9. Testing Strategy

- **Unit tests:** `tests/test_*` cover registry validation, upstream routing, tooling, security manager, streaming utilities, SDK adapter, etc.
- **Smoke/E2E:** `tests/test_smoke_gateway.py` plus `make smoke` target.
- **Fixtures:** `tests/fixtures/` includes drop-in agent snippets for discovery tests.
- **Coverage tooling:** `make test` (focused coverage) and `make coverage` for broader reporting.

When modifying logic, update/extend the relevant pytest modules and run with `PYTHONPATH=src pytest`.

---

## 10. Operational Notes

- **Run locally:** `make run` (injects `PYTHONPATH=src` and starts Uvicorn).
- **Docker/Compose:** Root `Dockerfile` sets `PYTHONPATH=/app/src`; `docker-compose.yaml` wires configs from `/app/src/config`.
- **Observability:** Structured logs plus optional Prometheus endpoints; reference `docs/systems/observability.md`.
- **Documentation:** Start from `docs/README.md` for category overview, then consult guides/plans/systems as needed.

Use this file as the top-level reference when onboarding new automation agents or summarizing the codebase for downstream tasks.
