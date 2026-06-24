from __future__ import annotations

import json
import re
from pathlib import Path

from claude_history.builder import build


def write_jsonl(path: Path, message: str, cwd: str = "/work/project") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "cwd": cwd,
            "message": {"role": "user", "content": message},
        },
        {
            "timestamp": "2024-01-01T00:00:01Z",
            "message": {"role": "assistant", "content": "ack"},
        },
    ]
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )


def write_jsonl_at(path: Path, message: str, timestamp: str, cwd: str = "/work/project") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        {
            "timestamp": timestamp,
            "cwd": cwd,
            "message": {"role": "user", "content": message},
        }
    ]
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )


def read_index_data(index_path: Path) -> list[dict]:
    text = index_path.read_text(encoding="utf-8")
    match = re.search(r"const DATA = (.*?);", text, re.S)
    assert match
    return json.loads(match.group(1))


def test_build_full_rebuild_removes_owned_orphans_but_keeps_user_files(tmp_path):
    source = tmp_path / "source"
    first_jsonl = source / "-work-project" / "first.jsonl"
    second_jsonl = source / "-work-project" / "second.jsonl"
    output = tmp_path / "out"
    output.mkdir()
    user_file = output / "user-notes.txt"
    user_file.write_text("do not remove", encoding="utf-8")

    write_jsonl(first_jsonl, "first message")

    first_index = build(
        [source],
        output,
        show_tools=True,
        full_results=False,
        by_activity=False,
        use_utc=False,
        no_subagents=False,
        incremental=False,
    )

    assert first_index == output / "index.html"
    assert first_index.exists()
    assert len(list((output / "conversations").glob("*.html"))) == 1
    assert len(list((output / "markdown").glob("*.md"))) == 1
    assert (output / "assets" / "style.css").exists()
    assert (output / "assets" / "fonts" / "Geist-Variable.woff2").exists()
    assert (output / "assets" / "fonts" / "GeistMono-Variable.woff2").exists()

    (output / "conversations" / "orphan.html").write_text("old", encoding="utf-8")
    (output / "markdown" / "orphan.md").write_text("old", encoding="utf-8")
    (output / "assets" / "orphan.css").write_text("old", encoding="utf-8")
    first_index.write_text("stale index", encoding="utf-8")

    first_jsonl.unlink()
    write_jsonl(second_jsonl, "second message")

    second_index = build(
        [source],
        output,
        show_tools=True,
        full_results=False,
        by_activity=False,
        use_utc=False,
        no_subagents=False,
        incremental=False,
    )

    assert second_index == output / "index.html"
    assert user_file.read_text(encoding="utf-8") == "do not remove"
    assert not (output / "conversations" / "orphan.html").exists()
    assert not (output / "markdown" / "orphan.md").exists()
    assert not (output / "assets" / "orphan.css").exists()

    conversation_files = list((output / "conversations").glob("*.html"))
    markdown_files = list((output / "markdown").glob("*.md"))
    assert len(conversation_files) == 1
    assert len(markdown_files) == 1

    rendered = conversation_files[0].read_text(encoding="utf-8")
    assert "second message" in rendered
    assert "first message" not in rendered
    assert "stale index" not in second_index.read_text(encoding="utf-8")


def test_build_index_metadata_is_newest_first(tmp_path):
    source = tmp_path / "source"
    output = tmp_path / "out"
    write_jsonl_at(source / "-work-project" / "older.jsonl", "older", "2024-01-01T00:00:00Z")
    write_jsonl_at(source / "-work-project" / "newer.jsonl", "newer", "2024-01-03T00:00:00Z")

    index = build([source], output, incremental=False)

    data = read_index_data(index)
    assert [item["t"] for item in data] == ["newer", "older"]
    assert data[0]["s"] > data[1]["s"]


def test_build_writes_lightweight_manifest(tmp_path):
    source = tmp_path / "source"
    output = tmp_path / "out"
    write_jsonl_at(source / "-work-project" / "one.jsonl", "hello", "2024-01-01T00:00:00Z")

    index = build([source], output, incremental=False)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))

    assert "const MANIFEST =" not in index.read_text(encoding="utf-8")
    assert manifest["summary"]["conversation_count"] == 1
    assert manifest["summary"]["prompt_count"] == 1
    assert manifest["projects"][0]["name"] == "/work/project"


