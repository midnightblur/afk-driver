"""The page parts of a version 2 page (SDD §8 row "engine: page parts", ADR-0003 design): the sections, the
questions for others, the worked examples, and the one label helper that gives every element its visible text."""

import copy
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
for folder in (PLUGIN / "scripts", ENGINE_DIR):
    sys.path.insert(0, str(folder))

import engine  # noqa: E402
from shell import parts_v2  # noqa: E402

ROUND_CODE = re.compile(r"(?<![\w-])R-?\d+(?![\w-])")
QUESTION_ATTR = 'data-afkv2-question="{}"'
WHO = re.compile(r"data-afkv2-who='([^']*)'")
FILTER = re.compile(r'<select id="afkv2-who-filter"[^>]*>(.*?)</select>', re.S)
TICK_GROUP = re.compile(r'<fieldset [^>]*data-afkv2-input="tick"[^>]*>')
TICK_ATTR = 'data-afkv2-input="tick"'
SEVERAL = 'data-afkv2-several="{}"'
EXAMPLES_HEADING = '<h2 class="afkv2-section-h">Worked examples</h2>'
TIP_ATTR = "data-afkv2-tip="
CHIP = "afkv2-chip"
CAUSE = re.compile(r'data-afkv2-cause="([^"]+)"')
V2_HEADING = "afkv2-v2-h"
CARD_TIP = 'data-afkv2-tip="Opens this card of round 3"'


def text(value, **extra):
    return {"type": "text", "props": {"text": value}, **extra}


def line(n, cause="finding", words="Wrote this part.", **extra):
    return {"round": n, "cause": cause, "text": words, **extra}


def card(card_id, section=None, settled_in=None, **extra):
    found = {"id": card_id, "kind": "confirm", "title": f"Is the {card_id[2:]} part right?",
             "body": text("Confirm the part."), **extra}
    if section:
        found["section"] = section
    if settled_in:
        found.update(state="settled_by_mark", settled={"by": "mark", "round": settled_in, "signal": "accept"})
    return found


def round_of(n, *items, state="settled"):
    return {"n": n, "state": state, "banner": {"settled": [], "unlocks": [], "parked": []}, "items": list(items)}


def note(note_id, n, owner):
    return {"id": note_id, "round": n, "target": owner, "item": owner, "text": "I cannot answer this.",
            "deleted": False}


def question(question_id, who, words, state="open", **extra):
    return {"id": question_id, "who": who, "question": words, "context": "The export writes **one** file.",
            "why": "It sets what the team builds first.", "origin": {"card": "i-scope"}, "state": state,
            "changes": [line(2, "finding", "Asked this question.")], **extra}


