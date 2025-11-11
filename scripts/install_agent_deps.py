#!/usr/bin/env python3
"""Install requirements for drop-in agents.

Usage:
    python scripts/install_agent_deps.py [--root src/agents] [--agent Spark]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def find_requirement_files(root: Path, agent_filter: str | None) -> list[Path]:
    files: list[Path] = []
    if not root.exists():
        return files
    for req in root.rglob("requirements.txt"):
        if agent_filter and agent_filter.lower() not in str(req.parent).lower():
            continue
        files.append(req)
    return files


def install_requirements(req_files: list[Path]) -> int:
    failures = 0
    for req_file in req_files:
        print(f"[install] {req_file}")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
        except subprocess.CalledProcessError:
            failures += 1
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Install dependencies for drop-in agents.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("src/agents"),
        help="Root directory containing agent folders (default: %(default)s)",
    )
    parser.add_argument(
        "--agent",
        type=str,
        default=None,
        help="Filter requirement files by agent name/path substring.",
    )
    args = parser.parse_args()
    req_files = find_requirement_files(args.root.resolve(), args.agent)
    if not req_files:
        print("No requirements.txt files found for agents.")
        raise SystemExit(0)
    failures = install_requirements(req_files)
    if failures:
        raise SystemExit(failures)


if __name__ == "__main__":
    main()
