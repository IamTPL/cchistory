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


def render_index_page(meta: list[dict[str, Any]]) -> str:
    template = _read_text_resource("templates/index.html")
    data = json.dumps(meta, ensure_ascii=False).replace("</", "<\\/")
    return template.replace("__DATA__", data)


def copy_assets(output_assets: Path) -> None:
    output_assets.mkdir(parents=True, exist_ok=True)
    source = resources.files("claude_history").joinpath("assets/style.css")
    with resources.as_file(source) as asset_path:
        shutil.copyfile(asset_path, output_assets / "style.css")
