from __future__ import annotations

from datetime import datetime, timezone

from claude_history.markdown_export import conv_to_html
from claude_history.model import Conversation, Totals, Turn


def test_conv_to_html_has_stats_bar_and_resume_command():
    dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    conv = Conversation(
        title="T", project="/work/proj", cwd="/work/proj", session_id="1c30f636",
        created=dt, last=dt,
        turns=[Turn(kind="human", time=dt, text="hello")],
        totals=Totals(messages=1, input_tokens=10, output_tokens=20, tool_calls=2),
    )
    out = conv_to_html(conv, show_tools=True, full_results=False, stem="2024-01-01_t_abc")
    assert "stats-bar" in out
    assert "cd /work/proj &amp;&amp; claude --resume 1c30f636" in out
    assert "--fork-session" in out
    assert 'href="../markdown/2024-01-01_t_abc.md"' in out
    assert 'href="2024-01-01_t_abc.json"' in out


def test_export_conversation_finds_and_writes_json(tmp_path):
    import json as _json
    from claude_history.cli import export_conversation

    conv_dir = tmp_path / "out" / "conversations"
    md_dir = tmp_path / "out" / "markdown"
    conv_dir.mkdir(parents=True)
    md_dir.mkdir(parents=True)
    stem = "2024-01-01_hello_abc"
    (conv_dir / f"{stem}.json").write_text(
        _json.dumps({"title": "Hello World", "session_id": "sid-1", "stem": stem}),
        encoding="utf-8")
    (md_dir / f"{stem}.md").write_text("# Hello World", encoding="utf-8")

    out_file = tmp_path / "exported.json"
    result = export_conversation("hello world", "json", str(tmp_path / "out"), str(out_file))
    assert result == out_file
    assert _json.loads(out_file.read_text(encoding="utf-8"))["session_id"] == "sid-1"

    md_out = export_conversation("sid-1", "md", str(tmp_path / "out"), None)
    assert md_out is None  # printed to stdout, returns None
