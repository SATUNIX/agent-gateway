# SDK Agent Onboarding Guide

This guide explains how to expose an OpenAI Agents SDK-powered agent through Agent Gateway so that any OpenAI-compatible UI (Open WebUI, curl, etc.) can address it via the `/v1/chat/completions` `model` field.

## 1. Author the SDK Agent

1. Create (or reuse) a Python module that exports a callable factory in the form `module_path:callable_name`.
2. The callable may:
   - Return an object with `run_sync(...)` (preferred) or `run(...)` methods.
   - Return a plain callable that accepts `messages`, `request`, `policy`, and `client`.
   - Return an OpenAI-style completion payload (`ChatCompletionResponse` or `dict`) or a plain string (auto-wrapped by the gateway).
3. Factory arguments provided by the gateway:
   - `agent`: `AgentSpec` describing the YAML entry.
   - `client`: pre-configured OpenAI client for the agent’s upstream (LM Studio, Ollama, OpenAI, etc.).
   - `request`: original `ChatCompletionRequest`.
   - `messages`: merged system/history/input messages that the upstream would receive.
   - `policy`: hop/token limits derived from agent metadata.

See `src/agents/sdk_example.py` for reference factories (`build_agent`, `return_string_agent`).

## 2. Register the Agent

Edit `src/config/agents.yaml` and add a new entry:

```yaml
defaults:
  namespace: default
  upstream: lmstudio
  model: gpt-4o-mini

agents:
  - name: my_sdk_agent
    namespace: labs      # optional
    display_name: "Labs Assistant"
    description: "SDK-powered research agent"
    kind: sdk
    module: "my_package.agents:build_agent"
    tools:
      - summarize_text   # optional
    metadata:
      max_tool_hops: 3
      max_completion_tokens: 512
```

- `module` must be importable by the Python runtime (ensure the module is on `PYTHONPATH` or packaged with the gateway).
- Optional `metadata` fields are enforced by `AgentExecutor`.

## 3. Reload the Registry

During development, set `GATEWAY_AGENT_AUTO_RELOAD=true` (or run the server with `AgentRegistry(auto_reload=True)`), so YAML edits hot-reload automatically. In production, call `POST /agents/refresh` after deploying updated configs.

## 4. Invoke the Agent

Once registered, clients can use:

```bash
curl https://gateway-host/v1/chat/completions \
  -H "Authorization: Bearer <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
        "model": "labs/my_sdk_agent",
        "messages": [{"role": "user", "content": "Plan a trip to Lisbon."}]
      }'
```

The gateway resolves `labs/my_sdk_agent`, builds the context (system/history/input), runs the SDK module, and returns an OpenAI-compatible response.

## Gotchas

- **Import errors**: The gateway wraps import failures in `SDKAgentError`. Check logs for details.
- **Hot reload**: File timestamps must change for reload; ensure editors perform actual writes.
- **Tool access**: SDK agents can invoke tools simply by including tool names in the YAML `tools` list; the executor handles the loop automatically.
- **Security**: SDK modules run with the gateway’s Python interpreter; treat them as trusted code or sandbox them externally.
- **OpenAI Agents SDK examples**: You can drop in files such as `src/agents/proper_example.py` (see repo sample) and reference `module: agents.proper_example:build_agent`. Ensure the `openai-agents` package is installed and `OPENAI_BASE_URL`/`OPENAI_API_KEY` point to the gateway.

For automated regression tests of SDK ingestion, see `tests/test_sdk_adapter.py` and `tests/test_agent_registry.py`.
