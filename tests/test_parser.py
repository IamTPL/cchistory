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


def _user(ts: str, content, **fields) -> dict:
    return {"type": "user", "timestamp": ts, "isSidechain": False,
            "message": {"role": "user", "content": content}, **fields}


def _assistant(ts: str, text: str) -> dict:
    return {"type": "assistant", "timestamp": ts,
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


HUMAN = {"origin": {"kind": "human"}, "promptSource": "sdk", "turnOrigin": "human"}
SMOKE_TEST_NOTIFICATION = (
    "<task-notification>\n"
    "<task-id>bfs8d6k42</task-id>\n"
    "<tool-use-id>toolu_01MdjEfqWQv5Nde7KVzDgUXs</tool-use-id>\n"
    "<output-file>/tmp/claude/tasks/bfs8d6k42.output</output-file>\n"
    "<status>completed</status>\n"
    '<summary>Background command "Run full smoke test in the background" completed (exit code 0)</summary>\n'
    "</task-notification>"
)


def test_background_task_notification_is_a_system_event_not_a_prompt(tmp_path):
    path = tmp_path / "-work-project" / "session.jsonl"
    write_jsonl(path, [
        _user("2026-09-23T04:38:17Z", [{"type": "text", "text": "Is the whole WBS scope covered?"}], **HUMAN),
        _assistant("2026-09-23T04:42:00Z", "The smoke test is running in the background."),
        _user("2026-09-23T04:43:29Z", SMOKE_TEST_NOTIFICATION,
              origin={"kind": "task-notification"}, promptSource="system",
              turnOrigin="task_notification", queueSkipAttachments=True),
    ])

    conv = parse_conversation(path)

    assert [t.text for t in conv.turns if t.kind == "human"] == ["Is the whole WBS scope covered?"]
    assert [t.text for t in conv.turns if t.kind == "system"] == [
        'Background command "Run full smoke test in the background" completed (exit code 0)'
    ]


def test_task_notification_without_origin_metadata_is_detected_from_content(tmp_path):
    path = tmp_path / "-work-project" / "session.jsonl"
    write_jsonl(path, [
        _user("2024-01-01T00:00:00Z", "real prompt"),
        _user("2024-01-01T00:00:05Z", SMOKE_TEST_NOTIFICATION),
    ])

    conv = parse_conversation(path)

    assert [(t.kind, t.text) for t in conv.turns] == [
        ("human", "real prompt"),
        ("system", 'Background command "Run full smoke test in the background" completed (exit code 0)'),
    ]


def test_meta_task_notification_joins_every_summary_and_drops_the_preamble(tmp_path):
    path = tmp_path / "-work-project" / "agent-a55e.jsonl"
    content = (
        "[SYSTEM NOTIFICATION - NOT USER INPUT]\n"
        "This is an automated background-task event, NOT a message from the user.\n\n"
        "<task-notification>\n<task-id>bk2pfmo6d</task-id>\n"
        '<summary>Monitor event: "wait for subagents"</summary>\n<event>checkpoint4</event>\n'
        "</task-notification>\n\n"
        "<task-notification>\n<task-id>bk2pfmo6d</task-id>\n<status>completed</status>\n"
        '<summary>Monitor "wait for subagents" stream ended</summary>\n'
        "</task-notification>"
    )
    write_jsonl(path, [
        _user("2024-01-01T00:00:00Z", "sub-agent task brief"),
        _user("2024-01-01T00:00:05Z", content, isMeta=True, origin={"kind": "task-notification"}),
    ])

    conv = parse_conversation(path)

    assert [(t.kind, t.text) for t in conv.turns] == [
        ("human", "sub-agent task brief"),
        ("system", 'Monitor event: "wait for subagents"\nMonitor "wait for subagents" stream ended'),
    ]


def test_meta_companion_records_are_hidden(tmp_path):
    path = tmp_path / "-work-project" / "session.jsonl"
    write_jsonl(path, [
        _user("2024-01-01T00:00:00Z", [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "iVBO"}},
            {"type": "text", "text": "Why is the Sales sidebar shorter?"},
        ], imagePasteIds=[8], **HUMAN),
        _user("2024-01-01T00:00:00Z", [
            {"type": "text", "text": "[Image: source: /tmp/claude/images/8.png, original 2412x1519]"},
        ], isMeta=True, turnCompanion=True),
        _user("2024-01-01T00:00:03Z",
              "[Image: original 2432x1400, displayed at 2000x1151. "
              "Multiply coordinates by 1.22 to map to original image.]",
              isMeta=True, turnCompanion=True),
        _user("2024-01-01T00:00:04Z",
              "<command-message>workflow-authoring</command-message>\n"
              "<command-name>workflow-authoring</command-name>\n"
              "<skill-format>true</skill-format>",
              isMeta=True, turnCompanion=True),
        _user("2024-01-01T00:00:04Z", "Continue from where you left off.", isMeta=True),
        _assistant("2024-01-01T00:00:09Z", "Because v2 dropped two menu groups."),
    ])

    conv = parse_conversation(path)

    assert [(t.kind, t.text, t.command) for t in conv.turns] == [
        ("human", "Why is the Sales sidebar shorter?", None),
        ("assistant", "Because v2 dropped two menu groups.", None),
    ]


