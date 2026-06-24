from __future__ import annotations

import json
from datetime import datetime, timezone

from claude_history.model import (
    Conversation, Totals, ToolCall, Turn, Usage,
    conversation_to_json, SCHEMA_VERSION,
)


def _dt():
    return datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_conversation_to_json_serializes_full_detail():
    conv = Conversation(
        title="t", project="/p", cwd="/p", session_id="sid",
        created=_dt(), last=_dt(),
        version="2.1.177", git_branch="main",
        turns=[Turn(
            kind="assistant", time=_dt(), text="hi",
            thinking=["because"], model="claude-opus-4-8",
            usage=Usage(input_tokens=5, output_tokens=7, cache_read_input_tokens=3),
            tool_calls=[ToolCall(
                name="Bash", tool_use_id="x",
                input={"command": "ls"}, arg_summary="ls", result_text="ok",
            )],
        )],
        totals=Totals(messages=1, input_tokens=5, output_tokens=7, models=["claude-opus-4-8"]),
    )
    data = json.loads(conversation_to_json(conv, "2024-01-01_t_abc"))

    assert data["schema_version"] == SCHEMA_VERSION
    assert data["stem"] == "2024-01-01_t_abc"
    assert data["session_id"] == "sid"
    assert data["created"].startswith("2024-01-01")
    assert data["turns"][0]["thinking"] == ["because"]
    assert data["turns"][0]["usage"]["input_tokens"] == 5
    assert data["turns"][0]["tool_calls"][0]["input"] == {"command": "ls"}
    assert data["turns"][0]["tool_calls"][0]["child_stem"] is None
