from __future__ import annotations

import json
from pathlib import Path

from claude_history.parser import decode_project, normalize_jsonl


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )


def test_normalize_jsonl_pairs_tools_filters_noise_and_skips_tool_result_only_user(tmp_path):
    path = tmp_path / "-home-user-fallback-project" / "session.jsonl"
    write_jsonl(
        path,
        [
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "cwd": "/work/chosen-project",
                "message": {
                    "role": "user",
                    "content": "Please inspect this\n<ide_opened_file>/tmp/hidden.py</ide_opened_file>",
                },
            },
            {
                "timestamp": "2024-01-01T00:00:01Z",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "I will run a command."},
                        {
                            "type": "tool_use",
                            "id": "toolu_1",
                            "name": "Bash",
                            "input": {"command": "printf done"},
                        },
                    ],
                },
            },
            {
                "timestamp": "2024-01-01T00:00:02Z",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_1",
                            "content": "done",
                        }
                    ],
                },
            },
            {
                "timestamp": "2024-01-01T00:00:03Z",
                "message": {
                    "role": "user",
                    "content": (
                        "<command-name>compact</command-name>"
                        "<command-args>--hard</command-args>"
                        "<command-message>noise</command-message>"
                    ),
                },
            },
        ],
    )

    conv = normalize_jsonl(path)

    assert conv["project"] == "/work/chosen-project"

    human_messages = [msg for msg in conv["messages"] if msg["kind"] == "human"]
    assert len(human_messages) == 1
    assert human_messages[0]["text"] == "Please inspect this"
    assert "hidden.py" not in human_messages[0]["text"]

    assistant = next(msg for msg in conv["messages"] if msg["kind"] == "assistant")
    assert assistant["tool_calls"][0]["name"] == "Bash"
    assert assistant["tool_calls"][0]["result"] == "done"

    command = next(msg for msg in conv["messages"] if msg["kind"] == "command")
    assert command["command"] == "/compact --hard"
    assert "<command-name>" not in command.get("text", "")

    assert all(
        "done" not in msg.get("text", "")
        for msg in conv["messages"]
        if msg["kind"] == "human"
    )


def test_decode_project_prefers_cwd_and_decodes_folder_fallback():
    assert (
        decode_project("-home-user-fallback-project", "/work/chosen-project")
        == "/work/chosen-project"
    )
    assert (
        decode_project("-home-tplong-WorkSpace-att_ocr_backend", "")
        == "/home/tplong/WorkSpace/att_ocr_backend"
    )


def test_normalize_jsonl_accepts_utf8_bom_on_first_line(tmp_path):
    path = tmp_path / "-work-project" / "session.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    first = json.dumps(
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "message": {"role": "user", "content": "hello with bom"},
        }
    )
    second = json.dumps(
        {
            "timestamp": "2024-01-01T00:00:01Z",
            "message": {"role": "assistant", "content": "ack"},
        }
    )
    path.write_text("\ufeff" + first + "\n" + second + "\n", encoding="utf-8")

    conv = normalize_jsonl(path)

    assert conv["title"] == "hello with bom"
    assert [msg["kind"] for msg in conv["messages"]] == ["human", "assistant"]
