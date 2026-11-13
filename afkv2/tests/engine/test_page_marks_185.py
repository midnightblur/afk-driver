"""The page marks of ticket 185 (PRD AC-046 to AC-049, SDD §14 rows "engine page, kit stylesheet, base card" and
"engine diagrams"): the changed-this-round mark after a title, round chips that fade by round age, the heading first
in each card body, and the export of a diagram picture into an artifact. Every renderer is an in-process stub."""

import json
import re
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
for folder in (PLUGIN / "scripts", ENGINE_DIR, Path(__file__).resolve().parent):
    sys.path.insert(0, str(folder))

import diagrams  # noqa: E402
import engine  # noqa: E402
from shell import page  # noqa: E402
from test_diagram_text import FLOW, StubRenderer  # noqa: E402
from test_page_parts_v2 import document  # noqa: E402

# The marks of the page HTML, each on a line of its own (plugin_check: a marker is never matched by part).
CHANGED = '<span class="afkv2-changed">Changed this round</span>'
MARK_CLASS = "afkv2-changed"
CARD_TITLE = 'class="afkv2-card-title"'
HISTORY = 'class="afkv2-history"'
FRESH_2 = 'data-afkv2-fresh="2"'
CHIP_CLASS = "afkv2-round-chip"
CHIP = re.compile(r'<span class="' + CHIP_CLASS + r'(?: [\w-]+)?" style="--afkv2-round: [^;"]+(?:; opacity: ([0-9.]+))?" '
                  r'title="Round (\d+)">')
CARD_OPEN = re.compile(r'<article class="afkv2-card[^"]*" id="([^"]+)"[^>]*>')
CARD_BODY = '<div class="afkv2-card-body"><h4 class="afkv2-h">'
CARD_BODY_CLASS = "afkv2-card-body"
CARD_BODY_RULE = ".afkv2-card-body"
CONTENT = '<div class="afkv2-body">'
ANSWER = '<div class="afkv2-answer">'
LIGHT_THEME = 'afkv2-diagram-theme--light">'
WHITE = "background-color: #ffffff"
FOLD_START = "<details>\n<summary>Mermaid source</summary>\n\n```mermaid\n"
FOLD_END = "```\n\n</details>\n"


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
    assert own.index(CARD_TITLE) < own.index(CHANGED)


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
    history = html[html.index(HISTORY):]
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
    assert FRESH_2 in element(html, "i-b") and CHANGED not in html


# --- AC-048: round chips fade by round age


def chip_strengths(html):
    """Each round number with the opacity of its chips; a chip with no opacity is fully strong."""
    found = {}
    for opacity, n in CHIP.findall(html):
        found.setdefault(int(n), set()).add(float(opacity or 1))
    return found


def test_the_current_round_chip_is_strongest_and_older_rounds_fade():
    found = chip_strengths(build(changed_document()))
    assert set(found) == {1, 2, 3}
    assert all(len(values) == 1 for values in found.values()), found
    assert found[3] == {1.0}
    assert found[3].pop() > found[2].pop() > found[1].pop()


def test_a_chip_never_fades_out_of_sight():
    doc = changed_document()
    settled = doc["rounds"][0]
    doc["rounds"] = [{**settled, "n": n, "items": [{**item, "id": f"{item['id']}-{n}"} for item in settled["items"]]}
                     for n in range(1, 8)] + [{**doc["rounds"][2], "n": 8}]
    for section in doc["sections"]:
        section["changes"] = []
    doc["notes"] = []
    found = chip_strengths(build(doc))
    assert min(value for values in found.values() for value in values) >= 0.4


# --- AC-046: each card body starts with its heading


def test_each_card_body_starts_with_its_heading():
    for doc in (changed_document(), document()):
        html = build(doc)
        assert CARD_OPEN.findall(html)
        for match in CARD_OPEN.finditer(html):
            assert html[match.end():].startswith(CARD_BODY), match.group(1)


def test_the_card_body_holds_the_content_and_not_the_mark_radios():
    html = build(changed_document())
    own = element(html, "i-closed")
    answer = own.index(ANSWER)
    start = own.index(CARD_BODY)
    assert start < own.index(CONTENT) < answer
    before_answer = own[start:answer]
    assert before_answer.count("<div") == before_answer.count("</div>"), "the card body closes before the radios"


def test_the_page_scripts_and_styles_find_the_heading_inside_the_card_body():
    shell = ENGINE_DIR / "shell"
    for script in ("tips.js", "runtime.js"):
        assert CARD_BODY_CLASS in (shell / script).read_text("utf-8"), script
    for sheet in ("tips.css", "kit.css"):
        assert CARD_BODY_RULE in (shell / sheet).read_text("utf-8"), sheet


# --- AC-049: export writes the picture the page showed into an artifact


@pytest.fixture
def renderer(monkeypatch):
    stub = StubRenderer()
    config = engine.data_folder() / diagrams.CONFIG_FILE
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("{}", "utf-8")
    monkeypatch.setattr(diagrams, "find_renderer", lambda: "mmdc")
    monkeypatch.setattr(diagrams, "call_renderer", stub)
    return stub


def light_picture_on_page(text):
    """The SVG of the light theme that the page shows for this diagram text, with its id."""
    html = diagrams.diagram_picture(text, "d-flow")
    start = html.index(LIGHT_THEME) + len(LIGHT_THEME)
    return html[start:html.index("</svg>", start) + len("</svg>")]


