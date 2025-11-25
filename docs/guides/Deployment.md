# Deployment Guide (V1)

## Table of Contents
- [1) Local Development (venv)](#1-local-development-venv)
- [2) Docker](#2-docker)
- [3) Docker Compose](#3-docker-compose)
- [4) Production Notes](#4-production-notes)
- [5) Health and Diagnostics](#5-health-and-diagnostics)
- [6) Ports and Networking](#6-ports-and-networking)
- [7) File Watching](#7-file-watching)
- [References](#references)

This guide covers common deployment methods for the Agent Gateway, including local dev, Docker, and Docker Compose. Choose the option that fits your environment.

## 1) Local Development (venv)
1. Clone repo and create venv:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
2. Optional dependencies:
   - Watch mode: `pip install "agent-gateway[watch]"`
   - SDK: `pip install openai-agents`
   - Agent-specific: `python scripts/install_agent_deps.py`
3. Env vars (examples):
   ```bash
   export PYTHONPATH=src
   export GATEWAY_SECURITY_CONFIG=src/config/security.yaml
   export GATEWAY_AGENT_CONFIG=src/config/agents.yaml
   ```
4. Run:
   ```bash
   uvicorn api.main:app --reload
   ```

## 2) Docker
1. Build:
   ```bash
   docker build -t agent-gateway:local .
   ```
2. Run with configs mounted (adjust paths as needed):
   ```bash
   docker run -p 8000:8000 \
     -e GATEWAY_SECURITY_CONFIG=/app/src/config/security.yaml \
     -e GATEWAY_AGENT_CONFIG=/app/src/config/agents.yaml \
     -e PYTHONPATH=/app/src \
     agent-gateway:local \
     uvicorn api.main:app --host 0.0.0.0 --port 8000
   ```
3. Mount drop-ins: bind-mount `src/agents` into the container or bake agents into the image.

## 3) Docker Compose
1. Use `docker-compose.yaml` as a template. Key mounts:
   - `./src/config:/app/src/config` for YAML configs.
   - `./src/agents:/app/src/agents` for drop-ins.
2. Start:
   ```bash
   docker-compose up --build
   ```
3. Environment overrides: set via `.env` or compose `environment:` section (e.g., `GATEWAY_AGENT_WATCH=0` in production).

## 4) Production Notes
- Disable `--reload` and watch mode; run with a process manager or container orchestration.
- Ensure `openai-agents` and agent-specific dependencies are present in the image (install via `scripts/install_agent_deps.py` during build).
- Set API keys and secrets via env vars, not committed files.
- Configure `GATEWAY_DEFAULT_MODEL` and `GATEWAY_DEFAULT_UPSTREAM` if drop-ins don’t specify `__gateway__` overrides.
- Expose `/metrics/prometheus` only when desired; secure admin endpoints with API keys.

## 5) Health and Diagnostics
- Health: `/health` and `/` basic probes.
- Models: `/v1/models` (requires API key).
- Agents/admin: `/admin/agents`, `/admin/agents/errors`, `/admin/metrics`.

## 6) Ports and Networking
- Default port: `8000` (uvicorn). Adjust via compose or `uvicorn` flags.
- Upstreams: ensure `src/config/upstreams.yaml` base URLs are reachable from the runtime environment (consider service DNS inside Compose/K8s).

## 7) File Watching
- Optional; enable with `GATEWAY_AGENT_WATCH=1` and install `watchfiles`.
- For containerized deployments, prefer manual refresh endpoints (`/admin/agents/refresh`) unless volume notifications are reliable.

## References
- System overview: `docs/guides/SystemOverview.md`
- Observability: `docs/systems/observability.md`
- Drop-in how-to: `docs/guides/DropInAgentGuide.md`
