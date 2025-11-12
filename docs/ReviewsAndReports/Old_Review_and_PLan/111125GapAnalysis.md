# Agent Gateway Drop-in Agent Gap Analysis Report

## 1. Executive Summary

The SATUNIX/agent-gateway supports integration of OpenAI Agents SDK agents as drop-ins, but only when they conform to specific gateway-level conventions. While the core discovery and adapter layers align with the OpenAI Agents SDK, several conditional requirements and implicit dependencies create friction for external developers attempting to drop in pre-built agents. The following analysis compares the **intended SDK behavior** with the **gateway’s current implementation**, highlighting functional gaps, configuration dependencies, and developer experience issues.

---

## 2. Key Findings

### ✅ Strengths

* **SDK Compatibility:** The gateway is fundamentally compliant with the OpenAI Agents SDK. Any valid `Agent(...)` instance or factory can be executed once discovered.
* **Auto-discovery:** Files under `src/agents/**/agent.py` are automatically scanned and loaded.
* **Security Model:** Centralized allowlists (in `security.yaml`) for module and tool access enhance security and prevent untrusted code execution.
* **Tool Governance:** Integration of `gateway_tool()` and `tools.yaml` ensures consistent ACL enforcement for tool invocation.

### ⚠️ Major Gaps

1. **Strict discovery and naming conventions** — Agents must be named and located precisely under `src/agents/<AgentName>/agent.py`. Alternate layouts or naming require manual configuration.
2. **Export dependency** — Only modules exporting `agent` or a discoverable `Agent` instance are registered. Any other naming pattern (`my_agent`, `app_agent`) requires special handling.
3. **Missing configuration defaults** — Agents without default `upstream` and `model` values fail silently during discovery.
4. **Security and ACL coupling** — The allowlist system can unexpectedly block agents or tools not pre-registered.
5. **No dependency bootstrap** — Drop-in folders with `requirements.txt` are ignored; dependencies must be manually installed.
6. **Incomplete documentation** — The repository references guides that do not exist (`DropInAgentGuide.md`, `Troubleshooting.md`).
7. **Opaque error reporting** — Validation errors (e.g., missing defaults or denied modules) are logged but not surfaced in API responses.

---

## 3. Gap Analysis Table

| Category                   | Gap Description                                       | Impact | Required Fix                                   | Effort | Priority |
| -------------------------- | ----------------------------------------------------- | ------ | ---------------------------------------------- | ------ | -------- |
| **File Discovery**         | Agents must be placed in `src/agents/<Name>/agent.py` | Medium | Add configuration override or relaxed search   | Medium | High     |
| **Export Symbol**          | Non-`agent` variable names not auto-registered        | High   | Add support for `__gateway__` export metadata  | Low    | High     |
| **Configuration Defaults** | Missing `upstream`/`model` drop agents silently       | High   | Provide fallback defaults in environment       | Medium | High     |
| **Security Policy**        | Default allowlists may reject valid agents/tools      | Medium | Improve diagnostics; log cause in `/v1/models` | Medium | Medium   |
| **Dependency Handling**    | No auto-install for `requirements.txt`                | High   | Add pre-load dependency check/installer        | High   | High     |
| **Tool Registration**      | Tools not wrapped with `gateway_tool()` blocked       | Medium | Add auto-wrapping of SDK `function_tool`       | Medium | Medium   |
| **Error Visibility**       | Failures only logged, not surfaced via API            | Medium | Expose registry diagnostics via `/v1/models`   | Medium | Medium   |
| **Docs Availability**      | Missing guides in `docs/guides/`                      | Low    | Regenerate guides from current spec            | Low    | Medium   |

---

## 4. Developer Experience (UX) Impacts

| UX Area                   | Problem                                                          | Developer Impact                                                        |
| ------------------------- | ---------------------------------------------------------------- | ----------------------------------------------------------------------- |
| **Onboarding**            | Missing `DropInAgentGuide.md` leaves unclear setup instructions. | Increases time to configure and test drop-ins.                          |
| **Error Feedback**        | Silent failures on missing defaults or denied security modules.  | Leads to confusion — agents appear missing from `/v1/models`.           |
| **Tool Integration**      | Wrapping tools manually adds complexity for simple SDK agents.   | Developers must refactor existing tools to align with `gateway_tool()`. |
| **Dependency Isolation**  | No per-agent dependency management.                              | Requires full environment rebuilds for new agents.                      |
| **Security Restrictions** | Restrictive ACLs require YAML modification for each new tool.    | Hinders rapid experimentation or local testing.                         |

---

## 5. Recommendations

1. **Introduce auto-discovery improvements**
   Allow more flexible file naming (`agent.py`, `main.py`, `__init__.py`) via configuration (`agents.discovery.pattern`).

2. **Add automatic export resolution**
   Permit explicit metadata in modules (e.g., `__gateway__ = {"export": "my_agent"}`) to declare agent entry points.

3. **Provide fallback defaults**
   If `upstream` or `model` are missing, use environment variables or a fallback constant to avoid silent drops.

4. **Dependency auto-installation**
   Add a hook that installs or validates `requirements.txt` when discovering new drop-ins.

5. **Improved diagnostics endpoint**
   Extend `/v1/models` response with detailed diagnostics (reason for drop, config validation errors, security violations).

6. **Restore missing documentation**
   Recreate `docs/guides/DropInAgentGuide.md` and `Troubleshooting.md` from the analysis content.

7. **Relax tool ACLs for dev mode**
   Introduce a `GATEWAY_SECURITY_MODE=dev` environment flag that disables strict allowlists for local testing.

---

## 6. Conclusion

The gateway is architecturally sound and compatible with OpenAI’s Agents SDK, but it requires **tight adherence to internal configuration rules**. The largest usability gaps stem from missing defaults, lack of dependency management, and silent validation failures. Addressing these areas would substantially improve the developer experience and allow true plug-and-play drop-in behavior.

---

### Status Summary

| Category               | Status               |
| ---------------------- | -------------------- |
| SDK Compatibility      | ✅ Compatible         |
| Drop-in Simplicity     | ⚠️ Conditional       |
| Documentation          | ❌ Missing            |
| Dependency Handling    | ❌ Manual             |
| Security Configuration | ⚠️ Context-dependent |
| Developer UX           | ⚠️ Moderate friction |

---

**Overall Readiness:** ⏳ *Partially Drop-in Ready*
With improved defaults, dependency hooks, and updated documentation, the SATUNIX Agent Gateway could achieve full SDK drop-in compatibility.
