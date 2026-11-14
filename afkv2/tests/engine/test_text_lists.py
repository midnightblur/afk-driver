"""A `markdown: true` text nests a list by indent; the kit styles the nested list in both themes."""

import re
import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[2] / "engine"
sys.path.insert(0, str(ENGINE_DIR))

import registry  # noqa: E402

KIT = (ENGINE_DIR / "shell" / "kit.css").read_text(encoding="utf-8")


def md(text):
    return registry.render_component({"type": "text", "props": {"text": text, "markdown": True}})


def test_a_line_indented_2_spaces_nests_under_the_point_above():
    html = md("- Menu\n- 2 job types:\n  - Export\n  - Archive\n    - Daily\n- Orders only")
    assert ("<ul><li>Menu</li><li>2 job types:<ul><li>Export</li><li>Archive<ul><li>Daily</li></ul></li></ul></li>"
            "<li>Orders only</li></ul>") in html


@pytest.mark.parametrize("text, flat", [
    ("- a\n- b", "<ul><li>a</li><li>b</li></ul>"),
    ("  - a\n  - b", "<ul><li>a</li><li>b</li></ul>"),
    ("- a\n  more words\n- b", "<ul><li>a more words</li><li>b</li></ul>"),
    ("- a\n - b", "<ul><li>a</li><li>b</li></ul>"),
])
def test_a_list_indented_as_a_whole_or_by_1_space_stays_flat(text, flat):
    assert flat in md(text)


def test_a_dedent_closes_each_open_level():
    html = md("- a\n  - b\n    - c\n- d")
    assert "<ul><li>a<ul><li>b<ul><li>c</li></ul></li></ul></li><li>d</li></ul>" in html
    assert html.count("<ul>") == html.count("</ul>") == 3
    assert html.count("<li>") == html.count("</li>") == 4


def test_a_nested_point_keeps_the_inline_subset_and_escapes_html():
    html = md("- top\n  - **bold** `<b>` text")
    assert "<li><strong>bold</strong> <code>&lt;b&gt;</code> text</li>" in html


def test_the_kit_indents_a_nested_list():
    assert re.search(r"\.afkv2-md li > ul \{[^}]*padding-left: 1\.2rem", KIT)
