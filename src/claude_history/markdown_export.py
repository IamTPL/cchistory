"""Markdown and HTML rendering helpers."""

from __future__ import annotations

import html
import json
import re
from typing import Any

import markdown as markdown_lib

from .parser import to_local, truncate

LABEL = {"human": "You", "assistant": "Claude", "command": "Command"}


def _format_int(value: int) -> str:
    return f"{int(value or 0):,}"


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
        f"*Tokens: in {_format_int(tot.input_tokens)} / out {_format_int(tot.output_tokens)} / cache "
        f"{_format_int(tot.cache_tokens)} · {_format_int(tot.tool_calls)} tools · "
        f"{_format_int(tot.thinking_blocks)} thinking*"
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
                bits.append(f"↑{_format_int(turn.usage.input_tokens)} ↓{_format_int(turn.usage.output_tokens)}")
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
        chips.append(f'<span class="chip">↑ {_format_int(u.input_tokens)}</span>')
        chips.append(f'<span class="chip">↓ {_format_int(u.output_tokens)}</span>')
        cache = u.cache_creation_input_tokens + u.cache_read_input_tokens
        if cache:
            chips.append(f'<span class="chip">cache {_format_int(cache)}</span>')
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
        open_attr = " open" if tc.child_stem else ""
        parts.append(f'<details class="tool-call"{open_attr}><summary>')
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
            child = html.escape(tc.child_stem)
            parts.append(
                f'<a class="subagent-link" href="{child}.html" '
                f'data-child-file="conversations/{child}.html">Open sub-agent</a>'
            )
        parts.append("</details>")
    parts.append("</div>")
    return "\n".join(parts)


def _turn_to_html(turn, show_tools: bool, full_results: bool,
                  use_utc: bool, show_thinking: bool,
                  turn_index: int = 0, prompt_index: int | None = None) -> str:
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
    classes = f"message message-{reclass(turn.kind)}"
    section_id = f"prompt-{prompt_index}" if prompt_index is not None else f"turn-{turn_index}"
    attrs = [
        f'id="{section_id}"',
        f'data-turn-index="{turn_index}"',
        f'data-kind="{html.escape(turn.kind)}"',
    ]
    if prompt_index is not None:
        classes += " prompt-anchor"
        attrs.append(f'data-prompt-index="{prompt_index}"')
        attrs.append(f'data-prompt-title="{html.escape(_prompt_title(turn.text), quote=True)}"')
    attr_text = " ".join(attrs)
    return "\n".join([
        f'<section class="{classes}" {attr_text}>',
        '<div class="message-head">',
        f'<span class="message-role">{html.escape(label)}</span>',
        f'<span class="message-chips">{chips}</span>' if chips else "",
        f'<span class="message-time">{html.escape(timestamp)}</span>' if timestamp else "",
        "</div>",
        "\n".join(body),
        "</section>",
    ])


def _prompt_title(text: str) -> str:
    title = " ".join(str(text or "").split())
    if len(title) <= 88:
        return title
    return title[:88].rstrip() + "..."