def test_build_index_metadata_contains_capped_deep_search_text(tmp_path):
    import json as _json
    source = tmp_path / "source" / "-work-project"
    source.mkdir(parents=True)
    output = tmp_path / "out"
    records = [
        {"timestamp": "2024-01-01T00:00:00Z", "cwd": "/work/project",
         "message": {"role": "user", "content": "find alpha prompt"}},
        {"timestamp": "2024-01-01T00:00:01Z",
         "message": {"role": "assistant", "content": "deep beta assistant answer"}},
    ]
    (source / "one.jsonl").write_text(
        "\n".join(_json.dumps(record) for record in records), encoding="utf-8")

    index = build([source], output, incremental=False)
    data = read_index_data(index)

    assert "find alpha prompt" in data[0]["q"]
    assert "deep beta assistant answer" in data[0]["q"]
    assert len(data[0]["q"]) <= 16_000


def test_index_metadata_includes_capped_deep_search_text(tmp_path):
    source = tmp_path / "source" / "-work-project"
    source.mkdir(parents=True)
    output = tmp_path / "out"
    records = [
        {"timestamp": "2024-01-01T00:00:00Z", "cwd": "/work/project",
         "message": {"role": "user", "content": "ordinary title prompt"}},
    ]
    for index in range(24):
        records.append({"timestamp": f"2024-01-01T00:00:{index + 1:02d}Z", "message": {
            "role": "assistant", "content": f"filler assistant response {index}"}})
    records.append({"timestamp": "2024-01-01T00:00:59Z", "message": {
        "role": "assistant", "content": "deep assistant phrase lemon-sky-indexable"}})
    (source / "s.jsonl").write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )

    index = build([source], output, incremental=False)

    data = read_index_data(index)
    assert "lemon-sky-indexable" in data[0]["q"]
    assert len(data[0]["q"]) <= 16_000


def test_incremental_reuse_invalidated_when_options_change(tmp_path):
    import json as _json
    source = tmp_path / "source" / "-work-project"
    source.mkdir(parents=True)
    output = tmp_path / "out"
    records = [
        {"timestamp": "2024-01-01T00:00:00Z", "cwd": "/work/project",
         "message": {"role": "user", "content": "hi"}},
        {"timestamp": "2024-01-01T00:00:01Z", "message": {
            "role": "assistant", "content": [
                {"type": "thinking", "thinking": "reasoning here", "signature": "s"},
                {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}},
            ]}},
        {"timestamp": "2024-01-01T00:00:02Z", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}},
    ]
    (source / "s.jsonl").write_text("\n".join(_json.dumps(r) for r in records), encoding="utf-8")

    # First build with defaults (thinking + tools shown)
    build([source], output, incremental=True)
    first = next((output / "conversations").glob("*.html")).read_text(encoding="utf-8")
    assert "reasoning here" in first and "tool-list" in first

    # Second incremental build with both turned off -> cache MUST invalidate & re-render
    build([source], output, show_tools=False, show_thinking=False, incremental=True)
    second = next((output / "conversations").glob("*.html")).read_text(encoding="utf-8")
    assert "reasoning here" not in second
    assert "tool-list" not in second


def test_build_links_subagent_to_parent_task(tmp_path):
    import json as _json
    source = tmp_path / "source" / "-work-project"
    source.mkdir(parents=True)
    output = tmp_path / "out"

    parent = [
        {"timestamp": "2024-01-01T00:00:00Z", "sessionId": "parent",
         "cwd": "/work/project", "message": {"role": "user", "content": "do it"}},
        {"timestamp": "2024-01-01T00:00:01Z", "sessionId": "parent",
         "message": {"role": "assistant", "content": [
             {"type": "tool_use", "id": "task-1", "name": "Task",
              "input": {"prompt": "sub work"}}]}},
    ]
    child = [
        {"timestamp": "2024-01-01T00:00:02Z", "sessionId": "child",
         "isSidechain": True, "sourceToolUseID": "task-1",
         "message": {"role": "user", "content": "sub work"}},
        {"timestamp": "2024-01-01T00:00:03Z", "sessionId": "child",
         "isSidechain": True, "message": {"role": "assistant", "content": "done"}},
    ]
    (source / "parent.jsonl").write_text("\n".join(_json.dumps(r) for r in parent), encoding="utf-8")
    (source / "agent-child.jsonl").write_text("\n".join(_json.dumps(r) for r in child), encoding="utf-8")

    build([source], output, incremental=False)

    parent_json = next(p for p in (output / "conversations").glob("*.json")
                       if _json.loads(p.read_text())["session_id"] == "parent")
    data = _json.loads(parent_json.read_text(encoding="utf-8"))
    link = data["turns"][1]["tool_calls"][0]["child_stem"]
    assert link  # parent's Task tool_use now points at the child's stem
    assert data["totals"]["subagents"] == 1


def test_cli_parser_has_no_thinking_flag():
    from claude_history.cli import _build_parser
    args = _build_parser().parse_args(["--no-thinking"])
    assert args.no_thinking is True
    assert _build_parser().parse_args([]).no_thinking is False
