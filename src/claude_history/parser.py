"""Parse and normalize Claude Code JSONL conversations."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESULT_PREVIEW = 300
NOISE_TAGS = (
    "local-command-caveat",
    "local-command-stdout",
    "local-command-stderr",
    "ide_opened_file",
    "ide_selection",
    "system-reminder",
    "command-message",
)


def decode_project(folder_name: str, cwd: str) -> str:
    """Return the best project label, preferring the recorded cwd."""
    if cwd:
        return cwd.rstrip("/\\") or cwd
    name = folder_name.lstrip("-").replace("-", "/")
    if not name:
        return folder_name
    if folder_name.startswith("-"):
        return "/" + name
    return name


def parse_ts(value: Any) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return datetime.min.replace(tzinfo=timezone.utc)
    s = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def to_local(dt: datetime, use_utc: bool = False) -> datetime:
    """Convert an aware datetime to local time unless UTC output is requested."""
    if dt.year <= 1:
        return dt
    return dt if use_utc else dt.astimezone()


def slugify(text: str | None, maxlen: int = 50) -> str:
    """Return a filename-safe slug for all supported operating systems."""
    text = (text or "untitled").strip().lower()
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text)
    text = re.sub(r"[^\w\s.-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_.-]+", "-", text).strip("-")
    text = text[:maxlen].rstrip("-")
    if not text:
        text = "untitled"
    if text.upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }:
        text = f"{text}-file"
    return text


def tool_arg_summary(name: str | None, inp: Any) -> str:
    if not isinstance(inp, dict):
        return ""
    for key in ("file_path", "path", "notebook_path"):
        if inp.get(key):
            return os.path.basename(str(inp[key]))
    for key in ("command", "pattern", "query", "url", "description", "prompt"):
        if inp.get(key):
            val = str(inp[key]).replace("\n", " ").strip()
            return val[:120] + ("..." if len(val) > 120 else "")
    return ""


def truncate(s: Any, full: bool) -> str:
    s = " ".join(str(s).split())
    if full or len(s) <= RESULT_PREVIEW:
        return s
    return s[:RESULT_PREVIEW] + f"... *(remaining {len(s) - RESULT_PREVIEW} chars)*"


def clean_user_text(s: Any) -> tuple[str, str | None]:
    if not isinstance(s, str):
        return "", None
    command = None
    m = re.search(r"<command-name>(.*?)</command-name>", s, re.S)
    if m:
        cmd = m.group(1).strip().lstrip("/")
        a = re.search(r"<command-args>(.*?)</command-args>", s, re.S)
        args = a.group(1).strip() if a else ""
        command = f"/{cmd}" + (f" {args}" if args else "")
    for tag in NOISE_TAGS + ("command-name", "command-args"):
        s = re.sub(rf"<{tag}>.*?</{tag}>", "", s, flags=re.S)
    s = re.sub(r"</?[a-z_-]+>", "", s).strip()
    if "Base directory for this skill:" in s or len(s) > 4000:
        s = ""
    return s, command


def normalize_jsonl(path: Path) -> dict[str, Any]:
    """Normalize one Claude Code JSONL file into renderable messages."""
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip().lstrip("\ufeff")
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                records.append(rec)

    cwd = next((r.get("cwd") for r in records if r.get("cwd")), "")
    subagent = path.stem.startswith("agent-") or any(r.get("isSidechain") for r in records)

    results: dict[str | None, str] = {}
    for rec in records:
        content = (rec.get("message", rec)).get("content", "")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    c = block.get("content", "")
                    if isinstance(c, list):
                        c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                    results[block.get("tool_use_id")] = str(c)

    msgs: list[dict[str, Any]] = []
    for rec in records:
        msg = rec.get("message", rec)
        role = msg.get("role") or rec.get("type")
        content = msg.get("content", rec.get("content", ""))
        ts = parse_ts(rec.get("timestamp") or msg.get("timestamp"))

        text_parts: list[str] = []
        tool_calls: list[dict[str, str]] = []
        only_tool_result = False
        if isinstance(content, list):
            has_real = False
            has_tool_result = False
            for block in content:
                if not isinstance(block, dict):
                    if isinstance(block, str):
                        text_parts.append(block)
                        has_real = True
                    continue
                block_type = block.get("type")
                if block_type == "text":
                    text_parts.append(block.get("text", ""))
                    has_real = True
                elif block_type == "tool_use":
                    has_real = True
                    tool_calls.append(
                        {
                            "name": block.get("name", "tool"),
                            "arg": tool_arg_summary(block.get("name"), block.get("input")),
                            "result": results.get(block.get("id"), ""),
                        }
                    )
                elif block_type == "tool_result":
                    has_tool_result = True
            only_tool_result = has_tool_result and not has_real
        else:
            text_parts.append(str(content or ""))

        if only_tool_result:
            continue
        raw = "\n".join(p for p in text_parts if p).strip()

        if role in ("user", "human"):
            text, command = clean_user_text(raw)
            if command:
                msgs.append(
                    {
                        "kind": "command",
                        "time": ts,
                        "text": "",
                        "command": command,
                        "tool_calls": [],
                    }
                )
            if text:
                msgs.append(
                    {
                        "kind": "human",
                        "time": ts,
                        "text": text,
                        "command": None,
                        "tool_calls": [],
                    }
                )
        elif role in ("assistant", "model"):
            if raw or tool_calls:
                msgs.append(
                    {
                        "kind": "assistant",
                        "time": ts,
                        "text": raw,
                        "command": None,
                        "tool_calls": tool_calls,
                    }
                )

    msgs.sort(key=lambda x: x["time"])
    created = msgs[0]["time"] if msgs else parse_ts(records and records[0].get("timestamp"))
    last = msgs[-1]["time"] if msgs else created
    title = ""
    for msg in msgs:
        if msg["kind"] == "human" and msg["text"]:
            title = msg["text"].splitlines()[0][:60]
            break
    title = title or path.stem
    return {
        "title": title,
        "created": created,
        "last": last,
        "project": decode_project(path.parent.name, cwd),
        "subagent": subagent,
        "messages": msgs,
    }
