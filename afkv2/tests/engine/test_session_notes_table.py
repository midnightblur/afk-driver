"""The session notes table and the card notes (SDD §14 rows "Session notes table" and "Answer pairing"):
one row per note, a Noted text column, every note of the session newest round first, older rounds as
closed groups with a count line, answers paired by note ids, and one link per changed element."""

import re
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
for folder in (PLUGIN / "scripts", ENGINE_DIR):
    sys.path.insert(0, str(folder))

import engine  # noqa: E402
from shell import page  # noqa: E402

V0, V1 = "afkv2.page/0", "afkv2.page/1"
SLOT = 'id="afkv2-notes-replies"'
CARD_START = 'id="{}" data-afkv2-item='
BODY = '<div class="afkv2-body">'
CHANGE_CLASS = "afkv2-nr-changed"
CARD_ROW, SESSION_ROW = "afkv2-nr-", "afkv2-ns-"
ROW_CLASS = 'class="afkv2-nr-row"'
ROUND_GROUP = 'data-afkv2-nr-round="{}"'
ROUND_FOLD = 'data-afkv2-fold="notes-round-{}"'


def text(value, **extra):
    return {"type": "text", "props": {"text": value}, **extra}


def card(item_id, **extra):
    return {"id": item_id, "kind": "confirm", "body": text(f"Body of {item_id}", id=f"{item_id}-words"), **extra}


def round_of(n, *items, state="settled", replies=None):
    return {"n": n, "state": state, "banner": {"settled": [], "unlocks": [], "parked": []},
            "items": list(items), **({"replies": replies} if replies else {})}


def note(note_id, round_n, target, item=None, words="words", quote=None):
    return {"id": note_id, "round": round_n, "target": target, "item": item, "quote": quote, "text": words,
            "deleted": False}


def document(*rounds, notes=(), maps=None):
    rounds = list(rounds)
    rounds[-1]["state"] = "current"
    return {"schema": V1,
            "session": {"id": "s1", "skill": "grill", "feature": "export", "ticket": "PROJ-1",
                        "started": "2026-01-05T09:00:00Z", "step": "Requirements grill"},
            "maps": maps or [], "notes": list(notes), "rounds": rounds}


def build(doc):
    return page.build(engine.READERS[doc["schema"]](doc))


def session(html):
    start = html.index(SLOT)
    return html[start:html.index("</section>", start)]


def on_card(html, item_id):
    start = html.index(CARD_START.format(item_id))
    return html[start:html.index(BODY, start)]


def row(html, row_id):
    start = html.index(f'id="{row_id}"')
    return html[start:html.index("</tr>", start)]


def both(html, item_id):
    """(the rows of the card, its row prefix) and (the session table, its row prefix)."""
    return (on_card(html, item_id), CARD_ROW), (session(html), SESSION_ROW)


def cells(row_html):
    return re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)


def three_notes():
    notes = [note(f"N-1-i-a-{k}", 1, "i-a", "i-a", f"note {k}") for k in (1, 2, 3)]
    return document(round_of(1, card("i-a")), notes=notes)


def test_3_notes_on_one_element_are_3_rows_each_with_its_own_note_id():
    html = build(three_notes())
    for k in (1, 2, 3):
        assert f"note {k}" in row(on_card(html, "i-a"), f"{CARD_ROW}N-1-i-a-{k}")
        assert f'title="N-1-i-a-{k}"' in row(session(html), f"{SESSION_ROW}N-1-i-a-{k}")
    assert on_card(html, "i-a").count(ROW_CLASS) == 3


def test_one_answer_of_2_notes_stands_in_both_rows_and_no_row_holds_2_notes():
    doc = three_notes()
    doc["rounds"][0]["replies"] = [{"id": "A-1-1", "text": "one answer for two", "notes": ["N-1-i-a-1", "N-1-i-a-3"]}]
    html = build(doc)
    for table, prefix in both(html, "i-a"):
        assert "one answer for two" in row(table, prefix + "N-1-i-a-1")
        assert "one answer for two" in row(table, prefix + "N-1-i-a-3")
        assert "one answer for two" not in row(table, prefix + "N-1-i-a-2")
        for k in (1, 2, 3):
            the_row = row(table, f"{prefix}N-1-i-a-{k}")
            assert the_row.count("note ") == 1 and len(re.findall(r'title="N-', the_row)) == 1


