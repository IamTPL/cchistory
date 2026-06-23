"""Locate Claude Code project history directories across platforms."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Mapping


def is_wsl() -> bool:
    """Return True when running inside Windows Subsystem for Linux."""
    return "microsoft" in platform.uname().release.lower()


def _safe_glob(path: Path, pattern: str) -> list[Path]:
    try:
        return list(path.glob(pattern))
    except OSError:
        return []


def discover_sources(
    env: Mapping[str, str] | None = None,
    home: str | Path | None = None,
    platform_system: str | None = None,
    wsl: bool | None = None,
) -> list[Path]:
    """Return existing Claude Code ``projects`` directories in priority order."""
    env_map = os.environ if env is None else env
    home_path = Path.home() if home is None else Path(home)
    system = platform.system() if platform_system is None else platform_system
    in_wsl = is_wsl() if wsl is None else wsl

    candidates: list[Path] = []
    config_dir = env_map.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        candidates.append(Path(config_dir) / "projects")
    candidates.append(home_path / ".claude" / "projects")

    if in_wsl:
        for base in _safe_glob(Path("/mnt/c/Users"), "*"):
            candidates.append(base / ".claude" / "projects")
    elif system == "Windows":
        for root in (Path(r"\\wsl$"), Path(r"\\wsl.localhost")):
            for distro in _safe_glob(root, "*"):
                for base in _safe_glob(distro / "home", "*"):
                    candidates.append(base / ".claude" / "projects")

    seen: set[str] = set()
    found: list[Path] = []
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        try:
            if candidate.is_dir():
                found.append(candidate)
        except OSError:
            continue
    return found