def document():
    """A valid version 2 page of 3 rounds: every section state, every question state, every example kind."""
    sections = [
        {"id": "sec-scope", "title": "What the export covers", "state": "current", "links": ["sec-format", "sec-old"],
         "body": text("The export writes the open rows to one file."),
         "changes": [line(1, "finding", "Wrote the first text."),
                     line(2, "note", "Added the closed rows.", notes=["N-2-sec-scope-1"]),
                     line(3, "answer_from", "Kept the file to 1 sheet.", question="q-format")]},
        {"id": "sec-format", "title": "File format", "state": "current", "body": text("A CSV file."),
         "changes": [line(1), line(3, "answer", "Chose CSV.", card="i-format")]},
        {"id": "sec-old", "title": "Old format notes", "state": "merged", "merged_into": "sec-format",
         "body": text("Notes."), "changes": [line(1), line(2, "finding", "Merged into the format part.")]},
        {"id": "sec-gone", "title": "Printing", "state": "removed", "reason": "The team dropped printing.",
         "body": text("Print the rows."), "changes": [line(1), line(2, "note", "Removed.", notes=["N-2-sec-gone-1"])]},
        {"id": "sec-later", "title": "Delivery by mail", "state": "not_reached", "body": text("The mail goes out later."),
         "changes": []},
    ]
    stories = [{"id": "st-plain", "text": "As a clerk, I export the open rows.", "changes": [line(1)]},
               {"id": "st-big", "text": "As a clerk, I export a large list.", "changes": [line(1)]}]
    examples = [
        {"id": "ex-plain", "title": "Three open rows", "kind": "frequent", "stories": ["st-plain"],
         "body": text("From 3 open rows to 1 file of 3 lines."), "changes": [line(2)]},
        {"id": "ex-big", "title": "A list of 1 million rows", "kind": "edge", "stories": ["st-big", "st-plain"],
         "body": text("From 1 million rows to 1 file."), "changes": [line(2)]},
        {"id": "ex-bad", "title": "A row with a comma", "kind": "risky", "stories": ["st-plain"],
         "body": text("A comma in a name stays in its cell."), "changes": [line(2), line(3, "finding", "Quoted cells.")]},
    ]
    questions = [
        question("q-format", ["Product owner"], "Which file format do the clerks need?", state="answered",
                 answer={"text": "CSV.", "choices": [], "role": "product owner", "date": "2026-11-05",
                         "signal": "N-3-q-format-1", "round": 3}),
        question("q-size", ["tester", "everyone"], "How many rows does a large list hold?",
                 ways=["Ask the support team", "Read the usage report"], links=["sec-scope"], waits_on="q-format",
                 example=text("A list of 1 million rows."),
                 choices={"options": [{"id": "opt-k", "text": "A thousand"}, {"id": "opt-m", "text": "A million"}],
                          "several": False}),
        question("q-cols", ["product owner"], "Which columns go in the file?", links=["sec-format", "sec-scope"],
                 choices={"options": [{"id": "opt-name", "text": "Name"}, {"id": "opt-date", "text": "Date"},
                                      {"id": "opt-sum", "text": "Sum"}], "several": True}),
        question("q-drop", ["tester"], "Does the export need a print view?", state="dropped",
                 dropped={"reason": "Printing is out of scope.", "note": "N-3-q-drop-1", "round": 3}),
        question("q-assume", ["Developer lead"], "May the file be zipped?", state="assumed",
                 assumption={"text": "The file is never zipped.", "card": "i-assume", "round": 2}),
    ]
    notes = [note("N-2-sec-scope-1", 2, "sec-scope"), note("N-2-sec-gone-1", 2, "sec-gone"),
             note("N-3-q-format-1", 3, "q-format"), note("N-3-q-drop-1", 3, "q-drop")]
    rounds = [round_of(1, card("i-scope", "sec-scope", 1)),
              round_of(2, card("i-assume", None, 2), card("i-rows", "sec-scope")),
              round_of(3, card("i-format", "sec-format", 3), card("i-closed", "sec-scope"), state="current")]
    return {"schema": "afkv2.page/2",
            "session": {"id": "s1", "skill": "grill", "feature": "export", "ticket": "PROJ-1",
                        "started": "2026-01-05T09:00:00Z", "step": "Requirements grill"},
            "maps": [], "notes": notes, "sections": sections, "stories": stories, "examples": examples,
            "questions": questions, "rounds": rounds}


class _Visible(HTMLParser):
    """The text a person sees: text outside scripts and styles. Attributes and hover text are not read."""

    def __init__(self):
        super().__init__()
        self.words, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        self.hidden += tag in ("script", "style")

    def handle_endtag(self, tag):
        self.hidden -= tag in ("script", "style")

    def handle_data(self, data):
        if not self.hidden:
            self.words.append(data)


def visible(html):
    reader = _Visible()
    reader.feed(html)
    return " ".join(" ".join(reader.words).split())


def part_of(html, element_id):
    """The article of one element."""
    start = html.index(f'<article id="{element_id}"')
    return html[start:html.index("</article>", start)]


def chip_text(html, css="afkv2-v2-open-count"):
    """The visible text of the one chip of class `css` in `html`, or None."""
    found = re.findall(rf'<span class="{CHIP} {css}">(.*?)</span>', html)
    assert len(found) <= 1, found
    return visible(found[0]) if found else None


def element_ids(doc):
    found = {entry["id"] for kind in ("sections", "stories", "examples", "questions") for entry in doc[kind]}
    found |= {option["id"] for q in doc["questions"] for option in (q.get("choices") or {}).get("options", [])}
    found |= {item["id"] for r in doc["rounds"] for item in r["items"]}
    return found | {n["id"] for n in doc["notes"]}


