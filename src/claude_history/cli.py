"""Command line interface for claude-history."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .builder import build
from .discovery import discover_sources
from .opener import open_viewer
from .server import serve as serve_backup


def export_conversation(query: str, fmt: str, output_dir: str,
                        out_file: str | None = None):
    base = Path(output_dir) / "conversations"
    sidecars = sorted(base.glob("*.json"))
    if not sidecars:
        raise FileNotFoundError(
            f"No build found in {output_dir}. Run 'claude-history' first.")
    needle = query.lower()
    match = None
    for sidecar in sidecars:
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        haystack = f"{data.get('title', '')} {data.get('session_id', '')} {sidecar.stem}".lower()
        if needle in haystack:
            match = (sidecar, data)
            break
    if match is None:
        raise FileNotFoundError(f"No conversation matches: {query!r}")
    sidecar, _data = match
    if fmt == "json":
        content = sidecar.read_text(encoding="utf-8")
    else:
        md_path = Path(output_dir) / "markdown" / f"{sidecar.stem}.md"
        content = md_path.read_text(encoding="utf-8")
    if out_file:
        Path(out_file).write_text(content, encoding="utf-8")
        return Path(out_file)
    print(content)
    return None


def _add_open_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--open", dest="open_browser", action="store_true", default=True)
    parser.add_argument("--no-open", dest="open_browser", action="store_false")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claude-history",
        description="Export and browse Claude Code history offline.",
    )
    parser.add_argument(
        "--source",
        action="append",
        help="Claude Code projects directory. Can be passed more than once.",
    )
    parser.add_argument(
        "--all-sources",
        action="store_true",
        help="Use every discovered source instead of only the first one.",
    )
    parser.add_argument("-o", "--output", default="claude_history_export")
    parser.add_argument(
        "--by-activity",
        action="store_true",
        help="Sort by last activity instead of conversation start.",
    )
    parser.add_argument("--no-tools", action="store_true")
    parser.add_argument("--no-thinking", action="store_true")
    parser.add_argument("--full-results", action="store_true")
    parser.add_argument("--incremental", action="store_true")
    parser.add_argument("--utc", action="store_true")
    parser.add_argument("--no-subagents", action="store_true")
    _add_open_flags(parser)

    subparsers = parser.add_subparsers(dest="command")
    serve_parser = subparsers.add_parser("serve", help="Serve an existing backup locally.")
    serve_parser.add_argument("-o", "--output", default="claude_history_export")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)
    _add_open_flags(serve_parser)

    export_parser = subparsers.add_parser("export", help="Export one conversation as md/json.")
    export_parser.add_argument("query", help="Title, session id, or filename fragment.")
    export_parser.add_argument("--format", choices=["md", "json"], default="md")
    export_parser.add_argument("--from", dest="from_dir", default="claude_history_export")
    export_parser.add_argument("-o", "--output", default=None)
    return parser


def _resolve_sources(args: argparse.Namespace) -> list[Path]:
    if args.source:
        return [Path(source) for source in args.source]

    found = discover_sources()
    if not found:
        raise FileNotFoundError(
            "Could not find Claude Code data. Use --source <projects-dir>."
        )

    if len(found) > 1:
        print("Discovered Claude Code sources:")
        for index, source in enumerate(found, 1):
            marker = " (selected)" if index == 1 and not args.all_sources else ""
            print(f"  {index}. {source}{marker}")
        if not args.all_sources:
            print("Use --all-sources to merge them, or --source to choose explicitly.")

    return found if args.all_sources else [found[0]]


def _run_build(args: argparse.Namespace) -> int:
    try:
        sources = _resolve_sources(args)
        print("Source: " + ", ".join(str(source) for source in sources))
        index = build(
            sources,
            args.output,
            show_tools=not args.no_tools,
            full_results=args.full_results,
            by_activity=args.by_activity,
            use_utc=args.utc,
            no_subagents=args.no_subagents,
            incremental=args.incremental,
            show_thinking=not args.no_thinking,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Built: {index}")
    if args.open_browser and not open_viewer(index):
        print(f"Open manually: {index.resolve()}")
    return 0


def _run_export(args: argparse.Namespace) -> int:
    try:
        result = export_conversation(args.query, args.format, args.from_dir, args.output)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if result:
        print(f"Exported: {result}")
    return 0


def _run_serve(args: argparse.Namespace) -> int:
    try:
        serve_backup(
            args.output,
            host=args.host,
            port=args.port,
            open_browser=args.open_browser,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "export":
        return _run_export(args)
    if args.command == "serve":
        return _run_serve(args)
    return _run_build(args)


if __name__ == "__main__":
    raise SystemExit(main())
