# Agent Gateway - 10‑Step Development Plan

Context: Based on “Agent Gateway - Final Design Specification”. Goal is a modular, OpenAI‑compatible gateway that fronts a chat UI and local/cloud LLM backends, supports declarative and SDK agents, and integrates MCP/Tools with a pluggable architecture.

## Step 1 - Scaffold Project
**Status:** [x] Completed (FastAPI hello app, manifests, directories, helper scripts, git repo)
- Objective: Initialize a production-ready Python service skeleton.
- Key tasks: Set up FastAPI, Uvicorn, OpenAI SDK, PyYAML, Pydantic; create dirs `api/`, `agents/`, `registry/`, `tooling/`, `sdk_adapter/`, `config/`; add `requirements.txt`, `pyproject.toml`, basic `README` and `Makefile`/scripts.
- Deliverables: Running “hello” server; base folders; dependency lockfile.

## Step 2 - Build API Layer
**Status:** [x] Completed (OpenAI-style chat endpoint with streaming, CORS, API key auth, admin routes, metrics)
- Objective: Provide OpenAI-compatible `/v1/chat/completions` plus admin endpoints.
- Key tasks: Implement non-streaming and streaming responses; CORS; gateway API-key auth middleware; management routes for `/agents`, `/upstreams`, `/metrics`.
- Deliverables: FastAPI app with parity schema; OpenAPI docs enabled.
- Depends on: Step 1.

## Step 3 - Implement Agent Registry
**Status:** [x] Completed (YAML-driven registry with namespaces, hot reload, admin refresh endpoint)
- Objective: Load and manage declarative (YAML/JSON) and SDK agents.
- Key tasks: Define agent spec; load from `config/agents.yaml`; support namespacing and hot-reload in dev; validation via Pydantic models.
- Deliverables: Registry module with list/get/refresh; sample agents file.
- Depends on: Steps 1–2.

## Step 4 - Implement Upstream Registry
**Status:** [x] Completed (YAML-configured upstream registry with OpenAI clients, health checks, refresh, env secrets)
- Objective: Manage OpenAI client instances for LM Studio, OpenAI, Ollama, etc.
- Key tasks: Create typed config for upstreams; instantiate clients with base URL and API key; health-check on load; env var expansion for secrets.
- Deliverables: Registry with `get_client(name)`; default LM Studio config.
- Depends on: Steps 1–2.

## Step 5 - Build Agent Executor
**Status:** [x] Completed (context-aware executor with policy enforcement, SDK hooks, upstream integration)
- Objective: Run the agent loop (LLM -> tool -> LLM) with policies.
- Key tasks: Build message context (system/history/input); detect type (SDK vs declarative); enforce hop/token limits; normalize outputs to OpenAI response shape.
- Deliverables: Executor with single-turn and multi-turn flows; policy settings.
- Depends on: Steps 3-4.

## Step 6 - Add SDK Adapter
**Status:** [x] Completed (dynamic loader + execution helper, sample SDK agent, unit tests)
- Objective: Support code-defined agents via OpenAI Agents SDK.
- Key tasks: Dynamic import from `module:function`; inject upstream OpenAI client; call `agent.run()`/`run_sync()`; convert results to OpenAI schema.
- Deliverables: `sdk_adapter` module with tests and example SDK agent.
- Depends on: Steps 3-5.

## Step 7 - Integrate Tool / MCP Manager
**Status:** [x] Completed (ToolManager with local/http/mcp providers, executor tool loop, admin endpoints)
- Objective: Centralize tool invocation including MCP, HTTP, and LocalPython.
- Key tasks: Implement MCP client (HTTP/SSE) and connection lifecycle; define common tool interface and result schema; wire executor -> tools -> executor.
- Deliverables: Tool manager with at least one MCP example; local/HTTP demo tools.
- Depends on: Step 5.

