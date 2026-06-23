"""Local HTTP serving for generated backups."""

from __future__ import annotations

import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .opener import open_url


def serve(
    output: str | Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    """Serve an existing backup directory until interrupted."""
    root = Path(output).resolve()
    index = root / "index.html"
    if not index.is_file():
        raise FileNotFoundError(f"No index.html found in {root}. Run claude-history first.")

    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(root))
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{server.server_port}/index.html"
    print(f"Serving {root} at {url}")
    if open_browser:
        if not open_url(url):
            print(f"Open manually: {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
