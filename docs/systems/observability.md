# Observability Reference

This document describes how to inspect logs, metrics, and recent errors for the Agent Gateway. Use it to validate drop-in agent health, tool governance, and upstream behavior.

## Logging
- Structured JSON logs with request/agent context: `request_id`, `agent_id`, `module_path`, `error_stage`, `tool_name`, and event fields (e.g., `agent.security.decision`, `tool.invoke`, `sdk_agent.*`).
- Request IDs: Accept `x-request-id`; middleware sets/returns it on responses.
- Error recorder: Recent discovery/runtime issues are appended to the in-memory ring buffer and surfaced via `/admin/agents/errors`.

## Metrics
- Admin snapshot: `GET /admin/metrics` returns request counts/latency, tool breakdown (`source` label distinguishes sdk vs declarative), and drop-in failure counters.
- Prometheus: `GET /metrics/prometheus` (when enabled) exports counters/histograms:
  - `agent_gateway_requests_total{streaming=*}`
  - `agent_gateway_request_latency_ms`
  - `agent_gateway_tool_invocations_total{tool,provider,status,source}`
  - `agent_gateway_tool_latency_ms`
  - `agent_gateway_upstream_requests_total{upstream,status}`
  - `agent_gateway_dropin_failures_total{kind}`
- Drop-in failures increment on discovery/import/security/tool violations.

## Recent Errors
- Endpoint: `GET /admin/agents/errors` returns the ring buffer with timestamps, request IDs, module/file info, kind/severity, and messages.
- Discovery diagnostics: Import/dependency/security failures are recorded automatically and also exposed on `/admin/agents`.

## Request Tracing Workflow
1. Capture `x-request-id` from client or response.
2. Inspect logs for `error_stage` and `module_path` to locate failing components.
3. Check `/admin/agents/errors` for correlated discovery/runtime entries.
4. Review `/admin/metrics` and Prometheus counters for tool/drop-in/upstream anomalies.

## References
- Troubleshooting guide: `docs/guides/Troubleshooting.md`
- Drop-in guide: `docs/guides/DropInAgentGuide.md`
- SDK onboarding: `docs/guides/SDKOnboarding.md`
