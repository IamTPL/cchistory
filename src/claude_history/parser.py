"""Parse and normalize Claude Code JSONL conversations."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .model import Conversation, Totals, ToolCall, Turn, Usage

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
    if "Base directory for this skill:" in s:
        s = ""
    return s, command


def _parse_usage(raw: Any) -> Usage | None:
    if not isinstance(raw, dict):
        return None
    return Usage(
        input_tokens=int(raw.get("input_tokens") or 0),
        output_tokens=int(raw.get("output_tokens") or 0),
        cache_creation_input_tokens=int(raw.get("cache_creation_input_tokens") or 0),
        cache_read_input_tokens=int(raw.get("cache_read_input_tokens") or 0),
    )


def build_turns(
    records: list[dict[str, Any]], results: dict[str, tuple[str, Any]]
) -> list[Turn]:
    turns: list[Turn] = []
    for rec in records:
        msg = rec.get("message", rec)
        role = msg.get("role") or rec.get("type")
        content = msg.get("content", rec.get("content", ""))
        ts = parse_ts(rec.get("timestamp") or msg.get("timestamp"))
        uuid = rec.get("uuid")
        parent_uuid = rec.get("parentUuid")
        model = msg.get("model")
        usage = _parse_usage(msg.get("usage"))

        text_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        has_real = False
        has_tool_result = False

        if isinstance(content, list):
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
                elif block_type == "thinking":
                    has_real = True
                    thought = (block.get("thinking") or "").strip()
                    if thought:
                        thinking_parts.append(thought)
                elif block_type == "tool_use":
                    has_real = True
                    tool_use_id = block.get("id", "")
                    result_text, structured = results.get(tool_use_id, ("", None))
                    raw_input = block.get("input")
                    tool_calls.append(ToolCall(
                        name=block.get("name", "tool"),
                        tool_use_id=tool_use_id,
                        input=raw_input if isinstance(raw_input, dict) else {},
                        arg_summary=tool_arg_summary(block.get("name"), raw_input),
                        result_text=result_text,
                        structured_result=structured,
                    ))
                elif block_type == "tool_result":
                    has_tool_result = True
        else:
            text_parts.append(str(content or ""))

        if has_tool_result and not has_real:
            continue
        raw = "\n".join(p for p in text_parts if p).strip()

        if role in ("user", "human"):
            text, command = clean_user_text(raw)
            if command:
                turns.append(Turn(kind="command", time=ts, command=command,
                                  uuid=uuid, parent_uuid=parent_uuid))
            if text:
                turns.append(Turn(kind="human", time=ts, text=text,
                                  uuid=uuid, parent_uuid=parent_uuid))
        elif role in ("assistant", "model"):
            if raw or tool_calls or thinking_parts:
                turns.append(Turn(kind="assistant", time=ts, text=raw,
                                  thinking=thinking_parts, tool_calls=tool_calls,
                                  model=model, usage=usage,
                                  uuid=uuid, parent_uuid=parent_uuid))

    turns.sort(key=lambda t: t.time)
    return turns


def read_records(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file into a list of dict records (robust to junk lines)."""
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip().lstrip("﻿")
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                records.append(rec)
    return records


def collect_results(records: list[dict[str, Any]]) -> dict[str, tuple[str, Any]]:
    """Map tool_use_id -> (result_text, structured_result).

    Reads tool_result blocks in message.content and merges the top-level
    ``toolUseResult`` structured payload from the same record.
    """
    results: dict[str, tuple[str, Any]] = {}
    for rec in records:
        structured = rec.get("toolUseResult")
        content = (rec.get("message", rec)).get("content", "")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                c = block.get("content", "")
                if isinstance(c, list):
                    c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                results[block.get("tool_use_id")] = (str(c), structured)
    return results


def pick_title(records: list[dict[str, Any]], turns: list[Turn]) -> str:
    ai_title = ""
    for rec in records:
        if rec.get("aiTitle"):
            ai_title = str(rec["aiTitle"]).strip()
    if ai_title:
        return ai_title[:80]
    for turn in turns:
        if turn.kind == "human" and turn.text:
            return turn.text.splitlines()[0][:60]
    return ""


def compute_totals(turns: list[Turn]) -> Totals:
    totals = Totals(messages=len(turns))
    models: list[str] = []
    first = last = None
    for turn in turns:
        if turn.time.year > 1:
            first = turn.time if first is None else min(first, turn.time)
            last = turn.time if last is None else max(last, turn.time)
        if turn.usage:
            totals.input_tokens += turn.usage.input_tokens
            totals.output_tokens += turn.usage.output_tokens
            totals.cache_tokens += (turn.usage.cache_creation_input_tokens
                                    + turn.usage.cache_read_input_tokens)
        totals.tool_calls += len(turn.tool_calls)
        totals.thinking_blocks += len(turn.thinking)
        if turn.model and turn.model not in models:
            models.append(turn.model)
    totals.models = sorted(models)
    if first is not None and last is not None:
        totals.duration_seconds = (last - first).total_seconds()
    return totals


def parse_conversation(path: Path) -> Conversation:
    records = read_records(path)
    results = collect_results(records)
    turns = build_turns(records, results)

    cwd = next((r.get("cwd") for r in records if r.get("cwd")), "")
    session_id = next((r.get("sessionId") for r in records if r.get("sessionId")), path.stem)
    version = next((r.get("version") for r in records if r.get("version")), None)
    git_branch = next((r.get("gitBranch") for r in records if r.get("gitBranch")), None)
    source_tool_use_id = next(
        (r.get("sourceToolUseID") for r in records if r.get("sourceToolUseID")), None)
    subagent = path.stem.startswith("agent-") or any(r.get("isSidechain") for r in records)

    title = pick_title(records, turns) or path.stem
    if turns:
        created, last = turns[0].time, turns[-1].time
    else:
        created = parse_ts(records[0].get("timestamp") if records else None)
        last = created

    return Conversation(
        title=title,
        project=decode_project(path.parent.name, cwd),
        cwd=cwd or "",
        session_id=session_id,
        created=created,
        last=last,
        subagent=subagent,
        version=version,
        git_branch=git_branch,
        source_tool_use_id=source_tool_use_id,
        turns=turns,
        totals=compute_totals(turns),
    )


