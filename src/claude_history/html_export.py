"""HTML template rendering and packaged asset helpers."""

from __future__ import annotations

import html
import json
import shutil
from importlib import resources
from pathlib import Path
from typing import Any


def _read_text_resource(name: str) -> str:
    return resources.files("claude_history").joinpath(name).read_text(encoding="utf-8")


def render_conversation_page(title: str, body_html: str) -> str:
    template = _read_text_resource("templates/conversation.html")
    return template.replace("__TITLE__", html.escape(title)).replace("__BODY__", body_html)


def _script_safe_json(payload: Any) -> str:
    """Serialize ``payload`` for embedding inside an inline ``<script>`` element.

    Escaping ``</`` alone is not enough: a ``<!--`` anywhere in the payload puts the
    HTML tokenizer into the script-data-escaped state, and a later ``<script`` pushes
    it into script-data-double-escaped, where the template's own ``</script>`` no
    longer closes the element. The rest of the document is then swallowed as script
    text and nothing runs. Escaping every angle bracket (plus ``&`` and the line
    terminators JSON leaves raw) keeps the payload inert while staying valid JSON.
    """
    text = json.dumps(payload, ensure_ascii=False)
    for char, escape in (
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("&", "\\u0026"),
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
    ):
        text = text.replace(char, escape)
    return text


def render_index_page(meta: list[dict[str, Any]], manifest: dict[str, Any] | None = None) -> str:
    template = _read_text_resource("templates/index.html")
    rendered = template.replace("__DATA__", _script_safe_json(meta))
    if "__MANIFEST__" in rendered:
        rendered = rendered.replace("__MANIFEST__", _script_safe_json(manifest or {}))
    return rendered


def copy_assets(output_assets: Path) -> None:
    output_assets.mkdir(parents=True, exist_ok=True)
    source = resources.files("claude_history").joinpath("assets")

    def copy_tree(resource, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        for child in resource.iterdir():
            target = destination / child.name
            if child.is_dir():
                copy_tree(child, target)
            else:
                with resources.as_file(child) as asset_path:
                    shutil.copyfile(asset_path, target)

    copy_tree(source, output_assets)