def test_an_answer_row_links_once_to_each_element_it_changed():
    doc = document(round_of(1, card("i-a"), card("i-b")),
                   notes=[note("N-1-i-a-1", 1, "i-a", "i-a"), note("N-1-i-b-1", 1, "i-b", "i-b")])
    doc["rounds"][0]["replies"] = [
        {"id": "A-1-1", "text": "changed two", "notes": ["N-1-i-a-1"], "changed": ["i-b", "i-a-words"]},
        {"id": "A-1-2", "text": "kept as it is", "notes": ["N-1-i-b-1"], "changed": []}]
    html = build(doc)
    for table, prefix in both(html, "i-a"):
        answer = cells(row(table, prefix + "N-1-i-a-1"))[4]
        assert answer.count('href="#i-b"') == 1 and answer.count('href="#i-a-words"') == 1
        assert CHANGE_CLASS in answer
    for table, prefix in both(html, "i-b"):
        answer = cells(row(table, prefix + "N-1-i-b-1"))[4]
        assert "kept as it is" in answer and CHANGE_CLASS not in answer and "href" not in answer


def test_a_repeated_changed_id_gives_one_link_with_the_element_label():
    doc = document(round_of(1, card("i-a"), card("i-b")), notes=[note("N-1-i-a-1", 1, "i-a", "i-a")])
    doc["rounds"][0]["replies"] = [
        {"id": "A-1-1", "text": "changed one", "notes": ["N-1-i-a-1"], "changed": ["i-b-words", "i-b-words"]}]
    answer = cells(row(session(build(doc)), SESSION_ROW + "N-1-i-a-1"))[4]
    assert answer.count('href="#i-b-words"') == 1 and ">Body of i-b</a>" in answer


def test_an_answer_to_a_deleted_note_stands_alone_in_the_session_table():
    doc = document(round_of(1, card("i-a")), notes=[{**note("N-1-i-a-1", 1, "i-a", "i-a"), "deleted": True}])
    doc["rounds"][0]["replies"] = [{"id": "A-1-1", "text": "answer to a gone note", "notes": ["N-1-i-a-1"]}]
    table = session(build(doc))
    assert "answer to a gone note" in row(table, CARD_ROW + "reply-1-1") and "From me" in table


def test_the_noted_text_column_holds_the_quote_and_your_note_only_the_words():
    doc = document(round_of(1, card("i-a")),
                   notes=[note("N-1-i-a-1", 1, "i-a-words", "i-a", "my words", quote="the <selected> text")])
    html = build(doc)
    for table, prefix in both(html, "i-a"):
        assert "<th>Noted text</th><th>Your note</th>" in table
        _, _, noted, words, *_ = cells(row(table, prefix + "N-1-i-a-1"))
        assert "the &lt;selected&gt; text" in noted and "my words" not in noted
        assert "my words" in words and "selected" not in words


def test_the_session_table_lists_every_note_and_answer_newest_round_first_with_a_link_each():
    doc = document(round_of(1, card("i-a")), round_of(2, card("i-b")),
                   notes=[note("N-1-i-a-1", 1, "i-a", "i-a", "card note one"),
                          note("N-2-R-2-1", 2, "R-2", None, "a steer"),
                          note("N-2-i-b-1", 2, "i-b-words", "i-b", "card note two")])
    doc["rounds"][1]["replies"] = [{"id": "A-2-1", "text": "an answer alone"}]
    table = session(build(doc))
    places = [table.index(words) for words in ("a steer", "card note two", "an answer alone", "card note one")]
    assert table.index(ROUND_GROUP.format(2)) < places[0] and places == sorted(places)
    assert table.index(ROUND_GROUP.format(1)) < places[3]
    assert 'href="#i-b"' in row(table, SESSION_ROW + "N-2-i-b-1") and 'href="#i-a"' in row(table, SESSION_ROW + "N-1-i-a-1")
    assert 'href="#R-2"' in row(table, CARD_ROW + "N-2-R-2-1")


def test_every_session_row_of_a_card_stands_for_that_card_and_every_id_is_unique():
    doc = three_notes()
    html = build(doc)
    found = page.targets(engine.READERS[V1](doc))
    for k in (1, 2, 3):
        assert found[f"afkv2-nr-N-1-i-a-{k}"] == "i-a" and found[f"afkv2-ns-N-1-i-a-{k}"] == "i-a"
    ids = re.findall(r' id="([^"]+)"', html)
    assert len(ids) == len(set(ids))


