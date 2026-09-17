"""Cross-platform browser opening helpers."""

from __future__ import annotations

import subprocess
import webbrowser
from pathlib import Path

from .discovery import is_wsl


def open_viewer(index_path: Path) -> bool:
    """Open a generated index.html in the user's browser."""
    resolved = index_path.resolve()
    path = str(resolved)
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
        # as_uri() is the only correct way to build this: on Windows a plain
        # "file://" + r"C:\..." makes "C:" the URL authority, and on every
        # platform spaces and non-ASCII characters need percent-encoding.
        return bool(webbrowser.open(resolved.as_uri()))
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

