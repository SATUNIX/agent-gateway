# Agent Gateway Documentation

This folder contains the living documentation for the Agent Gateway. Use it to learn how to run, extend, and operate the service for a V1-ready drop-in experience.

## Navigation
- `guides/`
  - `DropInAgentGuide.md` — How to add OpenAI Agents SDK modules (drop-ins), tooling, and watch mode (see code: `src/registry/agents.py`, `src/registry/discovery.py`).
  - `SDKOnboarding.md` — Onboarding for SDK authors (tools, dependencies, tests) with references to `sdk_adapter/` and `security/`.
  - `OperatorRunbook.md` — Day-2 operations, overrides, metrics, and refresh endpoints (admin APIs in `src/api/routes/admin.py`).
  - `Troubleshooting.md` — Common errors/remediations tied to `security.yaml`, tool allowlists, and discovery diagnostics.
  - `SystemOverview.md` — End-to-end architecture with code/config references for V1.
  - `Deployment.md` — Local, Docker, and Compose deployment patterns and production notes.
  - `UsageExamples.md` — Concrete API calls (models, chat, streaming), admin endpoints, and tracing.
- `systems/`
  - `observability.md` — Logging, metrics, request IDs, and error recorder usage (code: `src/observability/*`, `src/api/metrics.py`, `/admin/metrics`).
- `plans/`
  - `Gap_Analysis_Report.md` — Live gap-tracking reference.
  - `LaunchReadinessReview.md` — Release readiness checklist.
- `ReviewsAndReports/` — Current and historical gap analyses and development plans (latest: `251125GapAnalysis04.md`, `251125DevelopmentPlan04.md`).
- `UserManual.md` — Unified, production-grade manual with links to installs, configs, drop-ins, security, observability, and code map.

## How the Gateway Works (code pointers)
- Entry point: `src/api/main.py` wires middleware, routers, and metrics.
- Chat flow: `src/api/routes/chat.py` → `api/services/chat.py` → `agents/executor.py` → upstream clients (`registry/upstreams.py`) or SDK adapter (`sdk_adapter/adapter.py`).
- Discovery: `src/registry/agents.py` + `registry/discovery.py` auto-discover `agent.py` under `src/agents/**` (and extra paths) and merge with `config/agents.yaml`.
- Security: `src/security/manager.py` enforces API keys, rate limits, agent ACLs, and tool allowlists (`config/security.yaml`).
- Tooling: `src/tooling/manager.py` loads tools from `config/tools.yaml` and routes local/http/MCP calls.
- Observability: `src/observability/*`, `api/metrics.py`, error recorder in `observability/errors.py`, docs in `systems/observability.md`.

## Quick Start (developer)
1. Install deps: `pip install -r requirements.txt` (+ `openai-agents` for SDK agents).
2. Set env vars (examples):
   - `GATEWAY_SECURITY_CONFIG=src/config/security.yaml`
   - `GATEWAY_AGENT_CONFIG=src/config/agents.yaml`
   - `PYTHONPATH=src`
3. Run: `uvicorn api.main:app --reload`
4. List models: `curl -H "x-api-key: dev-secret" http://localhost:8000/v1/models`
5. Chat: `curl -X POST http://localhost:8000/v1/chat/completions -H "x-api-key: dev-secret" -H "Content-Type: application/json" -d '{"model":"default/sampleagent","messages":[{"role":"user","content":"Hi"}]}'`

## Testing
- Unit/acceptance: `make test` or `PYTHONPATH=src pytest`
- Drop-in acceptance: `make test-acceptance`
- Smoke: `make smoke`

## Observability Reference (summary)
- Logs: Structured JSON with `request_id`, `agent_id`, `module_path`, `error_stage`, tool/upstream events.
- Metrics: `/admin/metrics` (JSON) and `/metrics/prometheus` (Prometheus). Includes request latency, tool breakdown (`source` label distinguishes sdk vs declarative), upstream stats, drop-in failures.
- Errors: `/admin/agents/errors` exposes discovery/runtime ring buffer.
- Request context: `x-request-id` accepted/returned; middleware sets correlation IDs and log context.
See `systems/observability.md` for full details.

## Key Links
- Drop-in guide: `guides/DropInAgentGuide.md`
- SDK onboarding: `guides/SDKOnboarding.md`
- Troubleshooting: `guides/Troubleshooting.md`
- Observability: `systems/observability.md`
- Live gap reference: `plans/Gap_Analysis_Report.md`
- Current reports: `ReviewsAndReports/251125GapAnalysis04.md`, `ReviewsAndReports/251125DevelopmentPlan04.md`