def test_the_fixture_passes_the_document_check(tmp_path, capsys):
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(document()), "utf-8")
    assert engine.main(["check", str(path)]) == 0, capsys.readouterr().out


# --- the label helper


def test_the_label_of_a_round_reads_round_and_its_number():
    assert parts_v2.visible_label(document(), "round", 3) == "round 3"


def test_the_label_of_an_element_is_its_title_or_words_never_its_id():
    doc = document()
    assert parts_v2.visible_label(doc, "element", "sec-format") == "File format"
    assert parts_v2.visible_label(doc, "element", "ex-big") == "A list of 1 million rows"
    assert parts_v2.visible_label(doc, "element", "q-size") == "How many rows does a large list hold?"
    assert parts_v2.visible_label(doc, "element", "st-big") == "As a clerk, I export a large list."
    assert parts_v2.visible_label(doc, "element", "i-format") == "Is the format part right?"
    assert parts_v2.visible_label(doc, "element", "opt-m") == "A million"


def test_an_element_with_no_title_or_no_entry_gets_words_not_its_id():
    doc = document()
    del doc["rounds"][2]["items"][0]["title"]
    for element in ("i-format", "x-unknown"):
        label = parts_v2.visible_label(doc, "element", element)
        assert label and element not in label


def test_the_label_of_a_cause_state_and_kind_is_a_word():
    doc = document()
    assert parts_v2.visible_label(doc, "cause", "note") == "a note"
    assert parts_v2.visible_label(doc, "cause", "finding") == "a finding of the agent"
    assert parts_v2.visible_label(doc, "state", "not_reached") == "not reached yet"
    assert parts_v2.visible_label(doc, "kind", "edge") == "edge"


@pytest.mark.parametrize("kind, value", [("colour", "red"), ("state", "lost"), ("cause", "rumour"),
                                         ("kind", "rare")])
def test_an_unknown_label_kind_or_value_raises_1_error_type(kind, value):
    with pytest.raises(ValueError):
        parts_v2.visible_label(document(), kind, value)


def test_each_part_builds_its_element_index_once(monkeypatch):
    doc, built = document(), []
    build = parts_v2._build_index
    monkeypatch.setattr(parts_v2, "_build_index", lambda d: built.append(1) or build(d))
    for render in (parts_v2.render_sections, parts_v2.render_questions, parts_v2.render_examples):
        built.clear()
        assert render(doc)
        assert len(built) == 1, render.__name__
    with parts_v2.indexed(doc):
        built.clear()
        _every_part(doc)
        assert built == []


# --- sections


def test_a_section_shows_its_current_text_and_a_link_per_section_it_depends_on():
    scope = part_of(parts_v2.render_sections(document()), "sec-scope")
    assert "The export writes the open rows to one file." in visible(scope)
    assert scope.count('href="#sec-format"') == 1 and 'href="#sec-old"' not in scope
    assert re.search(r'<a [^>]*href="#sec-format"[^>]*>File format</a>', scope)


def test_a_section_change_list_shows_open_newest_first_one_line_per_round_naming_the_cause():
    html = parts_v2.render_sections(document())
    scope, format_ = part_of(html, "sec-scope"), part_of(html, "sec-format")
    assert "<details" not in html
    words = visible(scope)
    assert words.index("round 3") < words.index("round 2") < words.index("round 1")
    assert "an answer from product owner" in words and "a note" in words and "a finding of the agent" in words
    assert re.search(r'<a [^>]*href="#q-format"', scope)
    assert "your answer" in visible(format_)
    assert re.search(r'<a [^>]*href="#i-format"[^>]*>Is the format part right\?</a>', format_)


def test_each_change_line_names_its_cause_in_an_attribute():
    scope = part_of(parts_v2.render_sections(document()), "sec-scope")
    assert CAUSE.findall(scope) == ["answer_from", "note", "finding"]


def test_an_answer_from_a_question_with_no_answer_names_someone_else():
    doc = document()
    del doc["questions"][0]["answer"]
    words = visible(part_of(parts_v2.render_sections(doc), "sec-scope"))
    assert "round 3 · an answer from someone else to Which file format do the clerks need? : Kept the file to 1 sheet." in words


