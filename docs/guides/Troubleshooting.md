# Troubleshooting Guide

## Table of Contents
- [Quick Reference Matrix](#quick-reference-matrix)
- [1. Discovery & Dependencies](#1-discovery--dependencies)
- [2. Security & Access](#2-security--access)
- [3. Tooling Issues](#3-tooling-issues)
- [4. Watch Mode & Reloads](#4-watch-mode--reloads)
- [5. Metrics & Observability](#5-metrics--observability)
- [Logs and Error Recorder](#logs-and-error-recorder)
- [6. Getting Help](#6-getting-help)

Use this guide to diagnose and resolve common drop-in agent issues. Each entry references relevant admin endpoints, logs, and scripts.

---

## Quick Reference Matrix

| Symptom | Likely Cause | Resolution |
| --- | --- | --- |
| Agent missing from `/v1/models` | Discovery/import failure, missing dependency, or security block | Check `/admin/agents/errors` and `/admin/agents`; install deps via `scripts/install_agent_deps.py`; review logs (`agent.dropin.blocked`). |
| 403 when invoking agent | API key lacks permission or override expired | Use `/security/preview` to inspect decision; create temporary access via `/security/override` or update `security.yaml`. |
| Streaming stops immediately | Agent returned full response (no delta) or raised exception | Inspect gateway logs for `sdk_agent.failure`; check `/admin/agents/errors`. |
| Tool invocation denied | Tool module not in `local_tools_allowlist` or blocked by security; native SDK tool not allowed | Update `src/config/security.yaml` and `POST /security/refresh`; gateway-managed tools are preferred; native SDK tools are auto-instrumented but must still satisfy allowlists. |
| Watch mode not active | `watchfiles` missing or unsupported FS | Install optional dependency (`pip install "agent-gateway[watch]"`) and verify logs (`agent.watch.started`); otherwise, refresh manually. |
| Missing dependencies during discovery | `requirements.txt` entry not installed | Run `python scripts/install_agent_deps.py` (optionally `--agent <Name>`). Diagnostics will clear on next reload. |
| Override expired unexpectedly | Small TTL or server restart | Check logs for `agent.security.override.expired`; recreate override or edit `security.yaml`. |

---

## 1. Discovery & Dependencies

### Indicators
- `/admin/agents` shows diagnostics like “Import failed” or “Missing dependencies”.
- `/admin/agents/errors` contains entries with `kind=discovery_dependency`.
- Logs contain `agent_discovery` events.

### Actions
1. Inspect the diagnostics:
   ```bash
   curl -H "x-api-key: admin" http://localhost:8000/admin/agents/errors | jq .
   ```
2. Install missing packages:
   ```bash
   python scripts/install_agent_deps.py --agent SampleAgent
   ```
3. Reload discovery:
   ```bash
   curl -X POST -H "x-api-key: admin" http://localhost:8000/admin/agents/refresh
   ```

---

## 2. Security & Access

### Indicators
- 403 responses from `/v1/chat/completions`.
- `/admin/agents/errors` contains `security` entries.
- Logs show `agent.security.decision` = `deny`.

### Actions
1. Preview the decision:
   ```bash
   curl -X POST http://localhost:8000/security/preview \
     -H "x-api-key: admin" \
     -H "Content-Type: application/json" \
     -d '{"agent":"labs/sampleagent"}'
   ```
2. Apply temporary override:
   ```bash
   curl -X POST http://localhost:8000/security/override \
     -H "x-api-key: admin" \
     -H "Content-Type: application/json" \
     -d '{"agent":"labs/sampleagent","ttl_seconds":3600,"reason":"QA"}'
   ```
3. For long-term fixes, edit `src/config/security.yaml` (allowlists, namespace defaults) and `POST /security/refresh`.

---

## 3. Tooling Issues

### Indicators
- Logs: `tool.invoke` with `status=failure`.
- `/admin/agents/errors` shows `tool_violation`.
- Prometheus counter `agent_gateway_dropin_failures_total{kind="tool_violation"}` increments.

### Actions
1. Ensure gateway-managed tools are defined in `src/config/tools.yaml`.
2. For SDK tools, confirm `@function_tool` usage and that the output type matches expectations.
3. When using shared tools, prefer `use_gateway_tool("name")` so ACLs, retries, and metrics apply consistently.
4. Update `security.yaml` allowlists if the tool module is blocked.

---

## 4. Watch Mode & Reloads

### Indicators
- New agent folders are not detected automatically.
- Logs show `agent.watch.disabled`.

### Actions
1. Install watch dependency:
   ```bash
   pip install "agent-gateway[watch]"
   ```
2. Set env var and restart:
   ```bash
   export GATEWAY_AGENT_WATCH=1
   PYTHONPATH=src uvicorn api.main:app --reload
   ```
3. If watch mode cannot run (e.g., network mounts), disable it and call `/admin/agents/refresh` manually after changes.

---

## 5. Metrics & Observability

Use Prometheus to track:

| Metric | Description |
| --- | --- |
| `agent_gateway_dropin_failures_total{kind=...}` | Counts discovery/security/tool failures |
| `agent_gateway_tool_invocations_total` | Includes `source` label (gateway vs. declarative) |
| `agent_gateway_request_latency_ms` | Overall request latency |

Bind dashboards/alerts to these metrics to detect regressions early.

### Logs and Error Recorder
- Logs are structured JSON with `request_id`, `agent_id`, `module_path`, `error_stage`, and event fields (`tool.invoke`, `sdk_agent.*`, `agent.security.decision`).
- Recent errors: `/admin/agents/errors` exposes discovery/runtime issues with timestamps and context.
- See `docs/systems/observability.md` for end-to-end observability guidance.

---

## 6. Getting Help

- **Logs:** Structured JSON with `request_id`, `agent_id`, `module_path`, `error_stage`.
- **Admin endpoints:** `/admin/agents`, `/admin/agents/errors`, `/security/*`.
- **Docs:** `docs/guides/DropInAgentGuide.md`, `docs/guides/SDKOnboarding.md`, `docs/guides/OperatorRunbook.md`.

By following this guide, operators and developers can quickly diagnose drop-in issues and keep the gateway dependable for production use.
