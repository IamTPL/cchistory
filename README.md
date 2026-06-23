# Claude Code History

`claude-history` is a Python CLI for exporting and browsing Claude Code
conversation history offline.

It reads Claude Code `.jsonl` history files, creates a clean local export, and
generates a modern static viewer for searching and reviewing past sessions.

## What It Produces

- `markdown/*.md`: one Markdown file per conversation.
- `conversations/*.html`: one pre-rendered HTML page per conversation.
- `index.html`: an offline viewer grouped by project.
- `assets/style.css`: local CSS, no CDN required.

The viewer is built for large histories: conversation pages are pre-rendered,
the index embeds only metadata, project groups render lazily, and sidebar
sorting is newest-first.

## Features

- Cross-platform support: Windows, WSL, Ubuntu, and macOS.
- Automatic Claude Code source discovery.
- Clean rebuild by default to avoid stale/orphaned output.
- Optional incremental rebuilds for large histories.
- Project grouping from the recorded `cwd` field, with folder-name fallback.
- Modern 30/70 sidebar/content layout.
- Distinct styling for user prompts, commands, and Claude responses.
- Safe Markdown table rendering with overflow handling.
- Local `serve` command for a more robust browser experience than `file://`.

## Naming

- Python distribution: `claude-code-history`
- Python package: `claude_history`
- CLI command: `claude-history`
- Default output directory: `claude_history_export/`

The source package intentionally does not share a name with the generated output
directory, so `.gitignore` can ignore exports without hiding source files.

## Installation

### Recommended: pipx

```bash
pipx install .
```

If your shell cannot find the command afterwards:

```bash
pipx ensurepath
```

Then restart the terminal.

### Windows

From PowerShell or CMD:

```powershell
python -m pip install .
```

If `claude-history` is not on `PATH`, add Python's `Scripts` directory. Common
locations include:

```text
%APPDATA%\Python\Python3x\Scripts
<venv>\Scripts
```

### Development Install

```bash
python -m pip install -e ".[dev]"
```

## Quick Start

Build the default export into `./claude_history_export` and open the viewer:

```bash
claude-history
```

Build without opening a browser:

```bash
claude-history --no-open
```

Use an explicit Claude Code `projects` directory:

```bash
claude-history --source <path-to-.claude/projects> -o <output-dir>
```

Merge all discovered sources:

```bash
claude-history --all-sources
```

## CLI Options

```bash
claude-history [options]
```

Common options:

- `--source <path>`: Use a specific Claude Code `projects` directory. Can be passed more than once.
- `--all-sources`: Use every discovered source instead of only the first one.
- `-o, --output <path>`: Output directory. Defaults to `./claude_history_export`.
- `--by-activity`: Sort by last activity instead of conversation start time.
- `--no-tools`: Hide tool call details in the export.
- `--full-results`: Keep full tool results instead of compact previews.
- `--incremental`: Re-render only changed conversations when possible.
- `--utc`: Render timestamps in UTC instead of local time.
- `--no-subagents`: Exclude sidechain/sub-agent sessions from the index.
- `--open`: Open the viewer after build. Enabled by default.
- `--no-open`: Do not open the viewer after build.

Show the full help:

```bash
claude-history -h
```

## Serve Mode

The default viewer works directly from `index.html` using `file://`.

For very large exports, or if your browser behaves poorly with local files, use
the local server:

```bash
claude-history serve
```

Options:

```bash
claude-history serve -o <output-dir>
claude-history serve --host 127.0.0.1 --port 8000
claude-history serve --no-open
```

Trade-off:

- `file://` is the simplest option and works offline with no server.
- `serve` is more stable for large exports and browser security edge cases.

## Source Discovery

When `--source` is not provided, `claude-history` looks for Claude Code project
history directories in this order:

1. `CLAUDE_CONFIG_DIR/projects`, if `CLAUDE_CONFIG_DIR` is set.
2. `~/.claude/projects`.
3. On WSL: `/mnt/c/Users/*/.claude/projects`.
4. On Windows: WSL home directories through `\\wsl$` and `\\wsl.localhost`.

If multiple sources are found, the first one is used by default and the CLI
prints the discovered list. Use `--all-sources` to merge them, or `--source` to
choose explicitly.

## Output Layout

Default output:

```text
claude_history_export/
  conversations/
    *.html
  markdown/
    *.md
  assets/
    style.css
  index.html
  .claude-history-cache.json
```

On a full rebuild, the tool only owns and replaces:

- `conversations/`
- `markdown/`
- `assets/`
- `index.html`
- `.claude-history-cache.json`

Other files you place in the output directory are preserved.

Generated output should normally not be committed. The default
`claude_history_export/` directory is ignored by `.gitignore`.

## What Gets Exported

`claude-history` exports Claude Code history from `.jsonl` files under Claude
Code's `projects` directory.

It does not export unrelated chat sessions from other tools or products. For
example, a current Codex/OpenAI chat is not stored in Claude Code's
`.claude/projects` directory, so it cannot appear in this export.

If a Claude Code session is currently active and does not show up yet, close or
finish that session and rebuild. The `.jsonl` file may not be fully flushed
until the session ends.

## Development

Install development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run tests:

```bash
python -m pytest
```

Build a wheel without dependencies:

```bash
python -m pip wheel --no-deps -w dist .
```

## Notes

- All file I/O uses UTF-8 with replacement for malformed input.
- Broken `.jsonl` lines are skipped instead of crashing the build.
- Output filenames are slugged to avoid Windows-forbidden characters.
- HTML assets are local and offline-friendly.

