<div align="center">

# 📜 Claude Code History

**Export and browse your Claude Code conversation history — fully offline.**

`claude-history` reads Claude Code's raw `.jsonl` session files, turns them into a
clean local archive, and generates a modern static viewer for searching and
reviewing past sessions.

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20WSL%20%7C%20Linux%20%7C%20macOS-4c8bf5)](#-source-discovery)
[![Offline](https://img.shields.io/badge/Offline-No%20CDN%20required-2ea44f)](#-what-it-produces)

</div>

---

## ✨ Why this exists

Every Claude Code session is quietly saved on your machine as a raw `.jsonl`
file. Those files are hard to read, scattered across platforms, and offer no way
to search, review, or get statistics. `claude-history` bridges that gap with
three guiding principles:

| Principle | What it means |
| :-- | :-- |
| 🔒 **Private & offline** | Reads local files, writes local HTML/Markdown. No CDN, no telemetry, no required server — your conversations never leave your machine. |
| 👀 **Human-readable** | Raw JSONL becomes a clean web archive, grouped by project, with prompts, slash commands, and Claude's replies clearly distinguished. |
| 📈 **Built for scale** | Years of history stay fast: conversation pages are pre-rendered, the index embeds only metadata, project groups render lazily, and incremental rebuilds skip unchanged sessions. |

---

## 📦 Table of Contents

- [What It Produces](#-what-it-produces)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [CLI Reference](#-cli-reference)
- [Serve Mode](#-serve-mode)
- [Export a Single Conversation](#-export-a-single-conversation)
- [Source Discovery](#-source-discovery)
- [Output Layout](#-output-layout)
- [What Gets Exported](#-what-gets-exported)
- [Development](#-development)
- [Notes](#-notes)
- [License](#-license)

---

## 🗂️ What It Produces

| Output | Description |
| :-- | :-- |
| `index.html` | Offline viewer grouped by project, with search and statistics. |
| `conversations/*.html` | One pre-rendered HTML page per conversation. |
| `conversations/*.json` | Normalized machine-readable copy of each conversation. |
| `markdown/*.md` | One clean Markdown file per conversation. |
| `manifest.json` | Aggregated stats: per-project totals, activity heatmap, top tools/models, and the sub-agent graph. |
| `assets/style.css` | Local CSS — no CDN required. |

> [!NOTE]
> The viewer is designed for large histories. Conversation pages are
> pre-rendered, the index embeds only metadata, project groups render lazily,
> and the sidebar is sorted newest-first.

---

## 🚀 Installation

> [!TIP]
> `pipx` is the recommended way to install on **any** platform — it isolates the
> tool in its own environment and puts `claude-history` on your `PATH`. Plain
> `pip` works too if you prefer.

### 🐧 Linux / Ubuntu / WSL / macOS

```bash
pipx install .
```

If your shell cannot find the command afterwards:

```bash
pipx ensurepath
```

Then restart the terminal.

> If you don't have `pipx`, install it first with
> `python3 -m pip install --user pipx`, or just use `python3 -m pip install .`.

### 🪟 Windows

From PowerShell or CMD:

```powershell
pipx install .
```

Or, without `pipx`:

```powershell
python -m pip install .
```

If `claude-history` is not on `PATH`, add Python's `Scripts` directory. Common
locations include:

```text
%APPDATA%\Python\Python3x\Scripts
<venv>\Scripts
```

### 🧑‍💻 Development install (all platforms)

Installs the package in editable mode together with the test dependencies:

```bash
python -m pip install -e ".[dev]"
```

---

## ⚡ Quick Start

Build the default export into `./claude_history_export` and open the viewer:

```bash
claude-history
```

| Goal | Command |
| :-- | :-- |
| Build without opening a browser | `claude-history --no-open` |
| Use a specific projects directory | `claude-history --source <path> -o <output-dir>` |
| Merge all discovered sources | `claude-history --all-sources` |
| Re-render only what changed | `claude-history --incremental` |

> [!TIP]
> Run `claude-history -h` at any time to see the full help.

---

## 🛠️ CLI Reference

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
| `--open` / `--no-open` | Open the viewer after build. Enabled by default. |

---

## 🌐 Serve Mode

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

> [!NOTE]
> **Trade-off:** `file://` is the simplest option and works offline with no
> server. `serve` is more stable for large exports and browser-security edge
> cases.

---

## 📤 Export a Single Conversation

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

## 🔍 Source Discovery

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

## 📁 Output Layout

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

On a full rebuild, the tool **only owns and replaces** `conversations/`,
`markdown/`, `assets/`, `index.html`, `manifest.json`, and
`.claude-history-cache.json`. Any other files you place in the output directory
are preserved.

> [!IMPORTANT]
> Generated output should normally not be committed. The default
> `claude_history_export/` directory is ignored by `.gitignore`.

---

## 📥 What Gets Exported

`claude-history` exports Claude Code history from `.jsonl` files under Claude
Code's `projects` directory — and nothing else.

- It does **not** export chat sessions from other tools or products. A
  Codex/OpenAI chat, for example, is not stored in `.claude/projects`, so it
  cannot appear here.
- If an **active** session does not show up yet, finish or close it and rebuild.
  The `.jsonl` file may not be fully flushed until the session ends.

---

## 🧑‍💻 Development

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

## 📝 Notes

- All file I/O uses UTF-8 with replacement for malformed input.
- Broken `.jsonl` lines are skipped instead of crashing the build.
- Output filenames are slugged to avoid Windows-forbidden characters.
- HTML assets are local and offline-friendly.

---

## 📄 License

No license file is currently included. Add a `LICENSE` file (and a `license`
field in `pyproject.toml`) to declare usage terms.

<div align="center"><sub>Built for everyone who wants to keep — and actually read — their Claude Code history.</sub></div>