def four_rounds():
    rounds = [round_of(n, card(f"i-{n}")) for n in (1, 2, 3, 4)]
    notes = [note(f"N-{n}-i-{n}-1", n, f"i-{n}", f"i-{n}", f"note of round {n}") for n in (1, 2, 3, 4)]
    notes.append(note("N-1-i-1-2", 1, "i-1", "i-1", "second note of round 1"))
    rounds[0]["replies"] = [{"id": "A-1-1", "text": "answer of round 1", "notes": ["N-1-i-1-1", "N-1-i-1-2"]}]
    return document(*rounds, notes=notes)


def test_on_round_3_or_later_the_current_and_previous_round_are_open_and_each_older_round_is_its_own_closed_group():
    table = session(build(four_rounds()))
    open_part = table[:table.index("<details")]
    assert "note of round 4" in open_part and "note of round 3" in open_part
    folds = re.findall(r'<details([^>]*)><summary>(.*?)</summary>(.*?)</details>', table, re.S)
    assert len(folds) == 2
    (attrs_2, summary_2, body_2), (attrs_1, summary_1, body_1) = folds
    assert " open" not in attrs_2 + attrs_1
    assert ROUND_FOLD.format(2) in attrs_2 and ROUND_FOLD.format(1) in attrs_1
    assert "Round 2" in summary_2 and "1 note from you" in summary_2 and "note of round 2" in body_2
    assert "Round 1" in summary_1 and "2 notes from you, 1 answer from me" in summary_1
    assert "note of round 1" in body_1 and "note of round 2" not in body_1


def test_round_2_has_no_closed_group():
    doc = four_rounds()
    doc["rounds"] = doc["rounds"][:2]
    doc["rounds"][1]["state"] = "current"
    doc["notes"] = [n for n in doc["notes"] if n["round"] <= 2]
    table = session(build(doc))
    assert "<details" not in table and "note of round 1" in table and "note of round 2" in table


def test_each_card_still_shows_its_own_notes_under_it():
    html = build(four_rounds())
    for n in (1, 2, 3, 4):
        assert f"note of round {n}" in on_card(html, f"i-{n}")
    assert "note of round 2" not in on_card(html, "i-1")


def test_a_format_0_page_pairs_an_answer_by_its_about_list():
    doc = {"schema": V0,
           "session": {"id": "s1", "skill": "grill", "feature": "export", "ticket": "PROJ-1",
                       "started": "2026-01-05T09:00:00Z"},
           "rounds": [round_of(1, {**card("i-a"), "notes": [
               {"id": "N-1-i-a", "round": 1, "target": "i-a", "text": "old note", "deleted": False}]}),
               round_of(2, card("i-b"), state="current",
                        replies=[{"text": "answer by about", "about": ["i-a"]}])]}
    html = build(doc)
    assert "answer by about" in row(on_card(html, "i-a"), CARD_ROW + "N-1-i-a")
    assert "answer by about" in row(session(html), SESSION_ROW + "N-1-i-a")


# --- the column widths of the 2 notes tables (D-14): # | Where | Noted text | Your note | Answer [| Open]

WIDTH_RULE = re.compile(r"([^{}]*?)th:nth-child\((\d)\)\s*\{\s*width:\s*([^;]+);")
TABLE_CLASS, CARD_MODIFIER = "afkv2-nr-table", "afkv2-nr-table--card"


def widths(card_table):
    """The width that wins for each column of a notes table in the page's CSS: highest specificity, then the
    later rule. A rule without the card modifier holds for both tables."""
    found = {}
    for position, match in enumerate(WIDTH_RULE.finditer(page._assets(".css", page.BASE_CSS))):
        selector, column, width = match.group(1).strip(), int(match.group(2)), match.group(3).strip()
        if TABLE_CLASS not in selector or (CARD_MODIFIER in selector and not card_table):
            continue
        rank = (selector.count(".") + 1, position)
        if column not in found or rank > found[column][0]:
            found[column] = (rank, width)
    return {column: width for column, (_, width) in found.items()}


def test_the_session_table_fixes_the_number_and_open_columns_and_leaves_the_answer_free():
    session_widths = widths(card_table=False)
    assert session_widths[1].endswith("rem") and session_widths[6].endswith("rem")
    assert 5 not in session_widths
    assert all(session_widths[k].endswith("%") for k in (2, 3, 4))


def test_the_card_table_gives_the_text_columns_shares_and_leaves_the_answer_free():
    card_widths = widths(card_table=True)
    assert card_widths[1].endswith("rem") and 5 not in card_widths
    shares = [float(card_widths[k].rstrip("%")) for k in (2, 3, 4)]
    assert sum(shares) < 80 and shares[1] <= shares[2]
