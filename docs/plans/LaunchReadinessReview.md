# Launch Readiness Review

Use this checklist before tagging a release or promoting Agent Gateway to a new environment. Each item ensures the drop-in UX (“copy agent → serve via `/v1/chat/completions`”) remains intact.

---

## 1. Security & Overrides

- [ ] Confirm `src/config/security.yaml` matches the intended namespace defaults and allowlists.
- [ ] List active overrides via `POST /security/preview` and ensure temporary overrides are documented or cleared.
- [ ] Review logs for `agent.security.decision` anomalies; resolve any unexpected `deny` events.

## 2. Dependency & Discovery Health

- [ ] Run `python scripts/install_agent_deps.py` (with `--agent` filters if needed) to install agent-specific dependencies.
- [ ] Check `/admin/agents` and `/admin/agents/errors` for discovery/import failures; address missing deps or blocked modules.
- [ ] Ensure drop-in acceptance suite is green: `make test-acceptance`.

## 3. CI/Lint/Test Status

- [ ] Verify GitHub Actions `build-test` job succeeded (lint, unit, drop-in acceptance, dependency audit).
- [ ] Verify `nightly-audit` job succeeded or rerun `python scripts/nightly_audit.py` locally if needed.
- [ ] Confirm `agent_gateway_dropin_failures_total` counters are stable (no ongoing spikes).

## 4. Documentation & UX

- [ ] README, `docs/guides/DropInAgentGuide.md`, `docs/guides/SDKOnboarding.md`, and `docs/guides/Troubleshooting.md` reflect the latest workflows (watch mode, overrides, dependency helper).
- [ ] Operator Runbook includes any operational changes (watch mode toggles, new admin endpoints).
- [ ] Update release notes or changelog with relevant highlights and breaking changes.

## 5. Metrics & Alerts

- [ ] Prometheus dashboards show healthy request/tool/agent metrics; alert thresholds updated if necessary.
- [ ] Ensure alerting hooks (CI notify jobs) are functioning; address any open incidents triggered by recent failures.

Completing this checklist ensures each release maintains the promised drop-in experience with clear operational visibility.
