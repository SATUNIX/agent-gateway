# Agent Gateway User Manual (V1)

This manual provides a production-grade, end-to-end guide to installing, configuring, running, and operating the Agent Gateway. It links to detailed guides and code/config references.

## Table of Contents
- [1. Overview](#1-overview)
- [2. Install & Run](#2-install--run)
- [3. Configuration](#3-configuration)
- [4. Drop-In Agents](#4-drop-in-agents)
- [5. Security & Governance](#5-security--governance)
- [6. Observability](#6-observability)
- [7. Admin & Operations](#7-admin--operations)
- [8. Deployment](#8-deployment)
- [9. Testing](#9-testing)
- [10. Troubleshooting](#10-troubleshooting)
- [11. Code Map](#11-code-map)

## 1. Overview
- What it is: FastAPI gateway exposing OpenAI-compatible `/v1/chat/completions` with auto-discovered drop-in agents.
- Architecture: See `docs/guides/SystemOverview.md`.
- Entry point: `src/api/main.py`.

## 2. Install & Run
- Local dev: venv + `pip install -r requirements.txt`.
- Optional: `openai-agents`, `agent-gateway[watch]`, `scripts/install_agent_deps.py`.
- Quick start commands: see `docs/README.md` (Quick Start).
- Example run: `PYTHONPATH=src uvicorn api.main:app --reload`.

## 3. Configuration
- Agents: `src/config/agents.yaml` (declarative) + drop-in discovery under `src/agents/**`.
- Upstreams: `src/config/upstreams.yaml` (base_url, provider, priority, health checks).
- Tools: `src/config/tools.yaml` (local/http/MCP definitions).
- Security: `src/config/security.yaml` (API keys, rate limits, agent allowlists, tool allowlists).
- Env overrides: see `config/settings.py` and `docs/guides/SystemOverview.md`.

## 4. Drop-In Agents
- How to add: `docs/guides/DropInAgentGuide.md`.
- Discovery paths: `src/registry/discovery.py`, defaults include `src/agents/**` plus extra paths.
- SDK onboarding: `docs/guides/SDKOnboarding.md`.
- Dependencies: place `requirements.txt` per agent; install via `scripts/install_agent_deps.py`.

## 5. Security & Governance
- API key auth and rate limits: `src/security/manager.py`, config `security.yaml`.
- Agent ACLs & overrides: `/security/preview`, `/security/override` (admin routes).
- Tool allowlists: native tools require entries in `default.local_tools_allowlist`; gateway-managed tools preferred.
- Logging: decisions emitted as `agent.security.decision`.

## 6. Observability
- Reference: `docs/systems/observability.md`.
- Logs: structured JSON with `request_id`, `agent_id`, `module_path`, `error_stage`.
- Metrics: `/admin/metrics` JSON and `/metrics/prometheus` (when enabled); includes tool breakdown, drop-in failures, upstream metrics.
- Errors: `/admin/agents/errors` ring buffer for discovery/runtime issues.

## 7. Admin & Operations
- Endpoints: `/admin/agents`, `/admin/agents/errors`, `/admin/metrics`, `/admin/tools`, `/admin/upstreams`, refresh endpoints.
- Operator tips: `docs/guides/OperatorRunbook.md`.

## 8. Deployment
- Options: local venv, Docker, Docker Compose.
- Guide: `docs/guides/Deployment.md` (ports, mounts, envs, production notes).

## 9. Testing
- Unit/acceptance: `make test`, `make test-acceptance`.
- Smoke: `make smoke`.
- SDK/drop-in fixtures: `tests/fixtures/`.
- Guidance: `docs/guides/UsageExamples.md` and test targets in `README`.

## 10. Troubleshooting
- Quick fixes and error shapes: `docs/guides/Troubleshooting.md`.
- Tool allowlist issues, missing deps, ACL denials, watch mode.

## 11. Code Map
- API: `src/api/main.py`, `src/api/routes/*`, `src/api/services/chat.py`, `src/api/models/*`.
- Agents: `src/agents/executor.py`, `src/sdk_adapter/adapter.py`, `src/agents/__init__.py`.
- Registry: `src/registry/agents.py`, `src/registry/discovery.py`, `src/registry/models.py`, `src/registry/upstreams.py`.
- Tooling: `src/tooling/manager.py`, `src/tooling/mcp_client.py`, `src/tooling/local_tools.py`.
- Security: `src/security/manager.py`, `src/security/models.py`.
- Observability: `src/observability/*`, `src/api/metrics.py`, `src/observability/errors.py`.
