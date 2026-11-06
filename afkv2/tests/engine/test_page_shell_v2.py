"""The page shell of a version 2 page (SDD §8 row "engine: page shell", SDD §10, ADR-0003 design): the version 2
layout order, the banner's section lists, sections that never fold into the settled part, the page-size budget,
and version 0 and 1 pages that show the same visible text as before the version 2 layout."""

import copy
import hashlib
import json
import sys
import time
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
for folder in (PLUGIN / "scripts", ENGINE_DIR, Path(__file__).resolve().parent):
    sys.path.insert(0, str(folder))

import engine  # noqa: E402
import test_page_parts_v2 as parts_case  # noqa: E402
import test_page_shell as shell_case  # noqa: E402
from shell import page  # noqa: E402
from test_page_parts_v2 import card, document, line, question, round_of, text, visible  # noqa: E402

PAGE_BUDGET_BYTES = 1_000_000
RENDER_BUDGET_SECONDS = 2.0
BANNER = 'data-afkv2-banner="{}"'
SETTLED_PART = 'id="afkv2-settled"'
SECTIONS_PART = 'id="afkv2-sections"'
LINK = 'href="#{}"'


def build(doc):
    return page.build(engine.READERS[doc["schema"]](doc))


def banner(html, n):
    start = html.index(BANNER.format(n))
    return html[start:html.index("</header>", start)]


def block(html, start_marker):
    """The HTML of the section that opens with `start_marker`, up to its closing tag."""
    start = html.index(start_marker)
    return html[start:html.index("</section>", start)]


# --- the version 2 order


def test_a_version_2_page_shows_its_parts_in_the_version_2_order():
    html = build(document())
    order = ['<h1 class="afkv2-title">', BANNER.format(3), 'id="afkv2-notes-replies"', 'id="afkv2-r-3"',
             'id="afkv2-maps"', SECTIONS_PART, 'id="afkv2-examples"', 'id="afkv2-questions"']
    places = [html.index(marker) for marker in order]
    assert places == sorted(places)


def test_the_round_questions_show_in_one_block_and_each_links_to_its_section():
    html = build(document())
    questions = block(html, 'id="afkv2-r-3"')
    for card_id, section in (("i-closed", "sec-scope"), ("i-rows", "sec-scope")):
        start = questions.index(f'<article class="afkv2-card afkv2-card--confirm" id="{card_id}"')
        own = questions[start:questions.index("</article>", start)]
        assert LINK.format(section) in own
        assert "What the export covers" in visible(own)
    assert html.count('id="i-closed"') == 1


def test_a_card_on_a_merged_section_links_to_the_section_it_merged_into():
    doc = document()
    doc["rounds"][2]["items"][1]["section"] = "sec-old"
    html = build(doc)
    start = html.index('id="i-closed"')
    own = html[start:html.index("</article>", start)]
    assert LINK.format("sec-format") in own and LINK.format("sec-old") not in own


# --- the banner


def banner_document():
    """Round 3 adds 1 section, changes 2, merges 1 and removes 1."""
    doc = document()
    by_id = {section["id"]: section for section in doc["sections"]}
    by_id["sec-old"]["changes"].append(line(3, "finding", "Merged into the format part."))
    by_id["sec-gone"]["changes"].append(line(3, "finding", "Removed."))
    doc["sections"].append({"id": "sec-new", "title": "Where the file goes", "state": "current",
                            "body": text("The file goes to the downloads folder."),
                            "changes": [line(3, "finding", "Added this part.")]})
    return doc


def test_the_banner_lists_each_added_changed_merged_and_removed_section_with_a_link():
    html = build(banner_document())
    own = banner(html, 3)
    words = visible(own)
    for heading, section, title in (("Sections added", "sec-new", "Where the file goes"),
                                    ("Sections changed", "sec-scope", "What the export covers"),
                                    ("Sections changed", "sec-format", "File format"),
                                    ("Sections merged", "sec-old", "Old format notes"),
                                    ("Sections removed", "sec-gone", "Printing")):
        assert heading in words and title in words
        assert LINK.format(section) in own
    assert words.index("Sections added") < words.index("Where the file goes") < words.index("Sections changed")
    assert "Delivery by mail" not in words and LINK.format("sec-later") not in own


