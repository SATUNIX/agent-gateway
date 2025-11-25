"""Filesystem-based discovery for drop-in OpenAI Agents SDK modules."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata as import_metadata
import importlib.util
import inspect
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Iterator, Literal, Sequence

from packaging.requirements import Requirement


DiscoveredExportKind = Literal["agent", "factory", "runner", "module"]
DiagnosticKind = Literal["import", "dependency", "validation", "security"]
DiagnosticSeverity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class DiscoveredAgentExport:
    """Represents a single exported agent/factory discovered on disk."""

    package: str
    module: str
    attribute: str | None
    kind: DiscoveredExportKind
    file_path: Path
    file_hash: str
    modified_time: float
    requirements_file: Path | None = None
    docstring: str | None = None
    module_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def module_path(self) -> str:
        return f"{self.package}.{self.module}" if self.package else self.module

    @property
    def import_path(self) -> str:
        if self.attribute:
            return f"{self.module_path}:{self.attribute}"
        return self.module_path


@dataclass(frozen=True)
class DiscoveryDiagnostic:
    file_path: Path
    module: str
    message: str
    kind: DiagnosticKind
    severity: DiagnosticSeverity
    occurred_at: float = field(default_factory=lambda: time.time())


class AgentDiscoverer:
    """Walks the src/agents/ directory and records exported SDK objects."""

    def __init__(self, root: Path, package_name: str, export_names: Sequence[str]) -> None:
        self._root = root
        self._package = package_name
        self._export_names = [name.strip() for name in export_names if name.strip()]
        self._cache: dict[Path, tuple[float, str, list[DiscoveredAgentExport]]] = {}
        self._diagnostics: list[DiscoveryDiagnostic] = []

    def discover(self) -> list[DiscoveredAgentExport]:
        exports: list[DiscoveredAgentExport] = []
        self._diagnostics = []
        if not self._root.exists():
            return exports
        seen_paths: set[Path] = set()
        for file_path in self._iter_agent_files():
            seen_paths.add(file_path)
            exports.extend(self._process_file(file_path))
        # drop cache entries for deleted files
        for cached_path in list(self._cache):
            if cached_path not in seen_paths:
                self._cache.pop(cached_path, None)
        return exports

    def diagnostics(self) -> list[DiscoveryDiagnostic]:
        return list(self._diagnostics)

    def _iter_agent_files(self) -> Iterator[Path]:
        for path in self._root.rglob("agent.py"):
            if "__pycache__" in path.parts:
                continue
            yield path

    def refresh_file(self, file_path: Path) -> list[DiscoveredAgentExport]:
        return self._process_file(file_path)

    def drop_file(self, file_path: Path) -> None:
        self._cache.pop(file_path, None)

    def _process_file(self, file_path: Path) -> list[DiscoveredAgentExport]:
        try:
            mtime = file_path.stat().st_mtime
        except FileNotFoundError:
            return []
        relative_module = self._relative_module(file_path)
        requirements_file = self._requirements_file(file_path)
        missing_deps = self._missing_dependencies(requirements_file)
        if missing_deps:
            self._record_diagnostic(
                file_path,
                module=relative_module or file_path.stem,
                message=f"Missing dependencies: {', '.join(sorted(missing_deps))}",
                kind="dependency",
                severity="error",
            )
            return []

        cached = self._cache.get(file_path)
        file_hash = cached[1] if cached and cached[0] == mtime else self._hash_file(file_path)
        if cached and cached[0] == mtime and cached[1] == file_hash:
            return cached[2]

        try:
            module = self._load_module(relative_module, file_path)
        except Exception as exc:  # pragma: no cover - import errors depend on user code
            self._record_diagnostic(
                file_path,
                module=relative_module,
                message=f"Import failed: {exc}",
                kind="import",
                severity="error",
            )
            return []

        exports = list(
            self._inspect_module(
                relative_module,
                file_path,
                module,
                file_hash=file_hash,
                modified_time=mtime,
                requirements_file=requirements_file,
            )
        )
        self._cache[file_path] = (mtime, file_hash, exports)
        return exports

    def _relative_module(self, file_path: Path) -> str:
        relative = file_path.relative_to(self._root)
        parts = [part.replace(".py", "") for part in relative.parts]
        clean_parts = [part for part in parts if part]
        return ".".join(clean_parts)

    def _hash_file(self, file_path: Path) -> str:
        data = file_path.read_bytes()
        return hashlib.sha256(data).hexdigest()

    def _requirements_file(self, file_path: Path) -> Path | None:
        candidate = file_path.parent / "requirements.txt"
        return candidate if candidate.exists() else None

    def _missing_dependencies(self, requirements_file: Path | None) -> list[str]:
        if not requirements_file:
            return []
        missing: list[str] = []
        for line in requirements_file.read_text(encoding="utf-8").splitlines():
            stripped = line.split("#", 1)[0].strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                requirement = Requirement(stripped)
            except Exception:
                requirement = Requirement(stripped.split()[0])
            try:
                import_metadata.version(requirement.name)
            except import_metadata.PackageNotFoundError:
                missing.append(requirement.name)
        return missing

    def _load_module(self, relative_module: str, file_path: Path) -> ModuleType:
        module_name = f"{self._package}.{relative_module}" if relative_module else self._package
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError:
            spec_name = f"_gateway_dropin_{relative_module.replace('.', '_')}"
            spec = importlib.util.spec_from_file_location(spec_name, file_path)
            if spec is None or spec.loader is None:
                raise
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec_name] = module
            spec.loader.exec_module(module)
            return module

    def _inspect_module(
        self,
        relative_module: str,
        file_path: Path,
        module: ModuleType,
        *,
        file_hash: str,
        modified_time: float,
        requirements_file: Path | None,
    ) -> Iterable[DiscoveredAgentExport]:
        module_exports: list[DiscoveredAgentExport] = []
        gateway_meta = (
            getattr(module, "__gateway__", {})
            if isinstance(getattr(module, "__gateway__", {}), dict)
            else {}
        )
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name)
            preferred = attr_name in self._export_names and _looks_like_agent(attr)
            kind = "agent" if preferred else self._classify_export(attr)
            if kind is None:
                continue
            docstring = inspect.getdoc(attr)
            module_exports.append(
                DiscoveredAgentExport(
                    package=self._package,
                    module=relative_module,
                    attribute=attr_name,
                    kind=kind,
                    file_path=file_path,
                    file_hash=file_hash,
                    modified_time=modified_time,
                    requirements_file=requirements_file,
                    docstring=docstring,
                    module_metadata=gateway_meta,
                )
            )
        if module_exports:
            return module_exports
        return [
            DiscoveredAgentExport(
                package=self._package,
                module=relative_module,
                attribute=None,
                kind="module",
                file_path=file_path,
                file_hash=file_hash,
                modified_time=modified_time,
                requirements_file=requirements_file,
                docstring=inspect.getdoc(module),
                module_metadata=gateway_meta,
            )
        ]

    @staticmethod
    def _classify_export(obj: object) -> DiscoveredExportKind | None:
        if _looks_like_agent(obj):
            return "agent"
        if _looks_like_runner(obj):
            return "runner"
        if callable(obj) and _looks_like_agent_factory(obj):
            return "factory"
        return None

    def _record_diagnostic(
        self,
        file_path: Path,
        module: str,
        message: str,
        kind: DiagnosticKind,
        severity: DiagnosticSeverity,
    ) -> None:
        self._diagnostics.append(
            DiscoveryDiagnostic(
                file_path=file_path,
                module=module,
                message=message,
                kind=kind,
                severity=severity,
            )
        )


def _looks_like_agent(obj: object) -> bool:
    if obj is None:
        return False
    # Ignore class definitions to avoid duplicating exports
    if isinstance(obj, type):
        return False
    if callable(getattr(obj, "run_sync", None)) or callable(getattr(obj, "run", None)):
        return True
    cls = getattr(obj, "__class__", None)
    return bool(cls and cls.__name__ == "Agent")


def _looks_like_runner(obj: object) -> bool:
    if obj is None:
        return False
    return callable(getattr(obj, "run", None)) or callable(getattr(obj, "run_sync", None))


def _looks_like_agent_factory(obj: object) -> bool:
    if not callable(obj):
        return False
    name = getattr(obj, "__name__", "").lower()
    qualname = getattr(obj, "__qualname__", "").lower()
    combined = f"{name} {qualname}"
    return "agent" in combined or "build" in combined