def test_a_link_to_a_section_merged_twice_goes_to_the_last_section():
    doc = document()
    doc["sections"].append({"id": "sec-older", "title": "Older notes", "state": "merged", "merged_into": "sec-old",
                            "body": text("Older."), "changes": [line(1)]})
    doc["sections"][0]["links"] = ["sec-older"]
    html = parts_v2.render_sections(doc)
    assert re.findall(r'href="#(sec-[\w-]+)"', part_of(html, "sec-scope")) == ["sec-format"]
    assert 'href="#sec-format"' in part_of(html, "sec-older")


def test_a_merge_cycle_stops_after_the_merge_limit():
    sections = {"sec-x": {"state": "merged", "merged_into": "sec-y"},
                "sec-y": {"state": "merged", "merged_into": "sec-x"}}
    assert parts_v2.current_target(sections, "sec-x") == ("sec-x" if parts_v2.MERGE_LIMIT % 2 == 0 else "sec-y")


def test_a_section_drops_a_link_to_itself_and_to_a_section_merged_into_it():
    doc = document()
    doc["sections"][1]["links"] = ["sec-format", "sec-old"]
    format_ = part_of(parts_v2.render_sections(doc), "sec-format")
    assert "Depends on" not in visible(format_) and 'href="#sec-format"' not in format_


def test_a_section_with_open_questions_shows_a_chip_with_their_count():
    html = parts_v2.render_sections(document())
    assert chip_text(part_of(html, "sec-scope")) == "2 open questions"
    assert chip_text(part_of(html, "sec-format")) is None
    doc = document()
    doc["rounds"][2]["items"][1]["state"] = "settled_by_mark"
    doc["rounds"][2]["items"][1]["settled"] = {"by": "mark", "round": 3, "signal": "accept"}
    assert chip_text(part_of(parts_v2.render_sections(doc), "sec-scope")) == "1 open question"


def test_an_open_card_on_a_merged_section_counts_on_the_section_it_merged_into():
    doc = document()
    doc["rounds"][1]["items"][1]["section"] = "sec-old"
    html = parts_v2.render_sections(doc)
    assert chip_text(part_of(html, "sec-format")) == "1 open question"
    assert chip_text(part_of(html, "sec-scope")) == "1 open question"


def test_a_merged_or_removed_section_shows_1_line_with_a_link_or_its_reason():
    html = parts_v2.render_sections(document())
    merged, removed = part_of(html, "sec-old"), part_of(html, "sec-gone")
    assert "Old format notes" in visible(merged) and 'href="#sec-format"' in merged
    assert "The team dropped printing." in visible(removed)
    for gone in (merged, removed):
        assert "<ol" not in gone and gone.count("<p") == 1
    assert "Notes." not in visible(merged) and "Print the rows." not in visible(removed)


def test_a_section_not_reached_says_so():
    html = parts_v2.render_sections(document())
    assert chip_text(part_of(html, "sec-later"), "afkv2-v2-state") == "not reached yet"
    assert chip_text(part_of(html, "sec-scope"), "afkv2-v2-state") is None


def test_no_section_gives_no_block():
    doc = document()
    doc["sections"] = []
    assert parts_v2.render_sections(doc) == ""


# --- questions for others


def test_the_questions_show_every_question_in_list_order_with_its_roles():
    doc = document()
    html = parts_v2.render_questions(doc)
    words = visible(html)
    places = [words.index(q["question"]) for q in doc["questions"]]
    assert places == sorted(places)
    size = part_of(html, "q-size")
    assert QUESTION_ATTR.format("q-size") in size
    assert json.loads(WHO.search(size).group(1)) == ["tester", "everyone"]
    assert json.loads(WHO.search(part_of(html, "q-format")).group(1)) == ["product owner"]