def test_the_banner_of_an_earlier_round_lists_that_round_s_sections():
    html = build(document())
    own = banner(html, 2)
    words = visible(own)
    assert "Sections merged" in words and LINK.format("sec-old") in own
    assert "Sections removed" in words and LINK.format("sec-gone") in own
    assert "Sections added" not in words


def test_no_banner_shows_a_round_code():
    html = build(banner_document())
    for n in (1, 2, 3):
        assert not parts_case.ROUND_CODE.search(visible(banner(html, n)))


# --- a section never folds into the settled part


def test_a_section_of_an_earlier_round_stays_in_the_sections_part():
    doc = document()
    doc["sections"].append({"id": "sec-still", "title": "Who runs the export", "state": "current",
                            "body": text("A clerk runs it."), "changes": [line(1, "finding", "Wrote it.")]})
    html = build(doc)
    assert 'id="sec-still"' in block(html, SECTIONS_PART)
    assert SETTLED_PART in html
    assert 'id="sec-still"' not in block(html, SETTLED_PART)


# --- the page-size budget


SECTION_COUNT, ROUND_COUNT, NOTE_COUNT, QUESTION_COUNT, EXAMPLE_COUNT = 20, 12, 100, 30, 15
WORDS = ("The export writes the open rows of the list to one file, and each row keeps its own cells in the order "
         "the clerk sees them on the screen. ")


def budget_document():
    """A valid version 2 page of 20 sections, 12 rounds, 240 change lines, 100 notes, 30 questions, 15 examples."""
    sections = [{"id": f"sec-{s}", "title": f"Part {s} of the export", "state": "current",
                 "links": [f"sec-{(s + 1) % SECTION_COUNT}"], "body": text(WORDS * 4),
                 "changes": [line(n, "finding", f"Changed part {s} in this round.") for n in range(1, ROUND_COUNT + 1)]}
                for s in range(SECTION_COUNT)]
    stories = [{"id": f"st-{k}", "text": f"As a clerk, I export list {k}.", "changes": []} for k in range(EXAMPLE_COUNT)]
    examples = [{"id": f"ex-{k}", "title": f"Worked example {k}", "kind": ("frequent", "edge", "risky")[k % 3],
                 "stories": [f"st-{k}"], "body": text(WORDS * 2), "changes": []} for k in range(EXAMPLE_COUNT)]
    questions = [question(f"q-{k}", ["product owner", "tester"], f"Which rule applies to list {k}?",
                          links=[f"sec-{k % SECTION_COUNT}"], origin={"card": "i-r1-0"}, changes=[],
                          choices={"options": [{"id": f"opt-{k}-a", "text": "The first rule"},
                                               {"id": f"opt-{k}-b", "text": "The second rule"}], "several": k % 2 == 1})
                 for k in range(QUESTION_COUNT)]
    counts: dict = {}
    notes = []
    for k in range(NOTE_COUNT):
        n, owner = k % ROUND_COUNT + 1, f"sec-{k % SECTION_COUNT}"
        counts[(n, owner)] = counts.get((n, owner), 0) + 1
        notes.append({"id": f"N-{n}-{owner}-{counts[(n, owner)]}", "round": n, "target": owner, "item": owner,
                      "text": "This part misses the closed rows of the list.", "deleted": False})
    rounds = []
    for n in range(1, ROUND_COUNT + 1):
        items = [card(f"i-r{n}-{k}", f"sec-{(n + k) % SECTION_COUNT}", None if n == ROUND_COUNT else n)
                 for k in range(3)]
        rounds.append(round_of(n, *items, state="current" if n == ROUND_COUNT else "settled"))
    return {"schema": "afkv2.page/2",
            "session": {"id": "budget", "skill": "grill", "feature": "export", "ticket": "PROJ-1",
                        "started": "2026-01-05T09:00:00Z", "step": "Requirements grill"},
            "maps": [], "notes": notes, "sections": sections, "stories": stories, "examples": examples,
            "questions": questions, "rounds": rounds}


