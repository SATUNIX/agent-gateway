# Observability & Traceability Guide

Agent Gateway ships with built-in logging, metrics, and tracing hooks to help operators debug and monitor production deployments.

## Correlation IDs

- `RequestContextMiddleware` assigns a `x-request-id` header (or honors an incoming one) for every HTTP request.
- The request ID is propagated via context vars and included in:
  - Structured logs (request, tool invocations, security warnings, etc.).
  - HTTP responses (`x-request-id` header).
- Use this ID to correlate API logs, Prometheus entries, and downstream traces.

## Logging

- JSON logs include: timestamp, level, logger, request_id, message, and event-specific fields.
- `RequestLoggingMiddleware` logs every request with method/path/status/duration.
- Tool invocations (`event="tool.invoke"`) include provider, arguments, latency, status, and request_id.
- Security warnings (e.g., API key expirations) surface as structured log entries.

## Metrics

Endpoints:

- `GET /metrics` – JSON snapshot for quick checks.
- `GET /metrics/prometheus` – Prometheus scrape endpoint (set `GATEWAY_PROMETHEUS_ENABLED=true`).

Collected metrics:

- Request totals, streaming counts, and latency histograms.
- Tool invocations/failures + per-tool latency.
- Upstream requests per backend (success/failure counters + latency histograms).

Prometheus labels: `streaming`, `tool`, `provider`, `status`, `upstream`.

## Dashboards & Alerts (suggested)

- **Request Latency**: histogram_percentile of `agent_gateway_request_latency_ms`.
- **Tool Errors**: rate of `agent_gateway_tool_invocations_total{status="failure"}` by tool.
- **Upstream Health**: success vs failure ratio per upstream using `agent_gateway_upstream_requests_total`.
- **Security Alerts**: warnings from `api_key.expiring` log events (pipe to SIEM).

Sample Grafana panels can consume the above metrics; include `request_id` in log panel to cross-reference specific requests.