def _prompt_map(prompts: list[tuple[int, Any]], use_utc: bool) -> str:
    if not prompts:
        return ""
    items: list[str] = []
    for index, (_turn_index, turn) in enumerate(prompts, start=1):
        timestamp = (to_local(turn.time, use_utc).strftime("%H:%M")
                     if turn.time.year > 1 else "")
        title = html.escape(_prompt_title(turn.text))
        time = f"<span>{html.escape(timestamp)}</span>" if timestamp else ""
        items.append(
            f'<a class="prompt-item" href="#prompt-{index}" data-prompt-target="{index}">'
            f'<span class="prompt-id">P{index:02d}</span>'
            f'<span class="prompt-text"><strong>{title}</strong>{time}</span>'
            "</a>"
        )
    return (
        '<aside class="prompt-map" aria-label="Prompt map">'
        '<div class="prompt-map-header">'
        '<div class="prompt-map-heading">'
        '<strong>Prompt map</strong>'
        f'<span><span data-current-prompt>1</span> of {len(prompts)}</span>'
        '</div>'
        '<div class="prompt-map-actions">'
        '<button class="map-button" type="button" data-prompt-prev title="Previous prompt">Prev</button>'
        '<button class="map-button is-primary" type="button" data-prompt-next title="Next prompt">Next</button>'
        '</div>'
        '</div>'
        '<div class="prompt-map-current" data-current-prompt-title>Human turns only</div>'
        '<div class="prompt-list">'
        + "\n".join(items)
        + "</div>"
        "</aside>"
    )


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

    prompts = [
        (index, turn)
        for index, turn in enumerate(conv.turns, start=1)
        if turn.kind == "human" and turn.text
    ]

    article_class = "conversation has-prompt-map" if prompts else "conversation"
    parts = [
        f'<article class="{article_class}">',
        '<header class="conversation-header">',
        '<div class="conversation-eyebrow">Conversation stack</div>',
        '<div class="conversation-title-row">',
        f"<h1>{html.escape(str(conv.title))}</h1>",
        '<button class="button continue-open" type="button" '
        'data-continue-open aria-haspopup="dialog" aria-label="Open continue options">'
        'Continue</button>',
        '</div>',
        '<div class="conversation-meta">',
        f"<span>{html.escape(str(conv.project))}</span>",
    ]
    if created:
        parts.append(f"<span>{created} ({tz})</span>")
    parts.append(f"<span>{conv.totals.messages} messages</span>")
    parts.append("</div>")
    parts.append(_stats_bar(conv))
    parts.append(_resume_panel(conv, stem))
    parts.extend(["</header>", '<div class="conversation-body">', '<div class="message-list">'])

    prompt_lookup = {turn_index: prompt_number for prompt_number, (turn_index, _turn) in enumerate(prompts, start=1)}
    for turn_index, turn in enumerate(conv.turns, start=1):
        rendered = _turn_to_html(
            turn, show_tools, full_results, use_utc, show_thinking,
            turn_index=turn_index,
            prompt_index=prompt_lookup.get(turn_index),
        )
        if rendered:
            parts.append(rendered)

    parts.extend(["</div>", _prompt_map(prompts, use_utc), "</div>", "</article>"])
    return "\n".join(parts)


def _stats_bar(conv) -> str:
    tot = conv.totals
    items = [
        ("tokens in", tot.input_tokens), ("out", tot.output_tokens), ("cache", tot.cache_tokens),
        ("turns", tot.messages), ("tools", tot.tool_calls),
        ("thinking", tot.thinking_blocks), ("sub-agents", tot.subagents),
    ]
    cells = "".join(
        f'<span class="stat"><strong>{_format_int(value)}</strong>{html.escape(name)}</span>'
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
        safe_stem = html.escape(stem, quote=True)
        downloads = (
            f'<a class="dl" download="{safe_stem}.md" '
            f'href="../markdown/{safe_stem}.md" data-download>Download Markdown</a>'
            f'<a class="dl" download="{safe_stem}.json" '
            f'href="{safe_stem}.json" data-download>Download JSON</a>'
        )
    return (
        '<div class="modal-backdrop" data-continue-modal hidden>'
        '<section class="continue-dialog" role="dialog" aria-modal="true" '
        'aria-labelledby="continue-title">'
        '<div class="continue-dialog-head">'
        '<div class="continue-dialog-title">'
        '<strong id="continue-title">Continue conversation</strong>'
        '<span>Use this command when the project path exists on this machine.</span>'
        '</div>'
        '<button class="button" type="button" data-continue-close>Close</button>'
        '</div>'
        '<div class="continue-guide">'
        '<p>Run the command in a terminal to reopen this Claude Code session. '
        'Add <code>--fork-session</code> when you want to branch from the saved session.</p>'
        f'<pre class="resume-cmd"><code>{html.escape(cmd)}</code></pre>'
        '</div>'
        '<div class="resume-actions">'
        f'<button class="resume-copy" type="button" data-cmd="{html.escape(cmd, quote=True)}">'
        'Copy command</button>'
        f'{downloads}'
        '</div>'
        '</section>'
        "</div>"
    )


def reclass(kind: str) -> str:
    """Return a small safe CSS suffix for a message kind."""
    if kind in {"human", "assistant", "command"}:
        return kind
    return "generic"
