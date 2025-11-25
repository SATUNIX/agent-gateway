"""Security manager handling API keys, ACLs, and rate limiting."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from fnmatch import fnmatch

import yaml

from config import get_settings
from security.models import APIKeyEntry, SecurityConfig
from observability.errors import error_recorder
from api.metrics import metrics


logger = logging.getLogger("agent_gateway.security")


@dataclass
@dataclass
class AgentOverride:
    pattern: str
    expires_at: float
    reason: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern,
            "expires_at": int(self.expires_at),
            "reason": self.reason,
        }


@dataclass
class AuthContext:
    key_id: Optional[str]
    allow_agents: List[str]
    rate_limit_per_minute: int
    namespace_defaults: Dict[str, List[str]] = field(default_factory=dict)
    overrides: List[AgentOverride] = field(default_factory=list)

    def evaluate_agent(self, qualified_name: str, *, log_decision: bool = True) -> Dict[str, Any]:
        namespace = qualified_name.split("/", 1)[0]

        def _decision(
            source: str, allowed: bool, pattern: Optional[str], extra: Optional[Dict[str, Any]] = None
        ) -> Dict[str, Any]:
            if log_decision:
                self._log_decision(qualified_name, namespace, source, allowed, pattern, extra=extra)
            return {
                "allowed": allowed,
                "source": source,
                "pattern": pattern,
            }

        for override in self.overrides:
            if self._match_pattern(override.pattern, qualified_name):
                return _decision(
                    "override",
                    True,
                    override.pattern,
                    extra={"reason": override.reason, "expires_at": int(override.expires_at)},
                )

        for pattern in self.namespace_defaults.get(namespace, []):
            if self._match_pattern(pattern, qualified_name):
                return _decision("namespace_default", True, pattern)

        for pattern in self.allow_agents:
            if self._match_pattern(pattern, qualified_name):
                return _decision("api_key", True, pattern)

        return _decision("deny", False, None)

    def is_agent_allowed(self, qualified_name: str) -> bool:
        return self.evaluate_agent(qualified_name)["allowed"]

    @staticmethod
    def _match_pattern(pattern: str, name: str) -> bool:
        return fnmatch(name, pattern) or name == pattern

    def _log_decision(
        self,
        qualified_name: str,
        namespace: str,
        source: str,
        allowed: bool,
        pattern: Optional[str],
        *,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        logger.info(
            {
                "event": "agent.security.decision",
                "key_id": self.key_id,
                "agent": qualified_name,
                "namespace": namespace,
                "decision": "allow" if allowed else "deny",
                "source": source,
                "pattern": pattern,
                **(extra or {}),
            }
        )


class RateLimitExceeded(PermissionError):
    """Raised when a client exceeds the configured rate limit."""


class SecurityManager:
    def __init__(self, config_path: Path, fallback_key: Optional[str]) -> None:
        self._config_path = config_path
        self._fallback_key = fallback_key
        self._lock = threading.RLock()
        self._rate_buckets: Dict[str, Deque[float]] = {}
        self._agent_overrides: Dict[str, AgentOverride] = {}
        self._namespace_agent_defaults: Dict[str, List[str]] = {}
        self._config = self._load_config()
        self._refresh_module_lists()
        self._keys = self._build_key_index()

    @classmethod
    def from_settings(cls) -> SecurityManager:
        settings = get_settings()
        return cls(Path(settings.security_config_path).resolve(), settings.api_key)

    def authenticate(self, provided_key: Optional[str]) -> AuthContext:
        if not self._keys:
            # No keys configured means open mode (legacy behavior)
            if provided_key is None and self._fallback_key is None:
                return AuthContext(
                    key_id=None,
                    allow_agents=["*"],
                    rate_limit_per_minute=10_000,
                    namespace_defaults=self._namespace_agent_defaults,
                    overrides=self._active_agent_overrides(),
                )
            if provided_key == self._fallback_key:
                return AuthContext(
                    key_id="fallback",
                    allow_agents=["*"],
                    rate_limit_per_minute=10_000,
                    namespace_defaults=self._namespace_agent_defaults,
                    overrides=self._active_agent_overrides(),
                )
            raise PermissionError("Invalid or missing API key")

        if not provided_key:
            raise PermissionError("API key required")

        hashed = self._hash_key(provided_key)
        entry = self._keys.get(hashed)
        if not entry:
            raise PermissionError("Invalid API key")

        self._enforce_rate_limit(entry.id, entry.rate_limit.per_minute)
        if entry.expires_at and entry.expires_at.timestamp() < time.time():
            raise PermissionError("API key expired")

        self._warn_on_pending_expiry(entry)

        allow_agents = entry.allow_agents or self._config.default.allow_agents
        per_minute = entry.rate_limit.per_minute or self._config.default.rate_limit.per_minute
        return AuthContext(
            key_id=entry.id,
            allow_agents=allow_agents,
            rate_limit_per_minute=per_minute,
            namespace_defaults=self._namespace_agent_defaults,
            overrides=self._active_agent_overrides(),
        )

    def assert_tool_allowed(self, module_path: str) -> None:
        allowlist = self._config.default.local_tools_allowlist
        for pattern in allowlist:
            if self._match_tool_pattern(pattern, module_path):
                return
        raise PermissionError(f"Local tool '{module_path}' is not permitted by security policy")

    def reload(self) -> None:
        with self._lock:
            self._config = self._load_config()
            self._refresh_module_lists()
            self._keys = self._build_key_index()
            self._rate_buckets.clear()

    def summary(self) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for entry in self._config.api_keys:
            result.append(
                {
                    "key_id": entry.id,
                    "allow_agents": entry.allow_agents or self._config.default.allow_agents,
                    "rate_limit_per_minute": entry.rate_limit.per_minute
                    if entry.rate_limit
                    else self._config.default.rate_limit.per_minute,
                    "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
                }
            )
        return result

    def _enforce_rate_limit(self, key_id: str, per_minute: int) -> None:
        now = time.time()
        window_start = now - 60
        with self._lock:
            bucket = self._rate_buckets.setdefault(key_id, deque())
            while bucket and bucket[0] < window_start:
                bucket.popleft()
            if len(bucket) >= per_minute:
                raise RateLimitExceeded("Rate limit exceeded")
            bucket.append(now)

    def _load_config(self) -> SecurityConfig:
        if not self._config_path.exists():
            logger.warning("Security config not found at %s; falling back to env key", self._config_path)
            return SecurityConfig()
        data = yaml.safe_load(self._config_path.read_text(encoding="utf-8")) or {}
        return SecurityConfig(**data)

    def assert_agent_module_allowed(self, module_path: str) -> None:
        if self._matches_any(self._dropin_module_denylist, module_path):
            message = f"Drop-in module '{module_path}' is blocked by security policy"
            self._record_security_event("module_blocked", message, {"module": module_path})
            raise PermissionError(message)
        if self._dropin_module_allowlist and not self._matches_any(
            self._dropin_module_allowlist, module_path
        ):
            message = f"Drop-in module '{module_path}' is not in the allowlist"
            self._record_security_event("module_not_allowed", message, {"module": module_path})
            raise PermissionError(message)

    def preview_agent(self, qualified_name: str) -> Dict[str, Any]:
        overrides = self._active_agent_overrides()
        context = AuthContext(
            key_id="preview",
            allow_agents=self._config.default.allow_agents,
            rate_limit_per_minute=self._config.default.rate_limit.per_minute,
            namespace_defaults=self._namespace_agent_defaults,
            overrides=overrides,
        )
        decision = context.evaluate_agent(qualified_name, log_decision=False)
        override_info = None
        if decision["source"] == "override" and decision["pattern"]:
            override = next((o for o in overrides if o.pattern == decision["pattern"]), None)
            if override:
                override_info = override.as_dict()
        return {
            "agent": qualified_name,
            "allowed": decision["allowed"],
            "source": decision["source"],
            "pattern": decision["pattern"],
            "override": override_info,
        }

    def add_agent_override(self, pattern: str, ttl_seconds: int, reason: Optional[str] = None) -> Dict[str, Any]:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        expires_at = time.time() + ttl_seconds
        override = AgentOverride(pattern=pattern, expires_at=expires_at, reason=reason)
        with self._lock:
            self._purge_overrides()
            self._agent_overrides[pattern] = override
        logger.info(
            {
                "event": "agent.security.override.created",
                "pattern": pattern,
                "expires_at": int(expires_at),
                "reason": reason,
            }
        )
        return override.as_dict()

    def _build_key_index(self) -> Dict[str, APIKeyEntry]:
        index: Dict[str, APIKeyEntry] = {}
        for entry in self._config.api_keys:
            hashed = entry.hashed_key or (self._hash_key(entry.key) if entry.key else None)
            if not hashed:
                logger.warning("Skipping API key entry %s: missing key/hashed_key", entry.id)
                continue
            entry.hashed_key = hashed
            index[hashed] = entry
        return index

    def _warn_on_pending_expiry(self, entry: APIKeyEntry) -> None:
        if not entry.expires_at:
            return
        seconds_left = entry.expires_at.timestamp() - time.time()
        if seconds_left < 0:
            return
        days_left = seconds_left / 86400
        if days_left <= 7:
            logger.warning(
                {
                    "event": "api_key.expiring",
                    "key_id": entry.id,
                    "expires_in_days": round(days_left, 2),
                }
            )

    @staticmethod
    def _hash_key(key: Optional[str]) -> Optional[str]:
        if not key:
            return None
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    @staticmethod
    def _match_tool_pattern(pattern: str, module_path: str) -> bool:
        if pattern == "*":
            return True
        if pattern.endswith(":*"):
            prefix = pattern[:-2]
            return module_path.startswith(prefix)
        return pattern == module_path

    def _refresh_module_lists(self) -> None:
        default = self._config.default
        self._dropin_module_allowlist = default.dropin_module_allowlist or ["*"]
        self._dropin_module_denylist = default.dropin_module_denylist or []
        namespace_defaults: Dict[str, List[str]] = {}
        for namespace, rules in default.namespace_defaults.items():
            patterns = list(rules.allow_agents) if rules.allow_agents else [f"{namespace}/*"]
            namespace_defaults[namespace] = patterns
        self._namespace_agent_defaults = namespace_defaults

    def _purge_overrides(self) -> None:
        now = time.time()
        removed = []
        for pattern, override in list(self._agent_overrides.items()):
            if override.expires_at <= now:
                removed.append(pattern)
                self._agent_overrides.pop(pattern, None)
        if removed:
            logger.info(
                {
                    "event": "agent.security.override.expired",
                    "patterns": removed,
                }
            )

    def _active_agent_overrides(self) -> List[AgentOverride]:
        with self._lock:
            self._purge_overrides()
            return list(self._agent_overrides.values())

    @staticmethod
    def _matches_any(patterns: List[str], value: str) -> bool:
        for pattern in patterns:
            if pattern == "*":
                return True
            if fnmatch(value, pattern):
                return True
        return False

    def _record_security_event(self, kind: str, message: str, details: Dict[str, Any]) -> None:
        metrics.record_dropin_failure(kind=kind)
        error_recorder.record(event=kind, message=message, details=details)


security_manager = SecurityManager.from_settings()