def test_export_writes_the_light_picture_of_the_page_on_white(renderer, tmp_path):
    shown = light_picture_on_page(FLOW)
    dest = tmp_path / "pictures" / "d-flow.svg"
    diagrams.export(FLOW, dest)
    written = dest.read_text("utf-8")
    assert WHITE in written[:written.index(">")]
    assert written.replace(f' style="{WHITE}"', "") == shown.replace("d-flow--light", "d-flow")


def test_export_reuses_the_picture_the_page_rendered(renderer, tmp_path):
    light_picture_on_page(FLOW)
    calls = len(renderer.calls)
    diagrams.export(FLOW, tmp_path / "d-flow.svg")
    assert len(renderer.calls) == calls


def test_export_answers_the_picture_with_its_mermaid_source_in_a_fold_below_it(renderer, tmp_path):
    artifact = tmp_path / "SDD.md"
    markdown = diagrams.export(FLOW, tmp_path / "pictures" / "d-flow.svg", artifact)
    assert markdown.startswith("![d-flow](pictures/d-flow.svg)\n")
    fold = markdown[markdown.index("<details>"):]
    assert fold.startswith(FOLD_START) and FLOW in fold and fold.endswith(FOLD_END)


def test_export_with_no_renderer_refuses_and_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(diagrams, "find_renderer", lambda: None)
    dest = tmp_path / "d-flow.svg"
    with pytest.raises(diagrams.Refusal) as refused:
        diagrams.export(FLOW, dest)
    assert refused.value.code == "no-picture" and "/afkv2:setup" in refused.value.reason
    assert not dest.exists()


def test_the_engine_export_verb_writes_the_picture_and_answers_the_markdown(renderer, tmp_path, capsys):
    source = tmp_path / "flow.mmd"
    source.write_text(FLOW, "utf-8")
    dest = tmp_path / "pictures" / "d-flow.svg"
    code = engine.main(["export", str(source), "--dest", str(dest), "--artifact", str(tmp_path / "PRD.md")])
    answer = json.loads(capsys.readouterr().out)
    assert code == 0 and answer["ok"] is True
    assert answer["path"] == str(dest) and dest.is_file()
    assert answer["markdown"].startswith("![d-flow](pictures/d-flow.svg)")


def test_export_paints_white_over_a_transparent_background_the_renderer_set(renderer, tmp_path, monkeypatch):
    renderer_svg = '<svg id="{}" style="max-width: 10px; background-color: transparent;"><g></g></svg>'

    def transparent(argv, timeout):
        value = dict(zip(argv[1::2], argv[2::2]))
        Path(value["-o"]).write_text(renderer_svg.format(value["-I"]), "utf-8")
        return 0, ""

    monkeypatch.setattr(diagrams, "call_renderer", transparent)
    dest = tmp_path / "d-flow.svg"
    diagrams.export(FLOW, dest)
    style = re.search(r'^<svg[^>]*style="([^"]*)"', dest.read_text("utf-8")).group(1)
    assert "transparent" not in style and style.rstrip("; ").endswith(WHITE)


def test_export_of_a_text_file_with_a_last_newline_reuses_the_page_picture(renderer, tmp_path):
    light_picture_on_page(FLOW)
    calls = len(renderer.calls)
    diagrams.export(FLOW + "\n", tmp_path / "d-flow.svg")
    assert len(renderer.calls) == calls


# --- the changed edge stays where no words mark the change (a version 0 or 1 page, any other element)

FRESH_RULE = re.compile(r"^(\[data-afkv2-fresh\][^{]*)\{[^}]*box-shadow", re.M)
WORDS_MARK = ":not(:has(.afkv2-changed))"


def test_the_changed_edge_skips_only_an_element_that_shows_the_words():
    css = (ENGINE_DIR / "shell" / "kit.css").read_text("utf-8")
    selectors = [match.strip() for match in FRESH_RULE.findall(css)]
    assert selectors == ["[data-afkv2-fresh]" + WORDS_MARK]


# --- review round 1: the card takes no raw HTML, export answers every failure as a refusal


def test_a_card_takes_a_changed_flag_and_no_raw_html():
    import registry
    props = {"item": {"id": "i-x", "kind": "info", "title": "X", "body": {"type": "text", "props": {"text": "x"}}},
             "round": 1, "colour": "#fff", "current": True}
    assert registry.validate({"type": "card", "props": {**props, "mark": "<img src=x>"}}) != []
    html = registry.render_component({"type": "card", "props": {**props, "changed": True},
                                      "children": [props["item"]["body"]]})
    assert CHANGED in html


def test_export_to_a_folder_refuses_unwritable(renderer, tmp_path):
    with pytest.raises(diagrams.Refusal) as refused:
        diagrams.export(FLOW, tmp_path)
    assert refused.value.code == "unwritable"


def test_export_refuses_a_link_it_cannot_make_relative(renderer, tmp_path, monkeypatch):
    def no_relative(*_):
        raise ValueError("path is on mount 'C:', start on mount 'D:'")

    monkeypatch.setattr(diagrams.os.path, "relpath", no_relative)
    with pytest.raises(diagrams.Refusal) as refused:
        diagrams.export(FLOW, tmp_path / "d.svg", "D:/spec/SDD.md")
    assert refused.value.code == "usage"


def test_the_nav_label_leaves_out_the_changed_words():
    script = (ENGINE_DIR / "shell" / "tips.js").read_text("utf-8")
    label = script[script.index("var MARK = '." + MARK_CLASS + "';"):]
    assert "querySelector(MARK).remove()" in label[:label.index("\n    }\n")]
