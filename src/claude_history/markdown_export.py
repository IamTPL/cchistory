"""Markdown and HTML rendering helpers."""

from __future__ import annotations

import html
import json
import re
from typing import Any

import markdown as markdown_lib

from .parser import to_local, truncate

LABEL = {"human": "You", "assistant": "Claude", "command": "Command"}


def conv_to_markdown(
    conv,
    show_tools: bool,
    full_results: bool,
    use_utc: bool = False,
    show_thinking: bool = True,
) -> tuple[str, int]:
    """Render one Conversation as Markdown. Returns (text, rendered_count)."""
    out = [f"# {conv.title}", "", f"*Project: {conv.project}*"]
    if conv.created.year > 1:
        created = to_local(conv.created, use_utc)
        tz = "UTC" if use_utc else "local time"
        out.append(f"*Started: {created.strftime('%Y-%m-%d %H:%M')} ({tz})*")
    out.append(f"*Session: {conv.session_id}*")
    tot = conv.totals
    out.append(
        f"*Tokens: in {tot.input_tokens} / out {tot.output_tokens} / cache "
        f"{tot.cache_tokens} · {tot.tool_calls} tools · {tot.thinking_blocks} thinking*"
    )

    rendered: list[str] = []
    for turn in conv.turns:
        ts = (to_local(turn.time, use_utc).strftime("%Y-%m-%d %H:%M")
              if turn.time.year > 1 else "")
        block: list[str] = []
        if turn.kind == "command":
            block.append(f"`{turn.command}`")
        if turn.text:
            block.append(turn.text)
        if show_thinking and turn.thinking:
            for thought in turn.thinking:
                block.append("> 💭 " + thought.replace("\n", "\n> "))
        if show_tools and turn.tool_calls:
            for tc in turn.tool_calls:
                arrow = f" -> `{tc.arg_summary}`" if tc.arg_summary else ""
                line = f"**Tool: {tc.name}**{arrow}"
                if tc.result_text:
                    line += "\n> " + truncate(tc.result_text, full_results)
                block.append(line)
        if not block:
            continue
        meta = ""
        if turn.kind == "assistant" and (turn.model or turn.usage):
            bits = []
            if turn.model:
                bits.append(turn.model)
            if turn.usage:
                bits.append(f"↑{turn.usage.input_tokens} ↓{turn.usage.output_tokens}")
            meta = " · " + " · ".join(bits)
        header = f"### {LABEL.get(turn.kind, turn.kind)}" + (f"  -  `{ts}`" if ts else "") + meta
        rendered.append(header + "\n\n" + "\n\n".join(block))

    out.append(f"*Messages: {len(rendered)}*\n\n---\n")
    out.append("\n\n---\n\n".join(rendered))
    return "\n".join(out), len(rendered)


def md_to_html(md_text: str) -> str:
    """Render Markdown to HTML using the required offline-safe extensions."""
    safe_markdown = html.escape(md_text, quote=False)
    rendered = markdown_lib.markdown(
        safe_markdown,
        extensions=["fenced_code", "tables", "nl2br", "sane_lists"],
    )
    return _wrap_tables(rendered)


def _wrap_tables(html_text: str) -> str:
    """Wrap Markdown tables so the viewer can scroll them without layout overflow."""
    html_text = re.sub(r"<table(\b[^>]*)>", r'<div class="table-wrap"><table\1>', html_text)
    return html_text.replace("</table>", "</table></div>")


SOFT_CAP = 100_000


def _soft_cap(text: str, full_results: bool) -> str:
    if full_results or len(text) <= SOFT_CAP:
        return text
    dropped = (len(text) - SOFT_CAP) // 1024
    return text[:SOFT_CAP] + f"\n… (đã cắt {dropped} KB, xem .json để đầy đủ)"


def _turn_chips(turn) -> str:
    chips: list[str] = []
    if turn.model:
        chips.append(f'<span class="chip chip-model">{html.escape(turn.model)}</span>')
    if turn.usage:
        u = turn.usage
        chips.append(f'<span class="chip">↑ {u.input_tokens}</span>')
        chips.append(f'<span class="chip">↓ {u.output_tokens}</span>')
        cache = u.cache_creation_input_tokens + u.cache_read_input_tokens
        if cache:
            chips.append(f'<span class="chip">cache {cache}</span>')
    return "".join(chips)


def _thinking_to_html(thinking: list[str]) -> str:
    inner = "\n".join(
        '<div class="thinking-block">' + md_to_html(t) + "</div>" for t in thinking
    )
    return (f'<details class="thinking"><summary>Thinking · {len(thinking)}</summary>'
            f"{inner}</details>")


def _tool_calls_to_html(tool_calls, full_results: bool) -> str:
    parts = ['<div class="tool-list">']
    for tc in tool_calls:
        parts.append('<details class="tool-call"><summary>')
        parts.append(f'<span class="tool-name">{html.escape(tc.name or "tool")}</span>')
        if tc.arg_summary:
            parts.append(f'<span class="tool-arg">{html.escape(tc.arg_summary)}</span>')
        parts.append("</summary>")
        if tc.input:
            pretty = json.dumps(tc.input, ensure_ascii=False, indent=2)
            parts.append('<div class="tool-section">Input</div>')
            parts.append('<pre class="tool-input"><code>'
                         + html.escape(_soft_cap(pretty, full_results)) + "</code></pre>")
        if tc.result_text:
            parts.append('<div class="tool-section">Result</div>')
            parts.append('<pre class="tool-result"><code>'
                         + html.escape(_soft_cap(tc.result_text, full_results)) + "</code></pre>")
        if tc.child_stem:
            parts.append(f'<a class="subagent-link" href="{html.escape(tc.child_stem)}.html" '
                         'target="_top">↳ Mở sub-agent</a>')
        parts.append("</details>")
    parts.append("</div>")
    return "\n".join(parts)


