"""Filesystem-based discovery for drop-in OpenAI Agents SDK modules."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Iterable, Iterator, Literal


DiscoveredExportKind = Literal["agent", "factory", "runner", "module"]


@dataclass(frozen=True)
class DiscoveredAgentExport:
    """Represents a single exported agent/factory discovered on disk."""

    package: str
    module: str
    attribute: str | None
    kind: DiscoveredExportKind
    file_path: Path
    docstring: str | None = None

    @property
    def module_path(self) -> str:
        return f"{self.package}.{self.module}" if self.package else self.module

    @property
    def import_path(self) -> str:
        if self.attribute:
            return f"{self.module_path}:{self.attribute}"
        return self.module_path


class AgentDiscoverer:
    """Walks the src/agents/ directory and records exported SDK objects."""

    def __init__(self, root: Path, package_name: str) -> None:
        self._root = root
        self._package = package_name

    def discover(self) -> list[DiscoveredAgentExport]:
        exports: list[DiscoveredAgentExport] = []
        if not self._root.exists():
            return exports
        for file_path in self._iter_agent_files():
            rel_module = self._relative_module(file_path)
            module = self._load_module(rel_module, file_path)
            exports.extend(self._inspect_module(rel_module, file_path, module))
        return exports

    def _iter_agent_files(self) -> Iterator[Path]:
        for path in self._root.rglob("agent.py"):
            if "__pycache__" in path.parts:
                continue
            yield path

    def _relative_module(self, file_path: Path) -> str:
        relative = file_path.relative_to(self._root)
        parts = [part.replace(".py", "") for part in relative.parts]
        clean_parts = [part for part in parts if part]
        return ".".join(clean_parts)

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
    ) -> Iterable[DiscoveredAgentExport]:
        module_exports: list[DiscoveredAgentExport] = []
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name)
            kind = self._classify_export(attr)
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
                    docstring=docstring,
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
                docstring=inspect.getdoc(module),
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


def _looks_like_agent(obj: object) -> bool:
    cls = getattr(obj, "__class__", None)
    if cls is None:
        return False
    if cls.__name__ != "Agent":
        return False
    return hasattr(obj, "instructions")


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
