"""Agent registry implementation with hot-reload support."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set

import yaml

from config import get_settings
from registry.discovery import (
    AgentDiscoverer,
    DiscoveredAgentExport,
    DiscoveryDiagnostic,
    DiagnosticKind,
    DiagnosticSeverity,
)
from registry.models import AgentSpec, AgentsFile
from security import security_manager
from observability.errors import error_recorder
from api.metrics import metrics


def _slugify(value: str) -> str:
    normalized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value).strip("-")
    return normalized.lower() or "agent"


class AgentRegistry:
    """Loads and tracks agent definitions from a YAML file."""

    def __init__(
        self,
        config_path: Path,
        auto_reload: bool = False,
        discovery_root: Path | None = None,
        discovery_package: str | None = None,
    ) -> None:
        settings = get_settings()
        self._config_path = config_path
        self._auto_reload = auto_reload
        self._settings = settings
        self._logger = logging.getLogger("agent_gateway.registry")
        self._agents: Dict[str, AgentSpec] = {}
        self._yaml_agents: Dict[str, AgentSpec] = {}
        self._dropin_agents: Dict[str, AgentSpec] = {}
        self._dropin_source_index: Dict[str, Set[str]] = {}
        self._defaults: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._last_mtime: float = 0.0
        self._discovery_diagnostics: list[DiscoveryDiagnostic] = []
        self._discoverers: Dict[Path, AgentDiscoverer] = {}
        self._primary_root = Path(discovery_root or settings.agent_discovery_path).resolve()
        self._primary_package = discovery_package or settings.agent_discovery_package
        self._discoverers[self._primary_root] = AgentDiscoverer(
            self._primary_root,
            self._primary_package,
            export_names=settings.agent_export_names,
        )
        self._primary_discoverer = self._discoverers[self._primary_root]

        for extra_path in settings.agent_discovery_extra_paths:
            root = Path(extra_path).resolve()
            if root == self._primary_root:
                continue
            self._discoverers[root] = AgentDiscoverer(
                root,
                settings.agent_discovery_extra_package,
                export_names=settings.agent_export_names,
            )
        self._discovery_diagnostics: list[DiscoveryDiagnostic] = []
        self._watch_enabled = settings.agent_watch_enabled
        self._watch_thread: threading.Thread | None = None
        self._watch_stop: threading.Event | None = None
        self._load(force=True)
        self._refresh_discovery(force=True)
        if self._watch_enabled:
            self._start_watch_thread()

    @classmethod
    def from_settings(cls) -> "AgentRegistry":
        settings = get_settings()
        config_path = Path(settings.agent_config_path).resolve()
        auto_reload = settings.agent_auto_reload
        discovery_root = Path(settings.agent_discovery_path).resolve()
        return cls(
            config_path=config_path,
            auto_reload=auto_reload,
            discovery_root=discovery_root,
            discovery_package=settings.agent_discovery_package,
        )

    def list_agents(self) -> Iterable[AgentSpec]:
        self._auto_reload_if_needed()
        self._refresh_discovery()
        return sorted(self._agents.values(), key=lambda agent: agent.qualified_name)

    def get_agent(self, name: str) -> Optional[AgentSpec]:
        self._auto_reload_if_needed()
        self._refresh_discovery()
        if "/" in name:
            return self._agents.get(name)
        matches = [agent for agent in self._agents.values() if agent.name == name]
        if len(matches) == 1:
            return matches[0]
        return None

    def refresh(self) -> None:
        """Force a reload of the configuration file."""

        with self._lock:
            self._load(force=True)
            self._refresh_discovery(force=True)

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
            raise FileNotFoundError(f"Agent configuration file not found: {path}")
        mtime = path.stat().st_mtime
        if not force and mtime <= self._last_mtime:
            return
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}
        parsed = AgentsFile(**data)
        agents = {agent.qualified_name: agent for agent in parsed.agents}
        self._yaml_agents = agents
        self._defaults = parsed.defaults or {}
        self._last_mtime = mtime
        self._rebuild_catalog()

    def _refresh_discovery(self, force: bool = False) -> None:
        exports: list[DiscoveredAgentExport] = []
        self._discovery_diagnostics = []
        for root, discoverer in self._discoverers.items():
            if not root.exists():
                continue
            exports.extend(discoverer.discover())
            self._discovery_diagnostics.extend(discoverer.diagnostics())
        specs: Dict[str, AgentSpec] = {}
        for export in exports:
            spec = self._spec_from_export(export)
            if spec is None:
                continue
            specs[spec.qualified_name] = spec
        self._dropin_agents = specs
        self._reindex_dropin_sources()
        self._rebuild_catalog()

    def _rebuild_catalog(self) -> None:
        catalog = dict(self._yaml_agents)
        for key, spec in self._dropin_agents.items():
            if key in catalog:
                continue
            catalog[key] = spec
        self._agents = catalog

    def _reindex_dropin_sources(self) -> None:
        index: Dict[str, Set[str]] = {}
        for spec in self._dropin_agents.values():
            source_file = spec.metadata.get("source_file")
            if not source_file:
                continue
            index.setdefault(source_file, set()).add(spec.qualified_name)
        self._dropin_source_index = index

    def _compute_discovery_mtime(self) -> float:
        try:
            newest = self._primary_root.stat().st_mtime
        except FileNotFoundError:
            return 0.0
        for path in self._primary_root.rglob("*"):
            try:
                newest = max(newest, path.stat().st_mtime)
            except FileNotFoundError:
                continue
        return newest

    def _find_discovery_root(self, file_path: Path) -> Path:
        for root in self._discoverers.keys():
            if file_path.is_relative_to(root):
                return root
        return self._primary_root

    def _refresh_discovery_paths(self, paths: Set[Path]) -> None:
        if not paths:
            return
        existing = {path for path in paths if path.exists()}
        changed = False
        with self._lock:
            for root, discoverer in self._discoverers.items():
                scoped = {path for path in existing if path.is_relative_to(root)}
                if not scoped:
                    continue
                for path in scoped:
                    exports = discoverer.refresh_file(path)
                    changed |= self._remove_specs_for_path(path)
                    added: Set[str] = set()
                    for export in exports:
                        spec = self._spec_from_export(export)
                        if spec is None:
                            continue
                        self._dropin_agents[spec.qualified_name] = spec
                        added.add(spec.qualified_name)
                    if added:
                        self._dropin_source_index[str(path)] = added
                        changed = True
            for path in paths:
                if not path.exists():
                    changed |= self._remove_specs_for_path(path)
            if changed:
                self._reindex_dropin_sources()
                self._rebuild_catalog()

    def _remove_specs_for_path(self, path: Path) -> bool:
        key = str(path)
        names = self._dropin_source_index.pop(key, set())
        removed = False
        for name in names:
            if name in self._dropin_agents:
                removed = True
                self._dropin_agents.pop(name, None)
        return removed

    def _spec_from_export(self, export: DiscoveredAgentExport) -> AgentSpec | None:
        if export.attribute is None and export.kind == "module":
            return None
        default_namespace = self._defaults.get("namespace") or self._settings.agent_default_namespace
        default_upstream = self._defaults.get("upstream") or self._settings.agent_default_upstream
        default_model = self._defaults.get("model") or self._settings.agent_default_model

        gateway_meta = export.module_metadata or {}
        namespace_override = gateway_meta.get("namespace") or default_namespace or "default"
        upstream_override = gateway_meta.get("upstream") or default_upstream
        model_override = gateway_meta.get("model") or default_model

        if not upstream_override or not model_override:
            self._record_diagnostic(
                export,
                message="No upstream/model defaults configured for drop-in agent.",
                kind="validation",
            )
            return None

        namespace, name = self._derive_identity(export, namespace_override)
        display_name = name.replace("-", " ").title()
        if gateway_meta.get("display_name"):
            display_name = gateway_meta["display_name"]
        module_path = export.import_path
        if ":" not in module_path and export.attribute:
            module_path = f"{export.module_path}:{export.attribute}"
        try:
            created = int(export.file_path.stat().st_mtime)
        except FileNotFoundError:
            created = int(time.time())

        metadata = {
            "dropin": True,
            "export_kind": export.kind,
            "import_path": export.import_path,
            "source_file": str(export.file_path),
            "discovered_at": created,
            "discovery_hash": export.file_hash,
            "discovery_mtime": export.modified_time,
            "requirements_file": str(export.requirements_file) if export.requirements_file else None,
            "discovery_status": "available",
            "gateway_overrides": gateway_meta,
        }
        description = export.docstring or ""
        if gateway_meta.get("description"):
            description = gateway_meta["description"]

        if not self._is_module_allowed(export, module_path):
            return None
        return AgentSpec(
            name=name,
            namespace=namespace,
            display_name=display_name,
            description=description,
            kind="sdk",
            upstream=upstream_override,
            model=model_override,
            instructions=None,
            module=module_path,
            tools=[],
            metadata=metadata,
        )

    def _derive_identity(
        self, export: DiscoveredAgentExport, fallback_namespace: str
    ) -> tuple[str, str]:
        root = self._find_discovery_root(export.file_path)
        try:
            relative = export.file_path.parent.relative_to(root)
            parts = list(relative.parts)
        except ValueError:
            parts = []
        if not parts:
            namespace = fallback_namespace
            base_name = export.attribute or export.module.split(".")[-1]
        elif len(parts) == 1:
            namespace = fallback_namespace
            base_name = parts[0]
        else:
            namespace = parts[0]
            base_name = parts[-1]
        if export.attribute and export.attribute.lower() not in {"agent", base_name}:
            base_name = f"{base_name}-{export.attribute}"
        return namespace, _slugify(base_name)

    def _is_module_allowed(self, export: DiscoveredAgentExport, module_path: str) -> bool:
        try:
            security_manager.assert_agent_module_allowed(module_path)
            return True
        except PermissionError as exc:
            self._logger.warning(
                {
                    "event": "agent.dropin.blocked",
                    "module": module_path,
                    "reason": str(exc),
                }
            )
            self._record_diagnostic(
                export,
                message=str(exc),
                kind="security",
            )
            return False

    def _record_diagnostic(
        self,
        export: DiscoveredAgentExport,
        *,
        message: str,
        kind: DiagnosticKind,
        severity: DiagnosticSeverity = "error",
    ) -> None:
        metrics.record_dropin_failure(kind=f"discovery_{kind}")
        error_recorder.record(
            event="agent_discovery",
            message=message,
            details={
                "module": export.import_path,
                "file": str(export.file_path),
                "kind": kind,
                "severity": severity,
            },
        )
        self._discovery_diagnostics.append(
            DiscoveryDiagnostic(
                file_path=export.file_path,
                module=export.import_path,
                message=message,
                kind=kind,  # type: ignore[arg-type]
                severity=severity,  # type: ignore[arg-type]
            )
        )

    def _start_watch_thread(self) -> None:
        try:
            from watchfiles import watch
        except Exception:  # noqa: BLE001
            self._logger.warning(
                {
                    "event": "agent.watch.disabled",
                    "reason": "watchfiles not installed",
                }
            )
            return
        if not self._primary_root.exists():
            self._logger.warning(
                {
                    "event": "agent.watch.disabled",
                    "reason": f"discovery root missing ({self._primary_root})",
                }
            )
            return
        self._watch_stop = threading.Event()
        self._watch_thread = threading.Thread(
            target=self._watch_loop,
            args=(watch,),
            name="agent-watch",
            daemon=True,
        )
        self._watch_thread.start()
        self._logger.info(
            {
                "event": "agent.watch.started",
                "path": str(self._primary_root),
            }
        )

    def _watch_loop(self, watch_fn) -> None:
        assert self._watch_stop is not None
        try:
            for changes in watch_fn(
                self._primary_root,
                stop_event=self._watch_stop,
                recursive=True,
            ):
                paths = {
                    Path(path)
                    for _, path in changes
                    if path.endswith(".py") or path.endswith("requirements.txt")
                }
                if not paths:
                    continue
                self._refresh_discovery_paths(paths)
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                {
                    "event": "agent.watch.stopped",
                    "reason": str(exc),
                }
            )

    def list_discovery_diagnostics(self) -> Iterable[DiscoveryDiagnostic]:
        self._refresh_discovery()
        return list(self._discovery_diagnostics)


agent_registry = AgentRegistry.from_settings()