## Step 8 - Add Observability
**Status:** [x] Completed (structured logging middleware, tool/LLM metrics, optional Prometheus exporter)
- Objective: Provide consistent logs and optional metrics.
- Key tasks: Request/response logging middleware; tool usage and LLM latency timers; structured JSON logs; optional Prometheus `/metrics` endpoint.
- Deliverables: Logging helpers; metrics route behind a flag.
- Depends on: Steps 2, 5, 7.

## Step 9 - Implement Security Layer
**Status:** [x] Completed (config-driven API keys, ACL enforcement, rate limiting, sandboxed tool allowlists)
- Objective: Protect the gateway and control access.
- Key tasks: API key validation; per-agent allowlists; simple rate limiting; sandboxing constraints for local tools.
- Deliverables: Auth middleware; config-driven ACLs; rate-limit util.
- Depends on: Steps 2-3, 7.

## Step 10 - Testing & Packaging
**Status:** [x] Completed (pytest suite + smoke test, coverage tooling, Docker/compose, SBOM, CI, release automation)
- Objective: Finalize automated tests and produce production-ready artifacts.
- Key tasks:
  - Expand unit/integration coverage (registries, executor loops, SDK adapter, security manager, rate limiter, tool providers, observability wiring, FastAPI routes).
  - Provide deterministic fixtures/mocks for upstreams, MCP endpoints, and tool servers; add regression tests for config hot-reload paths.
  - Introduce end-to-end smoke test that spins up the gateway against a mocked upstream to validate streaming, tool loops, metrics, and auth enforcement.
  - Harden packaging: Dockerfile with multi-stage build, `docker-compose.yaml` for local orchestration (gateway + LM Studio stub + Redis/metrics as needed), versioned release scripts, SBOM/license scan hooks.
  - Define CI workflows (lint, type-check, tests, security scan, container build/push) and nightly job for dependency audit / key rotation reminders.
- Deliverables: Comprehensive pytest suite with fixtures, integration/smoke scripts, coverage reporting, Docker/compose assets, release checklist, GitHub Actions (or equivalent) CI pipeline.
- Depends on: All prior steps.

## Step 11 - Launch Readiness Review & Hardening
- Objective: Perform a holistic review to ensure the gateway is shippable and maintainable.
- Key tasks:
  - Conduct architecture and security reviews (threat modeling, dependency vulnerability scan, config validation) and address findings.
  - Execute load/stress tests (high QPS, burst traffic, noisy tool usage) to validate rate limits, resource caps, and graceful degradation.
  - Complete documentation: operator runbooks, troubleshooting guide, configuration matrix, upgrade/migration steps, API reference, changelog.
  - Run manual UAT with Open WebUI / sample clients, verifying multi-agent selection, streaming, tool loops, observability dashboards, and failure handling.
  - Prepare release artifacts (signed container image, version tags, release notes) and define ongoing maintenance tasks (rotation reminders, monitoring alerts).
- Deliverables: Review reports, resolved issue list, perf/load test results, finalized docs, release candidate build + sign-off checklist.
- Depends on: Step 10.
---

### Configuration Example (reference)
```yaml
upstreams:
  lmstudio:
    base_url: "http://localhost:1234/v1"
    api_key: "not-needed"

mcp_servers:
  weather:
    transport: http
    url: "https://mcp.example.com/weather"

agents:
  - name: "Assistant"
    kind: "declarative"
    upstream: "lmstudio"
    model: "gpt-4o-mini"
    instructions: |
      You are a concise and helpful assistant.
    tools:
      - name: "get_weather"
        provider: "mcp"
        mcp_server: "weather"
        mcp_method: "current"
    policies:
      max_tool_hops: 2

  - name: "Researcher"
    kind: "sdk"
    module: "agents.researcher:build_agent"
    upstream: "lmstudio"
    model: "gpt-4o-mini"
```

### Success Criteria
- OpenAI‑compatible chat completions (incl. streaming) verified against LM Studio.
- Agents load from YAML and SDK with hot‑reload in dev.
- Tool calls round‑trip via MCP/HTTP/LocalPython with logs and metrics.
- Basic auth, ACLs, and rate limiting active.
- Tests green and Docker image runs with sample config.



