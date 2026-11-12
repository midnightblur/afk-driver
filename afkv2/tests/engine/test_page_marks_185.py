"""The page marks of ticket 185 (PRD AC-046 to AC-049, SDD §14 rows "engine page, kit stylesheet, base card" and
"engine diagrams"): the changed-this-round mark after a title, round chips that fade by round age, the heading first
in each card body, and the export of a diagram picture into an artifact. Every renderer is an in-process stub."""

import re
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
for folder in (PLUGIN / "scripts", ENGINE_DIR, Path(__file__).resolve().parent):
    sys.path.insert(0, str(folder))

import engine  # noqa: E402
from shell import page  # noqa: E402
from test_page_parts_v2 import document  # noqa: E402

CHANGED = '<span class="afkv2-changed">Changed this round</span>'
TITLE_END = re.compile(r'<(h4|h3) class="afkv2-(?:h|v2-h)">')


def build(doc):
    return page.build(engine.READERS[doc["schema"]](doc))


def element(html, element_id):
    """The HTML of the article with this id, up to its first closing tag."""
    start = html.index(f'id="{element_id}"')
    return html[start:html.index("</article>", start)]


def heading(html, element_id):
    own = element(html, element_id)
    end = own.index("</h4>") if "</h4>" in own else own.index("</h3>")
    return own[:end]


def changed_document():
    """Round 3 is current: it changed the card i-format; the sections sec-scope and sec-format have a change line of
    round 3."""
    doc = document()
    doc["rounds"][2]["changed"] = ["i-format"]
    return doc


# --- AC-047: the changed mark


def test_a_card_changed_in_the_current_round_shows_the_mark_after_its_title():
    html = build(changed_document())
    own = heading(html, "i-format")
    assert CHANGED in own
    assert own.index('class="afkv2-card-title"') < own.index(CHANGED)


def test_a_card_the_current_round_did_not_change_shows_no_mark():
    html = build(changed_document())
    assert CHANGED not in element(html, "i-closed")


def test_a_section_with_a_change_line_of_the_current_round_shows_the_mark_after_its_title():
    html = build(changed_document())
    for section in ("sec-scope", "sec-format"):
        own = heading(html, section)
        assert CHANGED in own, section


def test_a_section_the_current_round_did_not_change_shows_no_mark():
    html = build(changed_document())
    for section in ("sec-old", "sec-gone", "sec-later"):
        assert CHANGED not in element(html, section), section


def test_round_1_shows_no_changed_mark():
    doc = changed_document()
    doc["rounds"] = [{**doc["rounds"][0], "state": "current", "changed": ["i-scope"]}]
    for section in doc["sections"]:
        section["changes"] = [line for line in section["changes"] if line["round"] == 1]
    assert CHANGED not in build(doc)


def test_a_card_in_a_history_shows_no_changed_mark():
    doc = changed_document()
    doc["rounds"][2]["items"][0]["carries"] = ["i-scope"]
    html = build(doc)
    history = html[html.index('class="afkv2-history"'):]
    assert CHANGED not in history[:history.index("</details>")]


def test_a_version_1_page_keeps_its_visible_text_and_shows_no_mark():
    """Version 0 and 1 pages keep the layout and the visible text they had before version 2 (ADR-0003 design);
    every new page is version 2."""
    doc = {"schema": "afkv2.page/1",
           "session": {"id": "s1", "skill": "grill", "feature": "export", "started": "2026-01-05T09:00:00Z"},
           "maps": [], "notes": [],
           "rounds": [{"n": 1, "state": "settled", "banner": {"settled": [], "unlocks": [], "parked": []},
                       "items": [{"id": "i-a", "kind": "info", "title": "First",
                                  "body": {"type": "text", "props": {"text": "a"}}}]},
                      {"n": 2, "state": "current", "changed": ["i-b"],
                       "banner": {"settled": [], "unlocks": [], "parked": []},
                       "items": [{"id": "i-b", "kind": "confirm", "title": "Second",
                                  "body": {"type": "text", "props": {"text": "b"}}},
                                 {"id": "i-c", "kind": "confirm", "title": "Third",
                                  "body": {"type": "text", "props": {"text": "c"}}}]}]}
    html = build(doc)
    assert 'data-afkv2-fresh="2"' in element(html, "i-b") and CHANGED not in html
