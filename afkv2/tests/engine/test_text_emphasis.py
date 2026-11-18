"""The emphasis marks of a `markdown: true` text (steer of round 5): **bold**, `code`, *italic* and ==highlight==,
one meaning each by the visualize guide. A mark never reads inside a code span or a link, and a lone star or a
glob stays text. The kit styles each mark in both themes."""

import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[2] / "engine"
sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(ENGINE_DIR.parent / "scripts"))

import registry  # noqa: E402

registry.load_components()

KIT = (ENGINE_DIR / "shell" / "kit.css").read_text(encoding="utf-8")
GUIDE = " ".join((ENGINE_DIR.parent / "skills" / "visualize" / "components" / "chip-and-text.md")
                 .read_text(encoding="utf-8").split())
SELECTORS = (".afkv2-md strong", ".afkv2-md em", ".afkv2-md code", ".afkv2-md-mark")
MARK = '<mark class="afkv2-md-mark">{}</mark>'


def md(text):
    return registry.render_component({"type": "text", "props": {"text": text, "markdown": True}})


def test_each_mark_renders_its_own_tag():
    html = md("**Decided** in `Job.java`, *inferred*, ==new==")
    assert "<strong>Decided</strong> in <code>Job.java</code>, <em>inferred</em>, " + MARK.format("new") in html


@pytest.mark.parametrize("text", ["a * b * c", "2*3*4", "the glob src/*.py and *.java", "* a list star *",
                                  "x == y == z", "== spaced =="])
def test_a_lone_star_a_glob_or_a_spaced_pair_stays_text(text):
    html = md(text)
    assert "<em>" not in html and "<mark" not in html


def test_no_mark_reads_inside_a_code_span():
    assert "<code>a*b*c ==d==</code>" in md("`a*b*c ==d==`")


def test_no_mark_reads_inside_a_link():
    html = md("see https://x.example/a==b==/*c* and [the page](https://y.example/*p*) then *ok*")
    assert 'href="https://x.example/a==b==/*c*"' in html and 'href="https://y.example/*p*"' in html
    assert html.count("<em>") == 1 and "<mark" not in html


def test_marks_nest_inside_bold_and_list_items():
    assert "<strong>bold <em>nested</em> ok</strong>" in md("**bold *nested* ok**")
    assert "<li><em>item</em> " + MARK.format("one") + "</li>" in md("- *item* ==one==")


def test_a_plain_text_shows_its_stars_as_they_are():
    html = registry.render_component({"type": "text", "props": {"text": "*not* ==marked=="}})
    assert "<p>*not* ==marked==</p>" in html


def test_the_kit_styles_each_mark_from_theme_tokens():
    for selector in SELECTORS:
        start = KIT.index(selector + " {")
        rule = KIT[start:KIT.index("}", start)]
        assert "var(--" in rule, selector


def test_the_guide_gives_each_mark_one_meaning():
    for mark in ("`**bold**`", "`` `code` ``", "`*italic*`", "`==highlight==`"):
        assert mark in GUIDE, mark
