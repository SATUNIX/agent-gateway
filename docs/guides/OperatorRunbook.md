# Operator Runbook

## Table of Contents
- [1. Configuration Sources](#1-configuration-sources)
- [2. Temporary Agent Overrides](#2-temporary-agent-overrides)
- [3. Security Refresh & Audit](#3-security-refresh--audit)
- [4. Incident Response Checklist](#4-incident-response-checklist)
- [5. Observability & Metrics](#5-observability--metrics)
- [6. Watch Mode & Auto-Reload](#6-watch-mode--auto-reload)

This runbook summarizes common day-2 workflows for Agent Gateway operators, with a focus on security controls, temporary overrides, and observability. The gateway is designed to expose OpenAI Agents SDK modules as `/v1/chat/completions` models through a single, policy-driven surface.

## 1. Configuration Sources

| Component | Location | Notes |
| --- | --- | --- |
| Agents | `src/config/agents.yaml` + `src/agents/**` | Declarative specs + drop-in SDK modules |
| Upstreams | `src/config/upstreams.yaml` | OpenAI-compatible providers |
| Tools | `src/config/tools.yaml` | Local / HTTP / MCP tooling definitions |
| Security | `src/config/security.yaml` | API keys, namespace defaults, drop-in policies |

Security config now supports **namespace defaults** (`default.namespace_defaults`) so teams can define policies such as `labs/*` without editing every key. Example:

```yaml
default:
  allow_agents:
    - "*"
  namespace_defaults:
    labs:
      allow_agents:
        - "labs/*"
```

## 2. Temporary Agent Overrides

Use the new admin endpoints to grant short-lived access without redeploying configs:

1. **Preview** the current decision:
   ```bash
   curl -X POST http://localhost:8000/security/preview \
     -H 'x-api-key: admin-key' \
     -H 'Content-Type: application/json' \
     -d '{"agent": "labs/sample"}'
   ```
   Response includes `allowed`, `source` (`api_key`, `namespace_default`, `override`, or `deny`), and the matching pattern.

2. **Create an override** when access is denied:
   ```bash
   curl -X POST http://localhost:8000/security/override \
     -H 'x-api-key: admin-key' \
     -H 'Content-Type: application/json' \
     -d '{"agent": "labs/sample", "ttl_seconds": 3600, "reason": "QA session"}'
   ```
   Overrides are stored in-memory with TTLs. They appear in logs as `agent.security.override.created` and automatically expire (also logged) once the TTL elapses.

3. **Monitor logs**: every allow/deny decision emits `agent.security.decision` with fields `agent`, `namespace`, `source`, `pattern`, and (for overrides) `reason` + `expires_at`.

## 3. Security Refresh & Audit

- `POST /security/refresh` reloads `src/config/security.yaml` from disk.
- `POST /security/preview` and `/security/override` work without reloads, operating on the in-memory policy surface.
- Nightly audit script: `python scripts/nightly_audit.py` (also used by CI) prints API key health summaries; review before releases.

## 4. Incident Response Checklist

1. **Unknown agent access denied** – issue `/security/preview` to confirm; apply a TTL override if needed and follow up with permanent config changes.
2. **Override cleanup** – overrides expire automatically; force cleanup by restarting the gateway or waiting for TTL. Log `agent.security.override.expired` confirms removal.
3. **Module blocked** – check logs for `agent.dropin.blocked` and adjust `dropin_module_allowlist` or namespace defaults, then `POST /security/refresh`.
4. **API key expiring** – watch for `api_key.expiring` warnings; rotate keys and redeploy `security.yaml`.

## 5. Observability & Metrics

- Decision logs: `agent.security.decision`, `agent.security.override.created`, `agent.security.override.expired`.
- Prometheus metrics: security counters for override usage and denied requests (see `/metrics` endpoint).
- Combine logs with `/admin/agents` diagnostics to troubleshoot drop-in readiness issues quickly.
- See `docs/systems/observability.md` for a full reference to logs, metrics, and error recorder usage.

## 6. Watch Mode & Auto-Reload

- **Enable:** Install the optional watch dependency (`pip install "agent-gateway[watch]"` or `pip install watchfiles`) and set `GATEWAY_AGENT_WATCH=1`.
- **Behavior:** A background watcher monitors `src/agents/**` and triggers incremental discovery reloads when `agent.py` files change. Diagnostics/logs still emit `agent.watch.started` / `agent.watch.stopped`.
- **Fallback:** If `watchfiles` is missing or the discovery root is unavailable, the gateway logs `agent.watch.disabled` and falls back to manual refresh (`POST /agents/refresh`).
- **Best practice:** Leave watch mode enabled in development environments for instant feedback; keep it off in prod if file watching is unnecessary or file systems lack inotify support.

With these controls, operators can keep the gateway locked down by default while still unblocking teams rapidly through auditable, temporary overrides.
