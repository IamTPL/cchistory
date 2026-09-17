from __future__ import annotations

import json
import re

from claude_history.html_export import render_index_page

HOSTILE = [
    {"t": "comment marker <!-- in a prompt", "p": "/tmp/a"},
    {"t": "nested <script>alert(1)</script> tag", "p": "/tmp/b"},
    {"t": "closing </script> on its own", "p": "/tmp/c"},
]


def extract_data(page: str) -> list[dict[str, str]]:
    match = re.search(r"const DATA = (.*?);\n", page, re.S)
    assert match, "DATA assignment not found"
    return json.loads(match.group(1).replace("\\u003c", "<").replace("\\u003e", ">"))


def test_index_payload_never_emits_raw_angle_brackets():
    page = render_index_page(HOSTILE, {"note": "<script><!--"})

    payload = page.split("const DATA = ", 1)[1].split(";\n", 1)[0]
    assert "<" not in payload
    assert ">" not in payload


def test_index_script_element_is_not_swallowed_by_payload():
    page = render_index_page(HOSTILE)

    assert page.count("<script") == page.count("</script>")


def test_index_payload_round_trips_hostile_titles():
    page = render_index_page(HOSTILE)

    assert extract_data(page) == HOSTILE
