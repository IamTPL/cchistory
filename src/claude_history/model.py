"""Typed data model for parsed Claude Code conversations."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

SCHEMA_VERSION = 1


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class ToolCall:
    name: str
    tool_use_id: str
    input: dict = field(default_factory=dict)
    arg_summary: str = ""
    result_text: str = ""
    structured_result: Any | None = None
    child_stem: str | None = None


@dataclass
class Turn:
    kind: str  # "human" | "assistant" | "command"
    time: datetime
    text: str = ""
    command: str | None = None
    thinking: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str | None = None
    usage: Usage | None = None
    uuid: str | None = None
    parent_uuid: str | None = None


@dataclass
class Totals:
    messages: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_tokens: int = 0
    tool_calls: int = 0
    thinking_blocks: int = 0
    subagents: int = 0
    models: list[str] = field(default_factory=list)
    duration_seconds: float | None = None


@dataclass
class Conversation:
    title: str
    project: str
    cwd: str
    session_id: str
    created: datetime
    last: datetime
    subagent: bool = False
    version: str | None = None
    git_branch: str | None = None
    source_tool_use_id: str | None = None
    turns: list[Turn] = field(default_factory=list)
    totals: Totals = field(default_factory=Totals)
    subagent_links: list[dict] = field(default_factory=list)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat() if value.year > 1 else None
    raise TypeError(f"Not JSON serializable: {type(value)!r}")


def conversation_to_json(conv: Conversation, stem: str) -> str:
    data = asdict(conv)
    data["schema_version"] = SCHEMA_VERSION
    data["stem"] = stem
    return json.dumps(data, ensure_ascii=False, indent=2, default=_json_default)
