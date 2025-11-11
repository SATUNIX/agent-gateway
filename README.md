# Agent Gateway

**Agent Gateway** is a modular, **OpenAI-compatible orchestration service** that connects your chat UI to both local and cloud-based LLM backends (OpenAI, LM Studio, Ollama, vLLM) through the **OpenAI Agents SDK**.
Drop a standard SDK agent into `src/agents/<Name>/agent.py`, and the gateway automatically exposes it as a `/v1/chat/completions` model—complete with routing, tooling, observability, and security.

<p align="center">
  <img width="940" height="539" alt="Agent Gateway Architecture" src="https://github.com/user-attachments/assets/192d84e2-7360-4e89-9f91-0019b6999cdd" />
</p>

---

## 📚 Table of Contents

* [Highlights](#highlights)
* [Quick Start](#quick-start)

  * [Linux/macOS](#linuxmacos)
  * [Windows](#windows)
* [Drop-in Agent Workflow](#drop-in-agent-workflow)
* [Configuration & Documentation](#configuration--documentation)
* [Troubleshooting](#troubleshooting)
* [Make Targets](#make-targets)
* [API Surface](#api-surface)
* [Observability & Security](#observability--security)
* [Testing & Packaging](#testing--packaging)
* [Roadmap](#roadmap)
* [Example Agents](#example-agents)

---

## 🚀 Highlights

| Capability                | Description                                                                                                                                               |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **OpenAI-Compatible API** | `/v1/chat/completions` (with streaming SSE) and admin endpoints for agents, upstreams, tools, and security.                                               |
| **Drop-in SDK Agents**    | Agents under `src/agents/**` are automatically registered as models—no YAML edits required. Supports hooks, handoffs, guardrails, and structured outputs. |
| **Tooling**               | Centralized Tool/MCP manager for local Python, HTTP, and MCP providers. Includes the `use_gateway_tool()` shim so SDK agents can reuse gateway tools.                            |
| **Routing**               | Namespace-aware registries map models to upstream providers (OpenAI, LM Studio, Ollama, etc.) with per-agent execution policies.                          |
| **Security**              | API keys, ACLs, rate limits, tool allowlists, module allow/deny lists, and nightly audit scripts.                                                         |
| **Observability**         | Structured logs, Prometheus metrics, request IDs, and visual dashboards (`docs/systems/observability.md`).                                                |
| **Packaging**             | Multi-stage Dockerfile, Docker Compose stack, SBOM generation, CI/CD pipeline, and operator runbooks.                                                     |

---

## ⚡ Quick Start

### Linux/macOS

```bash
git clone https://github.com/<org>/agent-gateway.git
cd agent-gateway
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp src/config/security.yaml src/config/security.local.yaml
export GATEWAY_SECURITY_CONFIG=src/config/security.yaml
export PYTHONPATH=src
uvicorn api.main:app --reload
```

Visit:

* `http://127.0.0.1:8000/docs` → OpenAPI Explorer
* `http://127.0.0.1:8000/v1/models` → Discovered agents (use `x-api-key`)

### Windows

```powershell
git clone https://github.com/<org>/agent-gateway.git
cd agent-gateway
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
setx GATEWAY_SECURITY_CONFIG "%CD%\src\config\security.yaml"
set PYTHONPATH=%CD%\src
uvicorn api.main:app --reload
```

> 💡 **Tip:** Set `GATEWAY_AGENT_AUTO_RELOAD=1` during development to enable hot-reload for YAML and drop-in modules.

---

## 🧩 Drop-in Agent Workflow

1. **Write an SDK Agent** under `src/agents/<AgentName>/agent.py`:

   ```python
   from agents import Agent, function_tool

   @function_tool
   def get_weather(city: str) -> str:
       return f"The weather in {city} is sunny"

   agent = Agent(name="Weather Agent", instructions="Always respond with weather.", tools=[get_weather])
   ```
2. **Run the Gateway**

   ```bash
   PYTHONPATH=src uvicorn api.main:app --reload
   ```
3. **List Models**

   ```bash
   curl -H "x-api-key: dev-secret" http://localhost:8000/v1/models
   ```
4. **Chat with an Agent**

   ```json
   {"model": "default/weatheragent", "messages": [{"role": "user", "content": "Weather in Tokyo"}]}
   ```
5. **Optional:** Use `use_gateway_tool()` to wrap entries from `src/config/tools.yaml` for centralized logging and ACLs.

Example (mixing native + gateway tools):

```python
from agents import Agent, function_tool
from sdk_adapter.gateway_tools import use_gateway_tool

@function_tool
def summarize(text: str) -> str:
    return text[:120] + "..."

http_echo = use_gateway_tool("http_echo")

agent = Agent(
    name="SampleAgent",
    instructions="Use summarize() for local context and http_echo for diagnostics.",
    tools=[summarize, http_echo],
)
```

See [`docs/guides/DropInAgentGuide.md`](docs/guides/DropInAgentGuide.md) for conventions, fixtures, and troubleshooting.

---

## ⚙️ Configuration & Documentation

| File                        | Purpose                                                     |
| --------------------------- | ----------------------------------------------------------- |
| `src/config/agents.yaml`    | Declarative agent registry (legacy, still supported).       |
| `src/config/upstreams.yaml` | Defines upstream LLM providers (URLs, keys, health checks). |
| `src/config/tools.yaml`     | Registry for gateway-managed tools.                         |
| `src/config/security.yaml`  | API keys, ACLs, tool/module allow/deny lists.               |
| `docs/`                     | Contains guides, references, and system docs.               |

**Environment Variables:**
`GATEWAY_AGENT_CONFIG`, `GATEWAY_UPSTREAM_CONFIG`, `GATEWAY_SECURITY_CONFIG`, `GATEWAY_AGENT_DISCOVERY_PATH`, `GATEWAY_AGENT_AUTO_RELOAD`, etc.

---

## 🧰 Troubleshooting

| Issue                            | Resolution                                                                                 |
| -------------------------------- | ------------------------------------------------------------------------------------------ |
| Agent not listed in `/v1/models` | Check logs for `agent.dropin.blocked` or import errors. Ensure the module exports `agent`. |
| 403 Forbidden                    | Tool or module not in `allowlist`. Update `src/config/security.yaml`.                      |
| Streaming ends early             | Confirm `stream:true` in request payload.                                                  |
| `PermissionError`                | Ensure `openai-agents` is installed in the active environment.                             |
| Rate limit (429)                 | Increase `rate_limit.per_minute` or rotate API keys.                                       |

See [`docs/guides/Troubleshooting.md`](docs/guides/Troubleshooting.md) for deeper debugging.

---

## 🧱 Make Targets

| Target                        | Description                               |
| ----------------------------- | ----------------------------------------- |
| `make run`                    | Start FastAPI app with reload.            |
| `make fmt` / `make lint`      | Format and lint code via Ruff.            |
| `make test` / `make coverage` | Run pytest and generate coverage reports. |
| `make smoke`                  | Execute end-to-end smoke test.            |
| `make docker-build`           | Build container image.                    |
| `make sbom`                   | Generate CycloneDX SBOM.                  |

---

## 🌐 API Surface

| Endpoint                          | Description                                       |
| --------------------------------- | ------------------------------------------------- |
| `POST /v1/chat/completions`       | OpenAI-compatible chat completion (supports SSE). |
| `GET /v1/models`                  | List ACL-filtered models.                         |
| `/agents`, `/upstreams`, `/tools` | Admin endpoints for registry refresh.             |
| `/security/refresh`               | Reload and validate API keys.                     |
| `/metrics`, `/metrics/prometheus` | Metrics JSON and Prometheus exporter.             |
| `/health`                         | Lightweight liveness probe.                       |

> All admin endpoints require `x-api-key`. Unauthorized or rate-limited requests return `403` or `429`.

---

## 🔍 Observability & Security

* **Logs:** Structured JSON with request IDs and tool invocation traces.
* **Metrics:** `/metrics` and `/metrics/prometheus` endpoints for performance data.
* **Security:** API keys, ACLs, rate limits, audit scripts, and nightly verification.

---

## 🧪 Testing & Packaging

* Full `pytest` coverage for registries, adapters, tools, and API routes.
* Canonical SDK examples in `tests/fixtures/dropin_agents`.
* `Dockerfile` and `docker-compose.yaml` for reproducible builds.
* Release pipelines include signed images, SBOMs, and changelog updates.

---

## 🗺️ Roadmap

Development milestones are tracked in
`docs/plans/AgentGateway_10-Step_Development_Plan.md`
A new plan will follow after the initial alpha release and capability assessment.

---

## 🧠 Example Agents

These examples represent the three levels of agent complexity available for initial experimentation.

<div align="center">

|                                             **Cortex** <br> *A large Mixture of Agents*                                             |                                            **Synapse** <br> *A moderate Mixture of Agents*                                           |                                          **Spark** <br> *A lightweight Mixture of Agents*                                          |
| :---------------------------------------------------------------------------------------------------------------------------------: | :----------------------------------------------------------------------------------------------------------------------------------: | :--------------------------------------------------------------------------------------------------------------------------------: |
| <img width="250" height="250" alt="Cortex" src="https://github.com/user-attachments/assets/8bf78a61-f799-425f-b882-1e7c4f032807" /> | <img width="250" height="250" alt="Synapse" src="https://github.com/user-attachments/assets/18c46ce2-2269-4b11-94b4-adfd0c67b1bf" /> | <img width="250" height="250" alt="Spark" src="https://github.com/user-attachments/assets/56cfb5a1-9039-44c5-8f47-d699f6618b0a" /> |

</div>

---
