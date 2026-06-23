"""Cross-platform browser opening helpers."""

from __future__ import annotations

import subprocess
import webbrowser
from pathlib import Path

from .discovery import is_wsl


def open_viewer(index_path: Path) -> bool:
    """Open a generated index.html in the user's browser."""
    path = str(index_path.resolve())
    try:
        if is_wsl():
            result = subprocess.run(
                ["wslpath", "-w", path],
                capture_output=True,
                check=False,
                text=True,
            )
            win_path = result.stdout.strip() or path
            subprocess.run(["cmd.exe", "/c", "start", "", win_path], check=False)
            return True
        return bool(webbrowser.open("file://" + path))
    except Exception:
        return False


def open_url(url: str) -> bool:
    """Open an HTTP URL, including from WSL into the Windows browser."""
    try:
        if is_wsl():
            subprocess.run(["cmd.exe", "/c", "start", "", url], check=False)
            return True
        return bool(webbrowser.open(url))
    except Exception:
        return False

