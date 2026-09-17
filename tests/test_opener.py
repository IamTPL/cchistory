from __future__ import annotations

from claude_history import opener


def test_open_viewer_passes_a_well_formed_file_uri(tmp_path, monkeypatch):
    index = tmp_path / "Tài liệu test" / "index.html"
    index.parent.mkdir(parents=True)
    index.write_text("<html></html>", encoding="utf-8")

    seen: list[str] = []
    monkeypatch.setattr(opener, "is_wsl", lambda: False)
    monkeypatch.setattr(opener.webbrowser, "open", lambda url: seen.append(url) or True)

    assert opener.open_viewer(index) is True
    url = seen[0]
    assert url == index.resolve().as_uri()
    assert url.startswith("file:///")
    assert " " not in url
