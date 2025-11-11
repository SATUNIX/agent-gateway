# Load, Stress, and Resiliency Plan

This document outlines the approach for validating Agent Gateway under production load and ensuring graceful degradation.

## 1. Load Testing

Use the provided Locust scenario (`load/locustfile.py`) or k6 equivalent to simulate chat workloads:

- Ramp up to target QPS (e.g., 50 requests/sec) with 70% non-streaming, 30% streaming traffic.
- Randomize agents between declarative and SDK variants, including tool-enabled agents.
- Measure p95/p99 latency, error rates, and tool/upstream saturation.

Run with:

```bash
locust -f load/locustfile.py --host https://gateway-host --users 200 --spawn-rate 20
```

## 2. Stress & Failure Injection

- Simulate upstream latency spikes (e.g., delay LM Studio) and verify the gateway surfaces 502 errors while preserving health.
- Force tool failures (HTTP 500, MCP timeouts) to ensure retries/backpressure behave and logs capture the request ID.
- Exceed per-key rate limits to confirm 429 responses and verify logs/metrics reflect throttling.

## 3. Resource Caps

- Configure process-level limits (uvicorn workers, Gunicorn) and monitor CPU/memory under load.
- Ensure rate limiting and upstream health checks prevent cascading failures.

## 4. Resiliency Checklist

- [ ] Rate limits documented/configured per key.
- [ ] Alerts for elevated upstream failures.
- [ ] Tool/MCP endpoints monitored (latency/error budgets).
- [ ] `/security/refresh` process tested post-rotation.
- [ ] Backups of configs & SBOMs stored securely.
