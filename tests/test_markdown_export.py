from __future__ import annotations

from claude_history.markdown_export import md_to_html


def test_md_to_html_wraps_tables_for_viewer_overflow():
    html = md_to_html(
        "| Column A | Column B |\n"
        "| --- | --- |\n"
        "| long text | more long text |\n"
    )

    assert '<div class="table-wrap"><table>' in html
    assert "</table></div>" in html


def test_md_to_html_escapes_raw_html():
    html = md_to_html("<script>alert('x')</script>\n\n**safe markdown**")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<strong>safe markdown</strong>" in html


def test_conv_to_markdown_includes_thinking_tokens_and_full_prompt():
    from datetime import datetime, timezone
    from claude_history.markdown_export import conv_to_markdown
    from claude_history.model import Conversation, Totals, Turn, Usage

    dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    conv = Conversation(
        title="T", project="/p", cwd="/p", session_id="sid", created=dt, last=dt,
        turns=[
            Turn(kind="human", time=dt, text="L" * 6000),
            Turn(kind="assistant", time=dt, text="ok", thinking=["my reasoning"],
                 model="claude-opus-4-8", usage=Usage(input_tokens=9, output_tokens=4)),
        ],
        totals=Totals(messages=2, input_tokens=9, output_tokens=4, thinking_blocks=1),
    )
    text, count = conv_to_markdown(conv, show_tools=True, full_results=False)
    assert count == 2
    assert "my reasoning" in text
    assert "claude-opus-4-8" in text
    assert "L" * 6000 in text  # long prompt fully present

    hidden, _ = conv_to_markdown(conv, show_tools=True, full_results=False, show_thinking=False)
    assert "my reasoning" not in hidden


def test_turn_to_html_has_collapsible_thinking_tools_and_chips():
    from datetime import datetime, timezone
    from claude_history.markdown_export import _turn_to_html
    from claude_history.model import ToolCall, Turn, Usage

    dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    turn = Turn(
        kind="assistant", time=dt, text="hi", thinking=["reasoning here"],
        model="claude-opus-4-8", usage=Usage(input_tokens=11, output_tokens=22),
        tool_calls=[ToolCall(name="Bash", tool_use_id="t", input={"command": "ls"},
                             arg_summary="ls", result_text="ok")],
    )
    html_out = _turn_to_html(turn, show_tools=True, full_results=False,
                             use_utc=False, show_thinking=True)
    assert "<details" in html_out
    assert "reasoning here" in html_out
    assert "claude-opus-4-8" in html_out
    assert "11" in html_out and "22" in html_out
    assert "Bash" in html_out and "command" in html_out

    no_think = _turn_to_html(turn, show_tools=True, full_results=False,
                             use_utc=False, show_thinking=False)
    assert "reasoning here" not in no_think
