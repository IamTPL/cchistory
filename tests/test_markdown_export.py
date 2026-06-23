from __future__ import annotations

from claude_backup.markdown_export import md_to_html


def test_md_to_html_wraps_tables_for_viewer_overflow():
    html = md_to_html(
        "| Column A | Column B |\n"
        "| --- | --- |\n"
        "| long text | more long text |\n"
    )

    assert '<div class="table-wrap"><table>' in html
    assert "</table></div>" in html

