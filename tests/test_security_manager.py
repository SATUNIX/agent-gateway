"""Tests for the security manager authentication and ACLs."""

from __future__ import annotations

from pathlib import Path
from time import sleep

import pytest

from security.manager import RateLimitExceeded, SecurityManager


def write_security_config(path: Path) -> None:
    path.write_text(
        """
version: 1
default:
  allow_agents:
    - "alpha/*"
  rate_limit:
    per_minute: 5
  local_tools_allowlist:
    - "tooling.local_tools:*"
  dropin_module_allowlist:
    - "agents_pkg.*"
  dropin_module_denylist:
    - "forbidden.*"

api_keys:
  - id: test
    key: super-secret
    allow_agents:
      - "alpha/*"
      - "beta/agent"
    rate_limit:
      per_minute: 2
""",
        encoding="utf-8",
    )


@pytest.fixture()
def security_manager_tmp(tmp_path: Path) -> SecurityManager:
    config = tmp_path / "security.yaml"
    write_security_config(config)
    return SecurityManager(config_path=config, fallback_key=None)


def test_authenticate_and_acl(security_manager_tmp: SecurityManager) -> None:
    ctx = security_manager_tmp.authenticate("super-secret")
    assert ctx.key_id == "test"
    assert ctx.is_agent_allowed("alpha/demo")
    assert ctx.is_agent_allowed("beta/agent")
    assert not ctx.is_agent_allowed("gamma/x")


def test_rate_limit_exceeded(security_manager_tmp: SecurityManager) -> None:
    security_manager_tmp.authenticate("super-secret")
    security_manager_tmp.authenticate("super-secret")
    with pytest.raises(RateLimitExceeded):
        security_manager_tmp.authenticate("super-secret")


def test_tool_allowlist(security_manager_tmp: SecurityManager) -> None:
    # Allowed tool should pass
    security_manager_tmp.assert_tool_allowed("tooling.local_tools:summarize_text")
    # Disallowed tool raises
    with pytest.raises(PermissionError):
        security_manager_tmp.assert_tool_allowed("os.system:run")


def test_agent_module_allowlist(security_manager_tmp: SecurityManager) -> None:
    # Allowed module pattern
    security_manager_tmp.assert_agent_module_allowed("agents_pkg.research.agent")
    # Denied module pattern
    with pytest.raises(PermissionError):
        security_manager_tmp.assert_agent_module_allowed("forbidden.module:agent")
