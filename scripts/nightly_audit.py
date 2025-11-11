"""Nightly audit script for dependency and API key checks."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import yaml

SECURITY_CONFIG = Path("config/security.yaml")


def load_security_config() -> dict:
    if not SECURITY_CONFIG.exists():
        return {}
    return yaml.safe_load(SECURITY_CONFIG.read_text(encoding="utf-8")) or {}


def audit_api_keys(config: dict) -> dict:
    findings: list[str] = []
    total = 0
    hashed = 0
    for entry in config.get("api_keys", []):
        total += 1
        if entry.get("hashed_key"):
            hashed += 1
        else:
            findings.append(f"Key '{entry.get('id')}' is missing 'hashed_key' (plaintext).")
        expires_at = entry.get("expires_at")
        if not expires_at:
            findings.append(f"Key '{entry.get('id')}' has no expiry set.")
            continue
        expires = dt.datetime.fromisoformat(expires_at)
        remaining = expires - dt.datetime.utcnow()
        if remaining.total_seconds() < 0:
            findings.append(f"Key '{entry.get('id')}' expired {abs(remaining.days)} days ago.")
        elif remaining.days < 7:
            findings.append(f"Key '{entry.get('id')}' expires in {remaining.days} days.")
    return {"findings": findings, "total_keys": total, "hashed_keys": hashed}


def main() -> None:
    config = load_security_config()
    security_report = audit_api_keys(config)
    report = {
        "timestamp": dt.datetime.utcnow().isoformat(),
        "security_findings": security_report["findings"],
        "total_api_keys": security_report["total_keys"],
        "hashed_api_keys": security_report["hashed_keys"],
        "dependency_audit": "Run `pip list --outdated` to review dependency updates.",
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
