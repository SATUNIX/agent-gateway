"""Security manager handling API keys, ACLs, and rate limiting."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from fnmatch import fnmatch

import yaml

from config import get_settings
from security.models import APIKeyEntry, SecurityConfig


logger = logging.getLogger("agent_gateway.security")


@dataclass
class AuthContext:
    key_id: Optional[str]
    allow_agents: List[str]
    rate_limit_per_minute: int

    def is_agent_allowed(self, qualified_name: str) -> bool:
        for pattern in self.allow_agents:
            if self._match_pattern(pattern, qualified_name):
                return True
        return False

    @staticmethod
    def _match_pattern(pattern: str, name: str) -> bool:
        if pattern == "*":
            return True
        if pattern.endswith("/*"):
            namespace = pattern[:-2]
            return name.startswith(f"{namespace}/")
        return pattern == name


class RateLimitExceeded(PermissionError):
    """Raised when a client exceeds the configured rate limit."""


class SecurityManager:
    def __init__(self, config_path: Path, fallback_key: Optional[str]) -> None:
        self._config_path = config_path
        self._fallback_key = fallback_key
        self._lock = threading.RLock()
        self._rate_buckets: Dict[str, Deque[float]] = {}
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
                return AuthContext(key_id=None, allow_agents=["*"], rate_limit_per_minute=10_000)
            if provided_key == self._fallback_key:
                return AuthContext(key_id="fallback", allow_agents=["*"], rate_limit_per_minute=10_000)
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
        return AuthContext(key_id=entry.id, allow_agents=allow_agents, rate_limit_per_minute=per_minute)

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
            raise PermissionError(f"Drop-in module '{module_path}' is blocked by security policy")
        if self._dropin_module_allowlist and not self._matches_any(
            self._dropin_module_allowlist, module_path
        ):
            raise PermissionError(f"Drop-in module '{module_path}' is not in the allowlist")

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

    @staticmethod
    def _matches_any(patterns: List[str], value: str) -> bool:
        for pattern in patterns:
            if pattern == "*":
                return True
            if fnmatch(value, pattern):
                return True
        return False


security_manager = SecurityManager.from_settings()
