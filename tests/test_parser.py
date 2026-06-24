from __future__ import annotations

import json
from pathlib import Path

from claude_history.parser import decode_project, parse_conversation


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )


def test_parse_conversation_pairs_tools_filters_noise_and_skips_tool_result_only_user(tmp_path):
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

    conv = parse_conversation(path)

    assert conv.project == "/work/chosen-project"

    human_turns = [t for t in conv.turns if t.kind == "human"]
    assert len(human_turns) == 1
    assert human_turns[0].text == "Please inspect this"
    assert "hidden.py" not in human_turns[0].text

    assistant = next(t for t in conv.turns if t.kind == "assistant")
    assert assistant.tool_calls[0].name == "Bash"
    assert assistant.tool_calls[0].result_text == "done"

    command = next(t for t in conv.turns if t.kind == "command")
    assert command.command == "/compact --hard"

    # tool_result-only user record is skipped — no extra human turn
    assert all(
        "done" not in t.text
        for t in conv.turns
        if t.kind == "human"
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


def test_parse_conversation_accepts_utf8_bom_on_first_line(tmp_path):
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

    conv = parse_conversation(path)

    assert conv.title == "hello with bom"
    assert [t.kind for t in conv.turns] == ["human", "assistant"]


def test_collect_results_merges_block_text_and_top_level_structured():
    from claude_history.parser import collect_results

    records = [{
        "toolUseResult": {"stdout": "hello", "exit_code": 0},
        "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu1", "content": "hello"},
        ]},
    }]
    results = collect_results(records)
    assert results["tu1"][0] == "hello"
    assert results["tu1"][1] == {"stdout": "hello", "exit_code": 0}


def test_build_turns_keeps_thinking_full_tool_io_and_usage():
    from claude_history.parser import build_turns, collect_results

    records = [
        {"timestamp": "2024-01-01T00:00:00Z", "message": {
            "role": "assistant", "model": "claude-opus-4-8",
            "usage": {"input_tokens": 10, "output_tokens": 20, "cache_read_input_tokens": 5},
            "content": [
                {"type": "thinking", "thinking": "let me plan", "signature": "s1"},
                {"type": "thinking", "thinking": "   ", "signature": "s2"},
                {"type": "text", "text": "Doing it"},
                {"type": "tool_use", "id": "tu1", "name": "Write",
                 "input": {"file_path": "a.py", "content": "X" * 5000}},
            ]}},
        {"timestamp": "2024-01-01T00:00:01Z", "toolUseResult": {"ok": True},
         "message": {"role": "user", "content": [
             {"type": "tool_result", "tool_use_id": "tu1", "content": "written"}]}},
    ]
    turns = build_turns(records, collect_results(records))

    assert len(turns) == 1  # tool_result-only user record is skipped
    t = turns[0]
    assert t.kind == "assistant"
    assert t.thinking == ["let me plan"]  # blank thinking dropped
    assert t.model == "claude-opus-4-8"
    assert t.usage.input_tokens == 10 and t.usage.cache_read_input_tokens == 5
    assert t.tool_calls[0].name == "Write"
    assert len(t.tool_calls[0].input["content"]) == 5000  # full input kept
    assert t.tool_calls[0].result_text == "written"
    assert t.tool_calls[0].structured_result == {"ok": True}


def test_build_turns_keeps_long_user_prompt():
    from claude_history.parser import build_turns, collect_results

    records = [{"timestamp": "2024-01-01T00:00:00Z",
                "message": {"role": "user", "content": "x" * 6000}}]
    turns = build_turns(records, collect_results(records))
    assert len(turns) == 1 and turns[0].kind == "human"
    assert len(turns[0].text) == 6000


def test_parse_conversation_uses_ai_title_and_metadata(tmp_path):
    import json as _json
    from claude_history.parser import parse_conversation

    path = tmp_path / "-work-proj" / "1c30f636.jsonl"
    path.parent.mkdir(parents=True)
    records = [
        {"type": "ai-title", "aiTitle": "Nice Title"},
        {"timestamp": "2024-01-01T00:00:00Z", "sessionId": "1c30f636",
         "cwd": "/work/proj", "version": "2.1.177", "gitBranch": "main",
         "message": {"role": "user", "content": "first prompt"}},
        {"timestamp": "2024-01-01T00:00:05Z",
         "message": {"role": "assistant", "model": "claude-opus-4-8",
                     "usage": {"input_tokens": 3, "output_tokens": 4},
                     "content": [{"type": "text", "text": "ack"}]}},
    ]
    path.write_text("\n".join(_json.dumps(r) for r in records), encoding="utf-8")

    conv = parse_conversation(path)
    assert conv.title == "Nice Title"
    assert conv.session_id == "1c30f636"
    assert conv.cwd == "/work/proj"
    assert conv.version == "2.1.177"
    assert conv.git_branch == "main"
    assert conv.totals.messages == 2
    assert conv.totals.output_tokens == 4
    assert conv.totals.models == ["claude-opus-4-8"]
    assert conv.totals.duration_seconds == 5.0