def test_sub_agent_hand_back_is_a_system_event_even_though_it_is_meta(tmp_path):
    path = tmp_path / "-work-project" / "session.jsonl"
    body = ("[Subagent hand-back] The text below is the final report of a subagent. The report follows:\n"
            "  **Yes: e-signature is in Phase 1.**")
    write_jsonl(path, [
        _user("2024-01-01T00:00:00Z", "Is e-signature in scope?", **HUMAN),
        _user("2024-01-01T00:00:30Z",
              f'Another Claude session sent a message:\n<agent-message from="a6c3df08">\n{body}\n</agent-message>',
              isMeta=True, promptSource="system", turnOrigin="peer",
              origin={"kind": "peer", "from": "a6c3df08", "senderTaskId": "a6c3df08", "body": body}),
    ])

    conv = parse_conversation(path)

    assert [t.text for t in conv.turns if t.kind == "human"] == ["Is e-signature in scope?"]
    system = [t for t in conv.turns if t.kind == "system"]
    assert len(system) == 1
    assert "**Yes: e-signature is in Phase 1.**" in system[0].text


def test_interrupt_marker_and_compact_summary_are_system_events(tmp_path):
    path = tmp_path / "-work-project" / "session.jsonl"
    write_jsonl(path, [
        _user("2024-01-01T00:00:00Z",
              "This session is being continued from a previous conversation that ran out of context.",
              isCompactSummary=True, isVisibleInTranscriptOnly=True),
        _user("2024-01-01T00:00:05Z", "keep going", **HUMAN),
        _user("2024-01-01T00:00:09Z", [{"type": "text", "text": "[Request interrupted by user for tool use]"}]),
    ])

    conv = parse_conversation(path)

    assert [(t.kind, t.text) for t in conv.turns] == [
        ("system", "This session is being continued from a previous conversation that ran out of context."),
        ("human", "keep going"),
        ("system", "[Request interrupted by user for tool use]"),
    ]
    assert conv.title == "keep going"


def test_title_falls_back_to_first_command_when_there_is_no_prompt(tmp_path):
    path = tmp_path / "-work-project" / "09916ea3.jsonl"
    write_jsonl(path, [
        _user("2024-01-01T00:00:00Z",
              "<command-message>superpowers:using-superpowers</command-message>\n"
              "<command-name>/superpowers:using-superpowers</command-name>",
              origin={"kind": "human"}),
        _user("2024-01-01T00:00:00Z",
              "<command-message>superpowers:brainstorming</command-message>\n"
              "<command-name>/superpowers:brainstorming</command-name>\n"
              "<command-args>Analyse the report</command-args>",
              origin={"kind": "human"}),
        _user("2024-01-01T00:00:00Z", "Base directory for this skill: /skills/brainstorming\n\n# Brainstorming",
              isMeta=True, turnCompanion=True),
        _assistant("2024-01-01T00:00:04Z", "Reading the spreadsheet."),
        _user("2024-01-01T00:00:09Z", [{"type": "text", "text": "[Request interrupted by user for tool use]"}]),
    ])

    conv = parse_conversation(path)

    assert conv.title == "/superpowers:brainstorming Analyse the report"


def test_meta_brief_that_opens_a_sub_agent_conversation_stays_its_prompt(tmp_path):
    path = tmp_path / "-work-project" / "agent-a7d19229.jsonl"
    brief = "`minimal prompt`\n\nYou are reviewing a pull request for real bugs."
    write_jsonl(path, [
        _user("2024-01-01T00:00:00Z", brief, isSidechain=True, isMeta=True,
              uuid="u1", parentUuid=None),
        {**_assistant("2024-01-01T00:00:04Z", "Getting the diff."), "uuid": "a1", "parentUuid": "u1"},
        _user("2024-01-01T00:00:05Z", "<system-reminder>Report via SubagentHandback.</system-reminder>",
              isSidechain=True, isMeta=True, uuid="u2", parentUuid="a1"),
    ])

    conv = parse_conversation(path)

    assert [(t.kind, t.text) for t in conv.turns] == [
        ("human", brief),
        ("assistant", "Getting the diff."),
    ]
    assert conv.title == "`minimal prompt`"
