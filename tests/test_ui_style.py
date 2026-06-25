from __future__ import annotations

from importlib import resources


def read_style() -> str:
    return resources.files("claude_history").joinpath("assets/style.css").read_text(
        encoding="utf-8"
    )


def test_stylesheet_uses_flat_shadcn_like_surfaces():
    css = read_style()

    assert "linear-gradient" not in css
    assert "--shadow-soft" not in css
    assert "--pink-soft" not in css
    assert "--pink-tint" not in css


def test_stylesheet_uses_slate_accent_instead_of_bright_blue():
    css = read_style()

    assert "--accent: #334155;" in css
    assert "--accent-2: #0f172a;" in css
    assert "--accent-soft: #f1f5f9;" in css
    for old_blue in ["#2563eb", "#1d4ed8", "#eff6ff", "#bfdbfe", "#93c5fd"]:
        assert old_blue not in css


def test_prompt_map_is_lightweight_outline_navigation():
    css = read_style()

    assert ".prompt-item.is-active" in css
    assert "box-shadow: inset 3px 0 0" not in css
    assert "border-left: 2px solid var(--accent)" in css
