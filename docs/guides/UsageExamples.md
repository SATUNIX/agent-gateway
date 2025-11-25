# Usage Examples

## Table of Contents
- [List Models](#list-models)
- [Non-Streaming Chat Completion](#non-streaming-chat-completion)
- [Streaming Chat Completion (SSE)](#streaming-chat-completion-sse)
- [Admin Endpoints](#admin-endpoints)
- [Tooling Behavior](#tooling-behavior)
- [Error Shapes](#error-shapes)
- [Tracing a Request](#tracing-a-request)
- [References](#references)

This guide provides practical examples for calling the Agent Gateway API and interpreting responses.

## List Models
```bash
curl -H "x-api-key: dev-secret" http://localhost:8000/v1/models
```
Response includes `id`, `description`, and `metadata` (namespace, kind, dropin flag).

## Non-Streaming Chat Completion
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "x-api-key: dev-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "model":"default/sampleagent",
    "messages":[{"role":"user","content":"Hello"}],
    "stream": false
  }'
```
Response: OpenAI-compatible `chat.completion` with choices/usage.

## Streaming Chat Completion (SSE)
```bash
curl -N -X POST http://localhost:8000/v1/chat/completions \
  -H "x-api-key: dev-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "model":"default/sampleagent",
    "messages":[{"role":"user","content":"Stream this"}],
    "stream": true
  }'
```
Yields SSE lines (`data: {...}`) ending with `data: [DONE]`.

## Admin Endpoints
- Refresh agents: `curl -X POST -H "x-api-key: dev-secret" http://localhost:8000/admin/agents/refresh`
- Metrics snapshot: `curl -H "x-api-key: dev-secret" http://localhost:8000/admin/metrics`
- Recent errors: `curl -H "x-api-key: dev-secret" http://localhost:8000/admin/agents/errors`

## Tooling Behavior
- Gateway-managed tools: defined in `src/config/tools.yaml`, auto-available to declarative agents and SDK agents via `use_gateway_tool("name")`.
- Native SDK tools: require allowlist entry in `src/config/security.yaml` (`default.local_tools_allowlist`), otherwise a `PermissionError` is returned.

## Error Shapes
- Unknown model: HTTP 404 with message: `Unknown agent or model '<id>'. Register it in src/config/agents.yaml.`
- ACL denial: HTTP 403 with message: `API key does not permit access to agent '<id>'`.
- Tool allowlist violation: 403/PermissionError with remediation text about adding `local_tools_allowlist`.
- Discovery/import errors: listed under `/admin/agents` diagnostics and `/admin/agents/errors`, incrementing drop-in failure metrics.

## Tracing a Request
1. Send `x-request-id` or read it from the response header.
2. Inspect structured logs for `request_id`, `agent_id`, `module_path`, and `error_stage`.
3. Check `/admin/agents/errors` for correlated entries.
4. Review `/admin/metrics` (tool breakdown, drop-in failures) or Prometheus for counters/histograms.

## References
- API models: `src/api/models/chat.py`
- Executor/SDK adapter: `src/agents/executor.py`, `src/sdk_adapter/adapter.py`
- Observability: `docs/systems/observability.md`
- Troubleshooting: `docs/guides/Troubleshooting.md`
