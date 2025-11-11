"""Upstream registry managing OpenAI-compatible clients."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

import httpx
import yaml
from openai import OpenAI

from config import get_settings
from registry.models import UpstreamSpec, UpstreamsFile


@dataclass
class UpstreamRecord:
    spec: UpstreamSpec
    client: OpenAI
    healthy: bool
    last_checked: float
    last_error: Optional[str] = None


class UpstreamRegistry:
    """Loads upstream definitions and instantiates OpenAI clients."""

    def __init__(self, config_path: Path, auto_reload: bool = False) -> None:
        self._config_path = config_path
        self._auto_reload = auto_reload
        self._entries: Dict[str, UpstreamRecord] = {}
        self._lock = threading.RLock()
        self._last_mtime: float = 0.0
        self._load(force=True)

    @classmethod
    def from_settings(cls) -> "UpstreamRegistry":
        settings = get_settings()
        return cls(
            config_path=Path(settings.upstream_config_path).resolve(),
            auto_reload=settings.upstream_auto_reload,
        )

    def list_upstreams(self) -> Iterable[UpstreamRecord]:
        self._auto_reload_if_needed()
        return sorted(
            self._entries.values(),
            key=lambda record: (record.spec.priority, record.spec.name),
        )

    def get_client(self, name: str) -> OpenAI:
        self._auto_reload_if_needed()
        record = self._entries.get(name)
        if not record:
            raise KeyError(f"Unknown upstream: {name}")
        return record.client

    def get_record(self, name: str) -> Optional[UpstreamRecord]:
        self._auto_reload_if_needed()
        return self._entries.get(name)

    def refresh(self) -> None:
        with self._lock:
            self._load(force=True)

    def _auto_reload_if_needed(self) -> None:
        if not self._auto_reload:
            return
        try:
            current_mtime = self._config_path.stat().st_mtime
        except FileNotFoundError:
            return
        if current_mtime <= self._last_mtime:
            return
        with self._lock:
            self._load(force=True)

    def _load(self, force: bool = False) -> None:
        path = self._config_path
        if not path.exists():
            raise FileNotFoundError(f"Upstream configuration file not found: {path}")
        mtime = path.stat().st_mtime
        if not force and mtime <= self._last_mtime:
            return
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}
        parsed = UpstreamsFile(**data)
        entries: Dict[str, UpstreamRecord] = {}
        for spec in parsed.upstreams:
            client = self._create_client(spec)
            healthy, error = self._check_health(spec)
            entries[spec.name] = UpstreamRecord(
                spec=spec,
                client=client,
                healthy=healthy,
                last_checked=time.time(),
                last_error=error,
            )
        self._entries = entries
        self._last_mtime = mtime

    def _create_client(self, spec: UpstreamSpec) -> OpenAI:
        api_key = self._resolve_secret(spec)
        return OpenAI(base_url=str(spec.base_url), api_key=api_key or "not-provided")

    @staticmethod
    def _resolve_secret(spec: UpstreamSpec) -> Optional[str]:
        if spec.api_key_env:
            return os.getenv(spec.api_key_env)
        value = spec.api_key
        if value and value.startswith("${") and value.endswith("}"):
            env_name = value[2:-1]
            return os.getenv(env_name)
        return value

    def _check_health(self, spec: UpstreamSpec) -> tuple[bool, Optional[str]]:
        url = f"{str(spec.base_url).rstrip('/')}{spec.health_path}"
        try:
            response = httpx.get(url, timeout=spec.health_timeout)
            if response.status_code < 500:
                return True, None
            return False, f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)


upstream_registry = UpstreamRegistry.from_settings()

