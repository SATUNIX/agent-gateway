# System Overview (v1)

## Table of Contents
- [Architecture and Entry Points](#architecture-and-entry-points)
- [Discovery and Registry](#discovery-and-registry)
- [Security and Governance](#security-and-governance)
- [Chat Execution Flow](#chat-execution-flow)
- [Configuration Files (YAML)](#configuration-files-yaml)
- [Key Docs](#key-docs)

This guide describes how the Agent Gateway is wired end-to-end, with code and config references for developers preparing the V1 release.

## Architecture and Entry Points
- FastAPI app: `src/api/main.py` wires middleware (request IDs/logging), routers (`/v1/chat/completions`, `/v1/models`, `/admin/**`), and optional Prometheus metrics.
- Middleware: `src/api/middleware.py` sets `x-request-id` and structured log context.
- Observability: `src/observability/*`, `src/api/metrics.py`, error recorder (`src/observability/errors.py`), docs in `docs/systems/observability.md`.

## Discovery and Registry
- Declarative agents: `src/config/agents.yaml` parsed by `src/registry/agents.py` (`AgentsFile`/`AgentSpec` models in `src/registry/models.py`).
- Drop-in discovery: `src/registry/discovery.py` walks `agent.py` under `src/agents/**` and extra paths; diagnostics feed metrics and error recorder.
- Upstreams: `src/config/upstreams.yaml` → `src/registry/upstreams.py` builds OpenAI-compatible clients with health checks.
- Tools: `src/config/tools.yaml` → `src/tooling/manager.py` (local/http/MCP providers).

## Security and Governance
- API keys, rate limits, agent allowlists: `src/security/manager.py`, models in `src/security/models.py`, config in `src/config/security.yaml`.
- Tool allowlists: `default.local_tools_allowlist` enforces native tool usage; gateway-managed tools bypass manual allowlisting.
- Security endpoints: `/security/preview`, `/security/override` in `src/api/routes/admin.py`.

## Chat Execution Flow
1. `/v1/chat/completions` (`src/api/routes/chat.py`) validates payload (`src/api/models/chat.py`) and enforces API key (`src/api/auth.py` → `security.manager`).
2. `src/api/services/chat.py` delegates to `agents/executor.py` with ACL checks and error mapping (404/403/502).
3. Declarative agents call upstreams (`registry/upstreams.py` clients); tool calls run via `tooling/manager.py` with metrics/allowlist checks.
4. SDK agents run through `sdk_adapter/adapter.py`, with tool governance and optional streaming; requires `openai-agents` installed.
5. Streaming chunks are encoded in `api/services/streaming.py` (SSE).

## Configuration Files (YAML)
- `src/config/agents.yaml`: Declarative agents and defaults (namespace/upstream/model).
- `src/config/upstreams.yaml`: Upstream providers (base_url, provider, priority, health checks, secrets).
- `src/config/tools.yaml`: Gateway-managed tools (local/http/MCP definitions, schemas, timeouts).
- `src/config/security.yaml`: API keys, rate limits, agent allow/deny patterns, tool allowlists, drop-in module allow/deny lists, namespace defaults.

## Key Docs
- Drop-in how-to: `docs/guides/DropInAgentGuide.md`
- SDK onboarding: `docs/guides/SDKOnboarding.md`
- Operations: `docs/guides/OperatorRunbook.md`
- Observability: `docs/systems/observability.md`
- Troubleshooting: `docs/guides/Troubleshooting.md`