def _turn_to_html(turn, show_tools: bool, full_results: bool,
                  use_utc: bool, show_thinking: bool) -> str:
    label = LABEL.get(turn.kind, turn.kind.title())
    timestamp = (to_local(turn.time, use_utc).strftime("%Y-%m-%d %H:%M")
                 if turn.time.year > 1 else "")
    body: list[str] = []
    if turn.kind == "command" and turn.command:
        body.append('<pre class="command-block"><code>'
                    + html.escape(turn.command) + "</code></pre>")
    if turn.text:
        body.append('<div class="message-content">' + md_to_html(turn.text) + "</div>")
    if show_thinking and turn.thinking:
        body.append(_thinking_to_html(turn.thinking))
    if show_tools and turn.tool_calls:
        body.append(_tool_calls_to_html(turn.tool_calls, full_results))
    if not body:
        return ""
    chips = _turn_chips(turn) if turn.kind == "assistant" else ""
    return "\n".join([
        f'<section class="message message-{reclass(turn.kind)}">',
        '<div class="message-head">',
        f'<span class="message-role">{html.escape(label)}</span>',
        f'<span class="message-chips">{chips}</span>' if chips else "",
        f'<span class="message-time">{html.escape(timestamp)}</span>' if timestamp else "",
        "</div>",
        "\n".join(body),
        "</section>",
    ])


def conv_to_html(
    conv,
    show_tools: bool,
    full_results: bool,
    use_utc: bool = False,
    show_thinking: bool = True,
    stem: str = "",
) -> str:
    created = ""
    if conv.created.year > 1:
        created = to_local(conv.created, use_utc).strftime("%Y-%m-%d %H:%M")
    tz = "UTC" if use_utc else "local time"

    parts = [
        '<article class="conversation">',
        '<header class="conversation-header">',
        '<div class="conversation-eyebrow">Conversation</div>',
        f"<h1>{html.escape(str(conv.title))}</h1>",
        '<div class="conversation-meta">',
        f"<span>{html.escape(str(conv.project))}</span>",
    ]
    if created:
        parts.append(f"<span>{created} ({tz})</span>")
    parts.append(f"<span>{conv.totals.messages} messages</span>")
    parts.append("</div>")
    parts.append(_stats_bar(conv))
    parts.append(_resume_panel(conv, stem))
    parts.extend(["</header>", '<div class="message-list">'])

    for turn in conv.turns:
        rendered = _turn_to_html(turn, show_tools, full_results, use_utc, show_thinking)
        if rendered:
            parts.append(rendered)

    parts.extend(["</div>", "</article>"])
    return "\n".join(parts)


def _stats_bar(conv) -> str:
    tot = conv.totals
    items = [
        ("tokens in", tot.input_tokens), ("out", tot.output_tokens), ("cache", tot.cache_tokens),
        ("turns", tot.messages), ("tools", tot.tool_calls),
        ("thinking", tot.thinking_blocks), ("sub-agents", tot.subagents),
    ]
    cells = "".join(
        f'<span class="stat"><strong>{value}</strong>{html.escape(name)}</span>'
        for name, value in items
    )
    extra: list[str] = []
    if conv.git_branch:
        extra.append(html.escape(conv.git_branch))
    if conv.version:
        extra.append("v" + html.escape(conv.version))
    if tot.models:
        extra.append(html.escape(", ".join(tot.models)))
    tail = f'<div class="stats-extra">{" · ".join(extra)}</div>' if extra else ""
    return f'<div class="stats-bar">{cells}</div>{tail}'


def _resume_panel(conv, stem: str) -> str:
    if conv.cwd:
        cmd = f"cd {conv.cwd} && claude --resume {conv.session_id}"
    else:
        cmd = f"claude --resume {conv.session_id}"
    downloads = ""
    if stem:
        downloads = (
            f'<a class="dl" download href="../markdown/{html.escape(stem)}.md">Download .md</a>'
            f'<a class="dl" download href="{html.escape(stem)}.json">Download .json</a>'
        )
    return (
        '<div class="resume-panel">'
        '<div class="resume-title">↻ Continue</div>'
        f'<pre class="resume-cmd"><code>{html.escape(cmd)}</code></pre>'
        f'<button class="resume-copy" type="button" data-cmd="{html.escape(cmd, quote=True)}">Copy</button>'
        '<div class="resume-hint">thêm <code>--fork-session</code> để rẽ nhánh (giữ bản gốc)</div>'
        f'<div class="resume-downloads">{downloads}</div>'
        "</div>"
    )


def reclass(kind: str) -> str:
    """Return a small safe CSS suffix for a message kind."""
    if kind in {"human", "assistant", "command"}:
        return kind
    return "generic"
