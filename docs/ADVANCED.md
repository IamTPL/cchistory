# Advanced usage

Everything beyond the one-command path in the [README](../README.md).

- [Troubleshooting](#troubleshooting)
- [Other ways to install](#other-ways-to-install)
- [CLI reference](#cli-reference)
- [Serve mode](#serve-mode)
- [Export a single conversation](#export-a-single-conversation)
- [Source discovery](#source-discovery)
- [Output layout](#output-layout)
- [What gets exported](#what-gets-exported)
- [Development](#development)
- [Notes](#notes)

---

## Troubleshooting

### `claude-history: command not found`

`pipx` installed the tool but your shell can't see it yet. Run:

```bash
pipx ensurepath
```

Then close the terminal and open a new one.

On Windows, if you installed with plain `pip` instead of `pipx`, add Python's
`Scripts` directory to your `PATH`. Common locations:

```text
%APPDATA%\Python\Python3x\Scripts
<venv>\Scripts
```

### `pipx: command not found`

Install it first:

```bash
python3 -m pip install --user pipx
```

### The page is built but a session is missing

If an **active** session doesn't show up, finish or close it and rebuild. Claude
Code may not flush the session file to disk until the session ends.

### The browser didn't open

The build still succeeded. Open `claude_history_export/index.html` manually, or
use [serve mode](#serve-mode).

---

## Other ways to install

`pipx` is recommended because it isolates the tool in its own environment and
puts `claude-history` on your `PATH`. These alternatives also work.

> On Windows, use `python` wherever these commands say `python3`.

### Plain pip

```bash
python3 -m pip install .
```

### Editable install, for working on the code

Installs the package in editable mode together with the test dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

### Running from source without installing

```bash
PYTHONPATH=src python3 -m claude_history.cli
```

---

## CLI reference

```bash
claude-history [options]
```

| Option | Description |
| :-- | :-- |
| `--source <path>` | Use a specific Claude Code `projects` directory. Can be passed more than once. |
| `--all-sources` | Use every discovered source instead of only the first one. |
| `-o, --output <path>` | Output directory. Defaults to `./claude_history_export`. |
| `--by-activity` | Sort by last activity instead of conversation start time. |
| `--no-tools` | Hide tool-call details in the export. |
| `--no-thinking` | Hide Claude's thinking blocks in the export. |
| `--full-results` | Keep full tool results instead of compact previews. |
| `--incremental` | Re-render only changed conversations when possible. |
| `--utc` | Render timestamps in UTC instead of local time. |
| `--no-subagents` | Exclude sidechain / sub-agent sessions from the index. |
| `--open` / `--no-open` | Open the viewer after build. Enabled by default; `--no-open` is useful in scripts and CI. |

Run `claude-history -h` for the full help.

---

## Serve mode

The viewer works directly from `index.html` over `file://`. For very large
exports, or if your browser is finicky with local files, run the bundled local
server instead:

```bash
claude-history serve
```

| Option | Default | Description |
| :-- | :-- | :-- |
| `-o, --output <path>` | `claude_history_export` | Directory to serve. |
| `--host <host>` | `127.0.0.1` | Bind address. |
| `--port <port>` | `8765` | Bind port. |
| `--open` / `--no-open` | open | Open the browser after starting. |

**Trade-off:** `file://` is the simplest option and works offline with no
server. `serve` is more stable for large exports and browser-security edge
cases.

---

## Export a single conversation

Pull one conversation out of an existing build as Markdown or JSON — handy for
sharing or piping into other tools:

```bash
# Print the best match for a title / session-id / filename fragment
claude-history export "jwt configuration"

# As JSON, written to a file
claude-history export "jwt configuration" --format json -o jwt.json

# Read from a non-default build directory
claude-history export "jwt configuration" --from <output-dir>
```

| Argument / Option | Description |
| :-- | :-- |
| `query` | Title, session id, or filename fragment to match. |
| `--format {md,json}` | Output format. Defaults to `md`. |
| `--from <dir>` | Build directory to read from. Defaults to `claude_history_export`. |
| `-o <file>` | Write to a file instead of printing to stdout. |

---

## Source discovery

When `--source` is not provided, `claude-history` looks for Claude Code project
history directories in this order:

1. `CLAUDE_CONFIG_DIR/projects`, if `CLAUDE_CONFIG_DIR` is set.
2. `~/.claude/projects`.
3. **On WSL:** `/mnt/c/Users/*/.claude/projects`.
4. **On Windows:** WSL home directories through `\\wsl$` and `\\wsl.localhost`.

If multiple sources are found, the first one is used by default and the CLI
prints the discovered list. Use `--all-sources` to merge them, or `--source` to
choose explicitly.

---

## Output layout

```text
claude_history_export/
├── conversations/
│   ├── *.html                  # pre-rendered conversation pages
│   └── *.json                  # normalized conversation data
├── markdown/
│   └── *.md                    # one Markdown file per conversation
├── assets/
│   └── style.css               # local, offline-friendly CSS
├── index.html                  # offline viewer
├── manifest.json               # aggregated stats + sub-agent graph
└── .claude-history-cache.json  # incremental-rebuild cache
```

| Output | Description |
| :-- | :-- |
| `index.html` | Offline viewer grouped by project, with search and statistics. |
| `conversations/*.html` | One pre-rendered HTML page per conversation. |
| `conversations/*.json` | Normalized machine-readable copy of each conversation. |
| `markdown/*.md` | One clean Markdown file per conversation. |
| `manifest.json` | Aggregated stats: per-project totals, activity heatmap, top tools/models, and the sub-agent graph. |
| `assets/style.css` | Local CSS — no CDN required. |

On a full rebuild, the tool **only owns and replaces** `conversations/`,
`markdown/`, `assets/`, `index.html`, `manifest.json`, and
`.claude-history-cache.json`. Any other files you place in the output directory
are preserved.

> [!IMPORTANT]
> Generated output should normally not be committed. The default
> `claude_history_export/` directory is ignored by `.gitignore`.

The viewer is designed for large histories: conversation pages are pre-rendered,
the index embeds only metadata, project groups render lazily, and the sidebar is
sorted newest-first.

---

## What gets exported

`claude-history` exports Claude Code history from `.jsonl` files under Claude
Code's `projects` directory — and nothing else.

- It does **not** export chat sessions from other tools or products. A
  Codex/OpenAI chat, for example, is not stored in `.claude/projects`, so it
  cannot appear here.
- If an **active** session does not show up yet, finish or close it and rebuild.
  The `.jsonl` file may not be fully flushed until the session ends.

---

## Development

Install development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run the test suite:

```bash
python -m pytest
```

Build a wheel without dependencies:

```bash
python -m pip wheel --no-deps -w dist .
```

### Naming conventions

| Item | Value |
| :-- | :-- |
| Python distribution | `claude-code-history` |
| Python package | `claude_history` |
| CLI command | `claude-history` |
| Default output directory | `claude_history_export/` |

> The source package intentionally does not share a name with the generated
> output directory, so `.gitignore` can ignore exports without hiding source
> files.

---

## Notes

- All file I/O uses UTF-8 with replacement for malformed input.
- Broken `.jsonl` lines are skipped instead of crashing the build.
- Output filenames are slugged to avoid Windows-forbidden characters.
- HTML assets are local and offline-friendly.
- Data embedded in `index.html` is escaped so conversation text containing
  `<script` or `<!--` cannot break the page.
