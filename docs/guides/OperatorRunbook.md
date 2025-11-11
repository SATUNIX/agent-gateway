# Operator Runbook

This runbook provides day-2 operations guidance for Agent Gateway, including configuration matrices, startup/shutdown procedures, and common recovery workflows.

## 1. Configuration Matrix

| Component | Config File | Override Env | Description |
| --- | --- | --- | --- |
| Agents | `src/config/agents.yaml` | `GATEWAY_AGENT_CONFIG` | Declarative + SDK agent definitions, namespace defaults, policies. |
| Upstreams | `src/config/upstreams.yaml` | `GATEWAY_UPSTREAM_CONFIG` | Backend endpoints (LM Studio, Ollama, OpenAI), health checks, secrets. |
| Tools | `src/config/tools.yaml` | `GATEWAY_TOOL_CONFIG` | Local/HTTP/MCP tools, schemas, MCP streaming flag. |
| Security | `src/config/security.yaml` | `GATEWAY_SECURITY_CONFIG` | API keys, ACLs, rate limits, tool allowlists. |
| Logging | n/a | `GATEWAY_LOG_LEVEL` | Structured log severity (INFO, DEBUG, etc.). |
| Metrics | n/a | `GATEWAY_PROMETHEUS_ENABLED` | Enables `/metrics/prometheus`. |

## 2. Deployment & Operations

### Startup
1. Ensure configs are mounted or baked into the container.
2. `make docker-build` (or pull from registry) and run via `docker-compose up --build`.
3. Validate `/health`, `/metrics`, and `/v1/chat/completions` smoke call.

### Shutdown
1. Drain clients or set upstreams to maintenance.
2. Stop gateway service (SIGTERM) and wait for connections to close.
3. Stop upstream/mocked services if running via `docker-compose`.

### Scaling
- Run multiple gateway instances behind an HTTP load balancer.
- Ensure shared volumes or config management keep YAML files consistent.
- Rate limiting is per API key per instance; coordinate global limits via load balancer if needed.

## 3. Routine Tasks

| Task | Command/Endpoint |
| --- | --- |
| Reload agents/tools/upstreams | `POST /agents/refresh`, `/tools/refresh`, `/upstreams/refresh`. |
| Reload security policies | `POST /security/refresh`. |
| Rotate API keys | Update `src/config/security.yaml`, reload, update clients, remove old keys. |
| Generate SBOM | `make sbom`. |
| Run nightly audit | `python scripts/nightly_audit.py` (automated in CI). |

## 4. Recovery Procedures

| Scenario | Action |
| --- | --- |
| Invalid agent module | Check logs (`SDKAgentError`), fix module path or code, reload agents. |
| Tool failure (HTTP/MCP) | Inspect tool logs (event `tool.invoke`), verify credentials/endpoints, adjust timeouts. |
| Upstream outages | Upstream metrics show increased failures—redirect traffic to backup upstream or reduce load. |
| Security breach/key leak | Rotate keys immediately (add new, reload, remove compromised). |
| Config errors | Use version control/backup to restore last known good YAML files, then reload. |

## 5. Observability Checklist

1. Ensure log ingestion picks up `request_id`, `event`, and `tool` fields.
2. Monitor Prometheus metrics:
   - `agent_gateway_request_latency_ms`
   - `agent_gateway_tool_invocations_total`
   - `agent_gateway_upstream_requests_total`
3. Set alerts for:
   - High 5xx rates or upstream failures.
   - Tool failure rate > threshold.
   - Rate-limit spikes (sustained 429 counts).

## 6. Disaster Recovery

1. Maintain backups of all config files and SBOMs (store in secure repo).
2. Document dependencies (e.g., S3 for logs, Prometheus for metrics).
3. For full rebuild:
   - Restore configs from backup.
   - Deploy new container image.
   - Re-run `POST /security/refresh`, `POST /agents/refresh`, etc.
   - Validate smoke tests before reintroducing traffic.