def test_the_budget_page_has_the_counts_of_sdd_section_10():
    doc = budget_document()
    assert len(doc["sections"]) == SECTION_COUNT and len(doc["rounds"]) == ROUND_COUNT
    assert sum(len(entry["changes"]) for kind in ("sections", "stories", "examples", "questions")
               for entry in doc[kind]) == 240
    assert (len(doc["notes"]), len(doc["questions"]), len(doc["examples"])) == (NOTE_COUNT, QUESTION_COUNT,
                                                                                 EXAMPLE_COUNT)


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A repository with a spec folder; the page document goes in its `pages` folder."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    root = tmp_path / "repo"
    (root / ".afkv2").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / ".afkv2" / "config.json").write_text('{"spec_folder": "specs"}', "utf-8")
    folder = root / "specs" / "pages"
    folder.mkdir(parents=True)
    return folder


def test_the_budget_page_renders_within_the_size_and_time_budget(home, capsys):
    path = home / "grill-budget.json"
    path.write_text(json.dumps(budget_document()), "utf-8")
    started = time.perf_counter()
    assert engine.main(["render", str(path)]) == 0, capsys.readouterr().out
    seconds = time.perf_counter() - started
    html = path.with_suffix(".html").read_bytes()
    assert SECTIONS_PART.encode() in html
    assert len(html) <= PAGE_BUDGET_BYTES, f"{len(html)} bytes, budget {PAGE_BUDGET_BYTES}"
    assert seconds <= RENDER_BUDGET_SECONDS, f"{seconds:.2f} s, budget {RENDER_BUDGET_SECONDS} s"


# --- version 0 and 1 pages show as before


# The visible text of each stored page, rendered at the base of the version 2 layout (commit c72cee14).
BEFORE = {
    "v0-page-with-notes.json": "74c2d3303d6260b4eb2d689ea32d32d53f3a79213618bbf98a648fcde6ec34a3",
    "v0-sdd-pass.json": "6056b9e6de5dd750aae3aad4ecbae3c8199f22aa98264e8b964234edf1ac2863",
    "v0-page-with-notes.json as version 1": "6814440946159be6d9c1acaa22fc8a46eb34e7c0d667073732b901fe09f04362",
    "v0-sdd-pass.json as version 1": "2feadffea9b2e204286da15139dbc3a2c1a032781983e6f676a4877a9948dafc",
    "two rounds, version 1": "6259db8efcfe768d6f6620c9dfd8a7ac03dea26dcd30659e4509ca028335e956",
    "changed rounds, version 1": "252e1b94bebba2a6633cbb78bf44bec165ebd43b6b937c41c9453fb240c6a517",
}


def old_pages():
    """Each stored version 0 page, the same page as the engine writes it in version 1, and the version 1 pages of
    the page shell tests."""
    found = {}
    for name in ("v0-page-with-notes.json", "v0-sdd-pass.json"):
        doc = json.loads((FIXTURES / name).read_text("utf-8"))
        found[name] = doc
        found[f"{name} as version 1"] = json.loads(json.dumps(engine.READERS[doc["schema"]](doc)))
    found["two rounds, version 1"] = shell_case.two_rounds()
    found["changed rounds, version 1"] = shell_case.changed_rounds()
    return found


@pytest.mark.parametrize("name", sorted(BEFORE))
def test_a_version_0_or_1_page_shows_the_same_visible_text_as_before(name):
    doc = copy.deepcopy(old_pages()[name])
    assert doc["schema"] in ("afkv2.page/0", "afkv2.page/1")
    assert hashlib.sha256(visible(build(doc)).encode("utf-8")).hexdigest() == BEFORE[name]
