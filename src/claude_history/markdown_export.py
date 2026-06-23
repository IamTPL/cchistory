"""Markdown and HTML rendering helpers."""

from __future__ import annotations

import html
import re
from typing import Any

import markdown as markdown_lib

from .parser import to_local, truncate

LABEL = {"human": "You", "assistant": "Claude", "command": "Command"}


def conv_to_markdown(
    conv: dict[str, Any],
    show_tools: bool,
    full_results: bool,
    use_utc: bool = False,
) -> tuple[str, int]:
    """Render one normalized conversation as Markdown."""
    out = [f"# {conv['title']}", "", f"*Project: {conv['project']}*"]
    if conv["created"].year > 1:
        created = to_local(conv["created"], use_utc)
        tz = "UTC" if use_utc else "local time"
        out.append(f"*Started: {created.strftime('%Y-%m-%d %H:%M')} ({tz})*")

    rendered: list[str] = []
    for msg in conv["messages"]:
        ts = (
            to_local(msg["time"], use_utc).strftime("%Y-%m-%d %H:%M")
            if msg["time"].year > 1
            else ""
        )
        block: list[str] = []
        if msg["kind"] == "command":
            block.append(f"`{msg['command']}`")
        if msg["text"]:
            block.append(msg["text"])
        if show_tools and msg["tool_calls"]:
            for tool_call in msg["tool_calls"]:
                arrow = f" -> `{tool_call['arg']}`" if tool_call["arg"] else ""
                line = f"**Tool: {tool_call['name']}**{arrow}"
                if tool_call["result"]:
                    line += "\n> " + truncate(tool_call["result"], full_results)
                block.append(line)
        if not block:
            continue
        header = f"### {LABEL.get(msg['kind'], msg['kind'])}" + (f"  -  `{ts}`" if ts else "")
        rendered.append(header + "\n\n" + "\n\n".join(block))

    out.append(f"*Messages: {len(rendered)}*\n\n---\n")
    out.append("\n\n---\n\n".join(rendered))
    return "\n".join(out), len(rendered)


def md_to_html(md_text: str) -> str:
    """Render Markdown to HTML using the required offline-safe extensions."""
    rendered = markdown_lib.markdown(
        md_text,
        extensions=["fenced_code", "tables", "nl2br", "sane_lists"],
    )
    return _wrap_tables(rendered)


def _wrap_tables(html_text: str) -> str:
    """Wrap Markdown tables so the viewer can scroll them without layout overflow."""
    html_text = re.sub(r"<table(\b[^>]*)>", r'<div class="table-wrap"><table\1>', html_text)
    return html_text.replace("</table>", "</table></div>")


def conv_to_html(
    conv: dict[str, Any],
    show_tools: bool,
    full_results: bool,
    use_utc: bool = False,
) -> str:
    """Render one normalized conversation as semantic HTML for the viewer."""
    created = ""
    if conv["created"].year > 1:
        created = to_local(conv["created"], use_utc).strftime("%Y-%m-%d %H:%M")
    tz = "UTC" if use_utc else "local time"

    parts = [
        '<article class="conversation">',
        '<header class="conversation-header">',
        '<div class="conversation-eyebrow">Conversation</div>',
        f"<h1>{html.escape(str(conv['title']))}</h1>",
        '<div class="conversation-meta">',
        f"<span>{html.escape(str(conv['project']))}</span>",
    ]
    if created:
        parts.append(f"<span>{created} ({tz})</span>")
    parts.append(f"<span>{len(conv['messages'])} messages</span>")
    parts.extend(["</div>", "</header>", '<div class="message-list">'])

    for message in conv["messages"]:
        rendered = _message_to_html(message, show_tools, full_results, use_utc)
        if rendered:
            parts.append(rendered)

    parts.extend(["</div>", "</article>"])
    return "\n".join(parts)


def _message_to_html(
    message: dict[str, Any],
    show_tools: bool,
    full_results: bool,
    use_utc: bool,
) -> str:
    kind = str(message.get("kind", "message"))
    label = LABEL.get(kind, kind.title())
    timestamp = (
        to_local(message["time"], use_utc).strftime("%Y-%m-%d %H:%M")
        if message["time"].year > 1
        else ""
    )
    body_parts: list[str] = []

    if kind == "command" and message.get("command"):
        body_parts.append(
            '<pre class="command-block"><code>'
            + html.escape(str(message["command"]))
            + "</code></pre>"
        )
    if message.get("text"):
        body_parts.append(
            '<div class="message-content">'
            + md_to_html(str(message["text"]))
            + "</div>"
        )
    if show_tools and message.get("tool_calls"):
        body_parts.append(_tool_calls_to_html(message["tool_calls"], full_results))
    if not body_parts:
        return ""

    safe_kind = reclass(kind)
    return "\n".join(
        [
            f'<section class="message message-{safe_kind}">',
            '<div class="message-head">',
            f'<span class="message-role">{html.escape(label)}</span>',
            f'<span class="message-time">{html.escape(timestamp)}</span>' if timestamp else "",
            "</div>",
            "\n".join(body_parts),
            "</section>",
        ]
    )


def _tool_calls_to_html(tool_calls: list[dict[str, str]], full_results: bool) -> str:
    parts = ['<div class="tool-list">']
    for tool_call in tool_calls:
        name = html.escape(str(tool_call.get("name", "tool")))
        arg = html.escape(str(tool_call.get("arg", "")))
        result = str(tool_call.get("result", ""))
        parts.append('<details class="tool-call">')
        parts.append("<summary>")
        parts.append(f'<span class="tool-name">{name}</span>')
        if arg:
            parts.append(f'<span class="tool-arg">{arg}</span>')
        parts.append("</summary>")
        if result:
            parts.append(
                '<pre class="tool-result"><code>'
                + html.escape(truncate(result, full_results))
                + "</code></pre>"
            )
        parts.append("</details>")
    parts.append("</div>")
    return "\n".join(parts)


def reclass(kind: str) -> str:
    """Return a small safe CSS suffix for a message kind."""
    if kind in {"human", "assistant", "command"}:
        return kind
    return "generic"