def test_a_question_shows_each_of_its_parts():
    html = parts_v2.render_questions(document())
    size = part_of(html, "q-size")
    words = visible(size)
    for part in ("tester, everyone", "The export writes one file.", "It sets what the team builds first.",
                 "Ask the support team", "Read the usage report", "A list of 1 million rows.", "open"):
        assert part in words, part
    assert "<strong>one</strong>" in size
    assert "answered by product owner on 2026-11-05" in visible(part_of(html, "q-format")) and "CSV." in visible(
        part_of(html, "q-format"))
    assert "Printing is out of scope." in visible(part_of(html, "q-drop"))
    assert "The file is never zipped." in visible(part_of(html, "q-assume"))


def test_a_question_links_each_linked_section_and_the_question_it_waits_on():
    html = parts_v2.render_questions(document())
    size, cols = part_of(html, "q-size"), part_of(html, "q-cols")
    assert re.search(r'<a [^>]*href="#sec-scope"[^>]*>What the export covers</a>', size)
    assert re.search(r'<a [^>]*href="#q-format"[^>]*>Which file format do the clerks need\?</a>', size)
    assert "waits on" in visible(size).lower()
    assert 'href="#sec-format"' in cols and 'href="#sec-scope"' in cols
    assert "waits on" not in visible(cols).lower()


def test_the_questions_have_a_native_role_filter_of_every_role_once():
    html = parts_v2.render_questions(document())
    select = FILTER.search(html).group(1)
    values = re.findall(r'<option value="([^"]*)"', select)
    assert values == ["", "product owner", "tester", "developer lead"]
    assert "Product owner" in visible(select) and "everyone" not in values


def test_a_question_with_choices_shows_radios_or_checkboxes_when_it_allows_several():
    html = parts_v2.render_questions(document())
    size, cols = part_of(html, "q-size"), part_of(html, "q-cols")
    group = TICK_GROUP.search(size).group(0)
    assert QUESTION_ATTR.format("q-size") in group and SEVERAL.format("false") in group
    assert re.findall(r'<input type="radio"[^>]*value="([^"]+)"', size) == ["opt-k", "opt-m"]
    assert re.findall(r'<input type="checkbox"[^>]*value="([^"]+)"', cols) == ["opt-name", "opt-date", "opt-sum"]
    assert SEVERAL.format("true") in cols and "A million" in visible(size)


def test_a_closed_question_or_one_with_no_choices_has_no_tick_inputs():
    html = parts_v2.render_questions(document())
    for closed in ("q-format", "q-drop", "q-assume"):
        assert TICK_ATTR not in part_of(html, closed), closed


def _choices(question_id, several=False):
    return {"options": [{"id": f"opt-{question_id}-yes", "text": "Yes"}, {"id": f"opt-{question_id}-no", "text": "No"}],
            "several": several}


def test_only_an_open_or_assumed_question_with_choices_has_tick_inputs():
    doc = document()
    for entry in doc["questions"]:
        if entry["id"] in ("q-format", "q-drop", "q-assume"):
            entry["choices"] = _choices(entry["id"])
    html = parts_v2.render_questions(doc)
    assert TICK_ATTR not in part_of(html, "q-format") and TICK_ATTR not in part_of(html, "q-drop")
    assume = part_of(html, "q-assume")
    assert TICK_ATTR in assume
    assert re.findall(r'<input type="radio"[^>]*value="([^"]+)"', assume) == ["opt-q-assume-yes", "opt-q-assume-no"]


def test_an_answer_with_ticks_names_each_ticked_choice():
    doc = document()
    doc["questions"][0]["choices"] = _choices("q-format", several=True)
    doc["questions"][0]["answer"]["choices"] = ["opt-q-format-no", "opt-q-format-yes"]
    words = visible(part_of(parts_v2.render_questions(doc), "q-format"))
    assert "answered by product owner on 2026-11-05: CSV. Ticked: No, Yes." in words


def test_a_role_with_quotes_and_markup_signs_keeps_the_who_attribute_whole():
    doc = document()
    doc["questions"].append(question("q-sign", ["O'Brien & <Co>", 'The "lead"'], "Who signs the export?"))
    raw = WHO.search(part_of(parts_v2.render_questions(doc), "q-sign")).group(1)
    assert "<" not in raw and ">" not in raw and not re.search(r"&(?!amp;|lt;|gt;|#x27;)", raw)
    assert json.loads(html.unescape(raw)) == ["o'brien & <co>", 'the "lead"']


