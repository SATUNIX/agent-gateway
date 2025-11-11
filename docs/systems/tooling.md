# Tool & MCP Integration Guide

Agent Gateway exposes a unified tool layer consumed by declarative and SDK agents. Tools may be implemented locally (Python callables), via HTTP endpoints, or MCP servers. This document covers configuration, security constraints, and execution semantics.

## Tool Definitions (`src/config/tools.yaml`)

Each tool entry includes:

```yaml
version: 1
tools:
  - name: summarize_text
    provider: local
    module: tooling.local_tools:summarize_text
    schema:
      required: ["text"]
      properties:
        text:
          type: string
        max_words:
          type: integer

  - name: http_echo
    provider: http
    method: POST
    url: https://httpbin.org/post
    timeout: 5

  - name: weather_lookup
    provider: mcp
    url: https://mcp.example.com/weather
    method: current
    timeout: 10
    stream: true
```

- **provider**: `local`, `http`, or `mcp`.
- **module**: `module:function` path (local only). Restricted via the security allowlist.
- **url/method**: HTTP or MCP endpoints.
- **schema**: Optional lightweight validation (required keys + basic type checks).
- **stream**: For MCP, indicates whether to open an SSE stream (per MCP spec).

## Execution Flow

1. Agent emits an OpenAI tool call (`function.name`, `function.arguments`).
2. `ToolManager` validates arguments against the optional schema, enforces security allowlists, and records telemetry.
3. The tool provider executes:
   - **Local**: imports the module/function and executes it with `(arguments, context)`.
   - **HTTP**: issues a REST call (GET query params or JSON body).
   - **MCP**: uses the MCP client to invoke `method` with `arguments` and execution context. Supports HTTP POST or SSE streaming.
4. The result is appended as a `tool` role message and fed back to the agent loop.

## Security Considerations

- Local modules run inside the gateway process. Only allow trusted packages and maintain the security allowlist (`src/config/security.yaml -> local_tools_allowlist`).
- HTTP/MCP tools can exfiltrate data; ensure TLS and authentication as needed.
- Tool schemas provide a basic guardrail; consider wrapping sensitive tools with additional validation.

## Observability

- Every invocation logs `event="tool.invoke"` with tool name, provider, latency, status, and arguments.
- Metrics capture tool invocation counts/failures and latency histograms (exported via `/metrics` and Prometheus).

## MCP Support

- MCP tools POST `{method, arguments, context}` to the configured `url`.
- When `stream: true`, the MCP client opens an SSE stream and concatenates events as the tool result.
- The execution context includes agent name, user ID (if provided), and policy limits to help downstream auditing.

For implementation details see `tooling/manager.py` and `tooling/mcp_client.py`.
