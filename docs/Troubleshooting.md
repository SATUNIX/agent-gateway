# Troubleshooting Guide

## 1. Common Errors

| Symptom | Possible Cause | Resolution |
| --- | --- | --- |
| `401 Unauthorized` | Missing/invalid `x-api-key` header | Verify key, rotate if expired, reload security config. |
| `403 Agent not allowed` | API key ACL denies the requested agent | Update `allow_agents` for the key or use permitted agent. |
| `429 Rate limit exceeded` | Sliding-window quota reached | Increase `rate_limit.per_minute`, add more keys, or throttle clients. |
| `502 Upstream failure` | Upstream LLM unavailable/slow | Check upstream logs, health checks, and metrics; fail over to another upstream. |
| Tool invocation error | Invalid arguments or allowlist violation | Check tool schema, ensure module is whitelisted, validate MCP endpoints. |
| SDK import failure | Wrong `module:function` path | Confirm module is on `PYTHONPATH`, fix YAML entry, rerun `POST /agents/refresh`. |

## 2. Debugging Steps

1. Grab the `x-request-id` from the response header.
2. Search logs for matching `request_id` to see request, tool, and upstream traces.
3. Inspect `/metrics` for spikes (latency, tool failures, upstream errors).
4. Confirm configuration state via admin endpoints (`/agents`, `/tools`, `/security/refresh` summary).

## 3. Hot Reload Failures

If registry changes aren’t taking effect:
- Ensure files are saved with updated timestamps.
- Confirm `GATEWAY_*_AUTO_RELOAD=true` or call the relevant `/refresh` endpoint.
- Check logs for YAML validation errors.

## 4. Tool Sandbox Issues

“Tool not permitted” indicates the module path is missing from `local_tools_allowlist`. Update `config/security.yaml`, then `POST /security/refresh`.

## 5. MCP Connectivity

- Verify MCP URL accepts POST requests and, if streaming, emits SSE lines.
- Ensure TLS/headers are configured correctly in `config/tools.yaml`.
- Use logs (`event="tool.invoke"`) to view MCP payloads and errors.