MARKUP = "<i>bold</i> & co"
ESCAPED = "&lt;i&gt;bold&lt;/i&gt; &amp; co"


def test_titles_questions_and_texts_are_escaped():
    doc = document()
    doc["sections"][0]["title"] = f"Scope {MARKUP}"
    doc["sections"][0]["changes"][0]["text"] = f"Wrote {MARKUP}"
    doc["questions"][1]["question"] = f"How many {MARKUP}?"
    doc["questions"][1]["ways"] = [f"Ask {MARKUP}"]
    doc["examples"][0]["title"] = f"Rows {MARKUP}"
    rendered = _every_part(doc)
    assert "<i>" not in rendered
    for heading in (f"Scope {ESCAPED}", f"How many {ESCAPED}?", f"Rows {ESCAPED}"):
        assert f'<h3 class="{V2_HEADING}">{heading}</h3>' in rendered, heading
    assert f"Wrote {ESCAPED}" in part_of(rendered, "sec-scope")
    assert f"<li>Ask {ESCAPED}</li>" in part_of(rendered, "q-size")
    assert f"How many {MARKUP}?" in visible(rendered)


def test_no_question_gives_no_block():
    doc = document()
    doc["questions"] = []
    assert parts_v2.render_questions(doc) == ""


# --- worked examples


def test_the_worked_examples_show_as_a_section_each_marked_frequent_edge_or_risky():
    html = parts_v2.render_examples(document())
    assert EXAMPLES_HEADING in html
    for example_id, kind, words in (("ex-plain", "frequent", "From 3 open rows to 1 file of 3 lines."),
                                    ("ex-big", "edge", "From 1 million rows to 1 file."),
                                    ("ex-bad", "risky", "A comma in a name stays in its cell.")):
        example = visible(part_of(html, example_id))
        assert kind in example and words in example, example_id
    big = visible(part_of(html, "ex-big"))
    assert "As a clerk, I export a large list." in big and "As a clerk, I export the open rows." in big
    bad = visible(part_of(html, "ex-bad"))
    assert bad.index("round 3") < bad.index("round 2")


def test_no_example_gives_no_block():
    doc = document()
    doc["examples"] = []
    assert parts_v2.render_examples(doc) == ""


# --- plain text (PRD AC-016, AC-017)


def _every_part(doc):
    return parts_v2.render_sections(doc) + parts_v2.render_questions(doc) + parts_v2.render_examples(doc)


def _untitled(doc):
    """The fixture with no card title, so each card a change line names needs words of its own."""
    doc = copy.deepcopy(doc)
    for round_ in doc["rounds"]:
        for item in round_["items"]:
            item.pop("title", None)
    return doc


def test_no_visible_text_of_any_part_holds_a_raw_element_id_or_a_round_code():
    for doc in (document(), _untitled(document())):
        words = visible(_every_part(doc))
        assert not ROUND_CODE.search(words), ROUND_CODE.search(words)
        for element in element_ids(doc):
            assert not re.search(rf"(?<![\w-]){re.escape(element)}(?![\w-])", words), element


def test_each_link_to_an_element_shows_its_meaning_on_hover():
    doc = _untitled(document())
    html = _every_part(doc)
    links = re.findall(r"<a [^>]*>", html)
    assert links and all(TIP_ATTR in link for link in links)
    assert CARD_TIP in html
    tips = re.findall(TIP_ATTR + r'"([^"]*)"', html)
    for element in element_ids(doc):
        assert not any(re.search(rf"(?<![\w-]){re.escape(element)}(?![\w-])", tip) for tip in tips), element


def test_the_hover_text_of_a_link_names_the_kind_of_element():
    doc = document()
    for element, tip in (("sec-format", "Opens this section"), ("ex-big", "Opens this worked example"),
                         ("q-size", "Opens this question for others"), ("st-big", "A story of this topic"),
                         ("opt-m", "A choice of a question for others"), ("i-format", "Opens this card of round 3"),
                         ("x-unknown", "Opens this part of the page")):
        assert f'{TIP_ATTR}"{tip}"' in parts_v2.link(doc, element), element
