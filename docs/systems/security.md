# Security & Key Management Guide

Agent Gateway enforces API-key authentication, per-agent allowlists, rate limiting, and local tool sandboxing. This guide explains how to manage keys, rotate secrets, and reload security policies without downtime.

## Configuration (`src/config/security.yaml`)

```yaml
version: 1
default:
  allow_agents:
    - "*"
  rate_limit:
    per_minute: 60
  local_tools_allowlist:
    - "tooling.local_tools:*"

api_keys:
  - id: "ops"
    key: "plain-text-dev-key"        # Omit in production
    hashed_key: "sha256:..."         # Preferred: `echo -n key | sha256sum`
    description: "Operations team key"
    allow_agents:
      - "default/*"
    rate_limit:
      per_minute: 120
    expires_at: "2025-01-01T00:00:00Z"
```

- **key**: Optional plaintext (use only for local dev). In production, set `hashed_key` to the SHA-256 digest and omit `key`.
- **allow_agents**: Patterns (`*`, `namespace/*`, `namespace/agent`).
- **rate_limit**: Sliding-window requests per minute.
- **expires_at**: ISO timestamp used for rotation reminders.

## Reloading Policies

- **Hot reload**: `POST /security/refresh` (requires admin API key) reloads `src/config/security.yaml` and returns sanitized key metadata.
- **Auto reload**: Not enabled by default (to avoid accidental changes). Use the admin endpoint after updating the YAML file.

## Rotation Procedure

1. Add new key entry with `hashed_key`, `allow_agents`, `rate_limit`, and `expires_at`.
2. `POST /security/refresh` to load it.
3. Update clients to use the new key.
4. Remove or expire the old key, then refresh again.
5. Run `python scripts/nightly_audit.py` (or wait for nightly CI) to ensure no pending expirations.

## Nightly Audit

`scripts/nightly_audit.py` scans `src/config/security.yaml` and prints findings (missing expirations, keys expiring soon, dependency reminders). CI runs it nightly; failures should page operators.

## Local Tool Allowlist

Local tools are restricted by `default.local_tools_allowlist`. Patterns follow the `module:function` format:

- `"tooling.local_tools:*"` – allow all functions within the module.
- `"package.tools:run_report"` – allow a specific callable.

Tools not matching the allowlist are blocked before import.

## Secrets Handling Tips

- Distribute hashed keys via config management (Vault, SSM). Avoid committing plaintext keys.
- Use environment-specific security files (e.g., mount `/etc/gateway/security.yaml` and set `GATEWAY_SECURITY_CONFIG`).
- Consider wrapping security config with OS-level ACLs; only the gateway process should read it.
