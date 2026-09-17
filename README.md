<div align="center">

# 📜 Claude Code History

**Turn your Claude Code chat history into a searchable web page on your own computer.**

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Offline](https://img.shields.io/badge/Offline-Nothing%20is%20uploaded-2ea44f)](#what-it-does)

</div>

---

## What it does

Claude Code quietly saves every session on your computer in a raw format that is
almost impossible to read. This tool collects all of them into one local web page
you can search and browse.

Nothing is uploaded. Nothing leaves your computer.

---

## Install it

You need [Python](https://www.python.org/downloads/) and
[pipx](https://pipx.pypa.io/stable/installation/).

Open a terminal in this folder and run:

```bash
pipx install .
```

---

## Use it

```bash
claude-history
```

That's it. It finds your history, builds the page, and opens it in your browser.

Run the same command again whenever you want to include new conversations.

---

## Or let Claude Code do it

Copy this into Claude Code while you're in this folder:

> Install this project with pipx, then run `claude-history` to build and open my
> Claude Code history.

---

## Opening it again later

The page is saved at `claude_history_export/index.html`. Open that file any time
to read your history again — no need to rebuild.

---

## Need more?

Every command-line option, the built-in web server, exporting a single
conversation, the output layout, and developer setup all live in
**[docs/ADVANCED.md](docs/ADVANCED.md)**.

Something not working? Start with
**[Troubleshooting](docs/ADVANCED.md#troubleshooting)**.

---

## License

No license file is included yet.

<div align="center"><sub>Built for everyone who wants to keep — and actually read — their Claude Code history.</sub></div>
