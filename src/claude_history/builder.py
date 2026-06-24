"""Build Markdown and offline HTML backups from Claude Code JSONL sources."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

from .html_export import copy_assets, render_conversation_page, render_index_page
from .markdown_export import conv_to_html, conv_to_markdown
from .model import SCHEMA_VERSION, conversation_to_json
from .parser import parse_conversation, slugify, to_local

CACHE_FILE = ".claude-history-cache.json"
OWNED_DIRS = ("conversations", "markdown", "assets")


def _coerce_sources(sources: str | Path | Iterable[str | Path]) -> list[Path]:
    if isinstance(sources, (str, Path)):
        return [Path(sources)]
    return [Path(source) for source in sources]


def _iter_jsonl_files(sources: list[Path]) -> list[Path]:
    files: list[Path] = []
    for source in sources:
        files.extend(path for path in source.rglob("*.jsonl") if path.is_file())
    return sorted(files)


def _source_key(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _short_hash(path: Path) -> str:
    return hashlib.sha1(_source_key(path).encode("utf-8", errors="replace")).hexdigest()[:10]


def _stem_for(path: Path, conv, use_utc: bool) -> str:
    date = (to_local(conv.created, use_utc).strftime("%Y-%m-%d")
            if conv.created.year > 1 else "0000-00-00")
    return f"{date}_{slugify(conv.title)}_{_short_hash(path)}"


def _load_cache(out: Path) -> dict[str, Any]:
    cache_path = out / CACHE_FILE
    if not cache_path.is_file():
        return {"files": {}}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {"files": {}}


def _write_cache(out: Path, cache: dict[str, Any]) -> None:
    (out / CACHE_FILE).write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _clean_full_rebuild(out: Path) -> None:
    for subdir in OWNED_DIRS:
        shutil.rmtree(out / subdir, ignore_errors=True)
    try:
        (out / "index.html").unlink()
    except FileNotFoundError:
        pass


def _ensure_layout(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for subdir in OWNED_DIRS:
        (out / subdir).mkdir(parents=True, exist_ok=True)
    copy_assets(out / "assets")


def _remove_rendered_files(out: Path, entry: dict[str, Any]) -> None:
    stem = entry.get("stem")
    if not stem:
        return
    for relative in (
        Path("conversations") / f"{stem}.html",
        Path("conversations") / f"{stem}.json",
        Path("markdown") / f"{stem}.md",
    ):
        try:
            (out / relative).unlink()
        except FileNotFoundError:
            pass


def _remove_unknown_rendered_files(out: Path, live_stems: set[str]) -> None:
    for folder, suffix in (("conversations", ".html"), ("conversations", ".json"),
                           ("markdown", ".md")):
        root = out / folder
        if not root.is_dir():
            continue
        for path in root.glob(f"*{suffix}"):
            if path.stem not in live_stems:
                try:
                    path.unlink()
                except OSError:
                    pass


def _metadata_from_conv(conv, stem: str, count: int, use_utc: bool) -> dict[str, Any]:
    date = (to_local(conv.created, use_utc).strftime("%Y-%m-%d")
            if conv.created.year > 1 else "0000-00-00")
    last = (to_local(conv.last, use_utc).isoformat() if conv.last.year > 1 else "")
    return {
        "t": conv.title, "p": conv.project, "dt": date, "last": last,
        "n": count, "f": f"conversations/{stem}.html", "sa": bool(conv.subagent),
    }


def _render_conv(
    conv,
    source_file: Path,
    stem: str,
    out: Path,
    show_tools: bool,
    full_results: bool,
    use_utc: bool,
    show_thinking: bool,
) -> dict[str, Any]:
    md_text, count = conv_to_markdown(conv, show_tools, full_results, use_utc, show_thinking)
    (out / "markdown" / f"{stem}.md").write_text(md_text, encoding="utf-8")
    body = conv_to_html(conv, show_tools, full_results, use_utc, show_thinking, stem)
    (out / "conversations" / f"{stem}.html").write_text(
        render_conversation_page(conv.title, body), encoding="utf-8")
    try:
        (out / "conversations" / f"{stem}.json").write_text(
            conversation_to_json(conv, stem), encoding="utf-8")
    except OSError:
        pass
    stat = source_file.stat()
    return {
        "mtime_ns": stat.st_mtime_ns, "size": stat.st_size, "stem": stem,
        "subagent": bool(conv.subagent), "session_id": conv.session_id,
        "source_tool_use_id": conv.source_tool_use_id,
        "sort_created": conv.created.timestamp() if conv.created.year > 1 else 0,
        "sort_last": conv.last.timestamp() if conv.last.year > 1 else 0,
        "meta": _metadata_from_conv(conv, stem, count, use_utc),
    }


def build(
    sources: str | Path | Iterable[str | Path],
    output: str | Path,
    show_tools: bool = True,
    full_results: bool = False,
    by_activity: bool = False,
    use_utc: bool = False,
    no_subagents: bool = False,
    incremental: bool = False,
    show_thinking: bool = True,
) -> Path:
    """Build the backup tree and return the generated index path."""
    source_paths = _coerce_sources(sources)
    files = _iter_jsonl_files(source_paths)
    if not files:
        raise FileNotFoundError(
            "No .jsonl files found in: " + ", ".join(str(source) for source in source_paths)
        )

    out = Path(output)
    if not incremental:
        _clean_full_rebuild(out)
    _ensure_layout(out)

    current_options = [bool(show_tools), bool(full_results), bool(use_utc),
                       bool(show_thinking), SCHEMA_VERSION]
    old_cache = _load_cache(out) if incremental else {"files": {}}
    old_entries = old_cache.get("files", {}) if old_cache.get("options") == current_options else {}
    new_entries: dict[str, Any] = {}

    # PASS 1: parse all into Conversation objects
    parsed: list[tuple[Path, Any, str]] = []  # (path, conv, stem)
    for source_file in files:
        conv = parse_conversation(source_file)
        if not conv.turns:
            continue
        parsed.append((source_file, conv, _stem_for(source_file, conv, use_utc)))

    # Link map: source_tool_use_id -> child stem
    link_map = {
        conv.source_tool_use_id: stem
        for _, conv, stem in parsed
        if conv.source_tool_use_id
    }
    # PASS 1b: attach child_stem to matching parent tool calls
    for _, conv, _stem in parsed:
        linked = 0
        for turn in conv.turns:
            for tc in turn.tool_calls:
                child = link_map.get(tc.tool_use_id)
                if child:
                    tc.child_stem = child
                    conv.subagent_links.append({
                        "tool_use_id": tc.tool_use_id, "child_stem": child})
                    linked += 1
        conv.totals.subagents = linked

    # PASS 2: render (with render-level incremental reuse)
    for source_file, conv, stem in parsed:
        key = _source_key(source_file)
        stat = source_file.stat()
        previous = old_entries.get(key)
        previous_stem = previous.get("stem") if isinstance(previous, dict) else None
        can_reuse = (
            incremental and isinstance(previous, dict)
            and previous.get("mtime_ns") == stat.st_mtime_ns
            and previous.get("size") == stat.st_size
            and previous_stem == stem
            and not conv.subagent_links  # always re-render parents that link children
            and (out / "markdown" / f"{stem}.md").is_file()
            and (out / "conversations" / f"{stem}.html").is_file()
            and (out / "conversations" / f"{stem}.json").is_file()
        )
        if can_reuse:
            entry = previous
        else:
            if isinstance(previous, dict):
                _remove_rendered_files(out, previous)
            entry = _render_conv(conv, source_file, stem, out,
                                 show_tools, full_results, use_utc, show_thinking)
        new_entries[key] = entry

    for key, entry in old_entries.items():
        if key not in new_entries and isinstance(entry, dict):
            _remove_rendered_files(out, entry)

    visible_entries = [
        entry
        for entry in new_entries.values()
        if not (no_subagents and entry.get("subagent"))
    ]
    sort_key = "sort_last" if by_activity else "sort_created"
    visible_entries.sort(key=lambda entry: entry.get(sort_key, 0), reverse=True)

    meta = [
        {**entry["meta"], "s": entry.get(sort_key, 0)}
        for entry in visible_entries
    ]
    live_stems = {entry["stem"] for entry in new_entries.values() if entry.get("stem")}
    _remove_unknown_rendered_files(out, live_stems)
    (out / "index.html").write_text(render_index_page(meta), encoding="utf-8")

    _write_cache(out, {"files": new_entries, "options": current_options})
    return out / "index.html"
