from __future__ import annotations

import json
import re
from pathlib import Path

from claude_backup.builder import build


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
