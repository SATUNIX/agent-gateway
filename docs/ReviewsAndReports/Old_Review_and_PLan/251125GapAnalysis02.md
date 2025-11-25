# Gap Analysis Report

## Metadata
- Date: 2025-11-25
- Reviewer: Codex
- Codebase Version: 36683c4

## Summary
- Drop-in discovery, diagnostics, and admin/metrics surfaces are in place, and declarative payloads now include tool definitions, but core OpenAI Agents SDK integration remains incomplete.
- Streaming is buffered/synthetic and skips tool execution, so `/v1/chat/completions` does not yet mirror OpenAI-compatible streaming or tool-call flows.
- Agent Builder-style imports (`Agent`, `function_tool`, `Runner`) are blocked by the local `agents` package and missing SDK dependency, preventing the promised copy-paste drop-in experience.
- Scope excluded `examples/` as requested; `docs/plans/Gap_Analysis_Report.md` is missing, limiting verification against the referenced remediation plan.

## Gaps Identified
| Gap Description | Location/Module | Impact | Suggested Remediation |
| --- | --- | --- | --- |
| Agents SDK namespace conflict and missing dependency block Agent Builder imports | `agents/__init__.py`; `sdk_adapter/gateway_tools.py`; `sdk_adapter/adapter.py`; `requirements.txt` | Drop-in modules that import `Agent`/`function_tool`/`Runner` fail to load; `use_gateway_tool()` cannot import `function_tool`; SDK path cannot run OpenAI Agents objects | Add the OpenAI Agents SDK dependency, rename or re-export the local `agents` package to expose SDK primitives, and update `_load_runner`/`gateway_tools` to import from the SDK explicitly; add acceptance coverage for an Agent Builder export |
| OpenAI Agents adapter drops message context and bypasses configured upstream/streaming | `sdk_adapter/adapter.py::_run_openai_agent` | Conversation history is flattened into one prompt string, the provided upstream client is ignored, and no streaming/tool telemetry is emitted; Agent Builder agents diverge from expected behavior and may bypass gateway security/upstream routing | Convert ChatCompletion messages to the SDK’s input items (preserving roles/tool calls), invoke `Runner.run` with the gateway-provided client/upstream, and add streaming/delta passthrough plus gateway tool instrumentation |
| Streaming path is synthetic and tool loop is disabled when `stream=true` | `agents/executor.py::_invoke_declarative_stream`, `stream_completion` | SSE output is replayed from a buffered list; upstream streaming/tool_call deltas are not forwarded, and tool hops never run in streaming mode; clients expecting OpenAI-compatible streaming or tool chaining break | Stream upstream chunks asynchronously, execute tool_call deltas via `tool_manager`, and gate streaming when tool hops are unsupported to avoid silent skips |
| Gateway tooling governance is optional for SDK agents | `sdk_adapter/adapter.py`; `sdk_adapter/gateway_tools.py` | Native SDK `function_tool` calls bypass gateway metrics/ACLs unless authors manually wrap them; centralized tool observability/security is not guaranteed for drop-ins | Intercept or wrap SDK tool executions to route through `tool_manager`, enforce or document `use_gateway_tool` for shared tools, and extend tests to assert tool telemetry for SDK agents |
| Remediation reference missing (`docs/plans/Gap_Analysis_Report.md`) | Docs referencing the plan (e.g., `docs/ReviewsAndReports/Old_Review_and_PLan/DEVPLAN.md`) | The cited plan cannot be reviewed; contributors hit dead links and alignment with the intended remediation scope cannot be validated | Restore or recreate `docs/plans/Gap_Analysis_Report.md`, or update references to the current plan and map progress against it |

## Remediation Alignment
- Previously noted gaps around missing tool schemas and metrics have been partially addressed: declarative payloads now include tools/tool_choice, drop-in diagnostics surface via `/admin/agents` and metrics include tool/drop-in breakdowns, and the smoke/acceptance tests compile.
- The key remediation items for Agent Builder compatibility (SDK dependency, message preservation, streaming/tool governance) remain open, and the referenced `docs/plans/Gap_Analysis_Report.md` plan is absent, preventing full alignment verification.

## Agent Pattern Alignment
- Discovery/namespace mapping for `src/agents/**` and watch-mode coverage for `.py` and `requirements.txt` match the Spark/SampleAgent drop-in pattern.
- The runtime diverges from Spark/SampleAgent behavior: SDK primitives are unavailable due to the local `agents` package, the adapter flattens conversations instead of passing `TResponseInputItem` lists, no streaming/tool deltas are forwarded, and gateway-managed tooling is optional. As a result, Agent Builder exports will not behave the same when hosted here.

## Conclusion
The gateway is not yet aligned with the goal of “drop in an Agent Builder module and serve it via `/v1/chat/completions` without YAML edits.” Major blockers remain around the missing Agents SDK dependency/namespace conflict, loss of message context and upstream routing in the SDK adapter, synthetic streaming that skips tool execution, and the missing remediation plan document. Addressing these items is required before declaring the drop-in goal met.
