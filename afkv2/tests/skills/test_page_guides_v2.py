"""The page guides on version 2 (SDD §3 rows "use-lavish" and "visualize"; SDD §14 row "Glossary "Answer"").

use-lavish holds every page layout rule and the answer rules; visualize holds the pictures. The quality of the
rules is proved by a dogfood run; these tests pin where each rule lives and that it agrees with the code.
"""

import json
import re
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN / "engine"))
sys.path.insert(0, str(PLUGIN / "skills" / "use-lavish" / "scripts"))
from shell import inject  # noqa: E402
import round_document  # noqa: E402

GLOSSARY = PLUGIN / "GLOSSARY.md"
HOME = PLUGIN / "skills" / "use-lavish"
SKILL_MD = HOME / "SKILL.md"
ROUND_PASS_MD = HOME / "ROUND-PASS.md"


def _section(text, heading):
    """The text under `heading` up to the next heading of the same or a higher level."""
    level = heading.split(" ", 1)[0]
    start = text.index(heading + "\n")
    rest = text[start + len(heading) + 1:]
    stop = re.search(rf"^#{{1,{len(level)}}} ", rest, re.M)
    return " ".join((rest[:stop.start()] if stop else rest).split())


def _row(text, rule):
    return next(line for line in text.splitlines() if line.startswith(f"| {rule} |"))


# --- the glossary: the agent's reply to a note is a Reply (PRD AC-022)

def test_glossary_names_reply():
    terms = inject.parse_glossary(GLOSSARY)
    assert "reply" in terms and "note" in terms["reply"].casefold()
    assert "its own reply" in terms["reply"]
    shared = {**inject._seed(inject.SEED), **terms}
    tipped = [key for key in shared if re.search(r"\banswers?\b", key, re.I)]
    assert not tipped, tipped


# --- the answer rules: 1 reply per note, each reading stated (PRD AC-012, AC-013)

def test_each_note_gets_its_own_reply_that_states_each_reading():
    text = SKILL_MD.read_text("utf-8")
    rules = _section(text, "### Answer rules")
    assert "states each reading" in _row(text, "AR-05")
    ten = _row(text, "AR-10")
    for fact in ("its own reply, written for that note", "No reply copies another note's reply", "`reply-many-notes`"):
        assert fact in ten, fact
    assert "repeats in each" not in rules and "one answer per point" not in rules


def test_the_note_reading_writes_1_reply_per_note():
    """Review finding f4: `notes` names the note of the reply on every version; version 2 refuses 2 or more."""
    notes = _section(ROUND_PASS_MD.read_text("utf-8"), "## Read the notes")
    assert "each note id it answers" not in notes
    for fact in ("A reply names the id of its note in `notes`", "On a version 2 page, a reply that names 2 or more "
                 "notes is refused", "states each reading"):
        assert fact in notes, fact


def test_the_guide_names_the_refusal_the_builder_writes():
    """Consumes 0006; review finding f8: the code of AR-10 is the one the builder raises."""
    codes = re.findall(r"\(`([a-z]+(?:-[a-z]+)+)`\)", _row(SKILL_MD.read_text("utf-8"), "AR-10"))
    assert codes == ["reply-many-notes"], codes
    builder = (HOME / "scripts" / "round_document.py").read_text("utf-8")
    assert f'Refusal("{codes[0]}"' in builder


# The words of a reply to a note: "answer" stays for an answer to a card or a question (review finding f1).
ANSWER_KEPT = ("Answer rules", "answer rules", "an answer, a new idea, a question")


def _answer_words(text):
    for kept in ANSWER_KEPT:
        text = text.replace(kept, "")
    return re.findall(r"\banswer\w*", text, re.I)


def test_the_agent_writes_a_reply_to_each_note():
    """Review finding f1: Reply is the glossary term for the write-back to a note (PRD AC-022)."""
    text = SKILL_MD.read_text("utf-8")
    notes = _section(ROUND_PASS_MD.read_text("utf-8"), "## Read the notes")
    assert not _answer_words(notes), _answer_words(notes)
    for rule in [f"AR-{k:02}" for k in range(1, 11)]:
        row = _row(text, rule)
        assert not _answer_words(row), (rule, _answer_words(row))
    for part in (_section(text, "## Take over a page"), _row(text, "`scripts/round_document.py build --doc D --session "
                 "S [--ticket K] --round-input F [--ticket-file T] [--replace] [--private]`")):
        assert not _answer_words(part), _answer_words(part)
    readings = _section(ROUND_PASS_MD.read_text("utf-8"), "## Read the questions and the settled notes")
    keep = next(part for part in readings.split("- ") if part.startswith("`keep`"))
    assert not _answer_words(keep), _answer_words(keep)
    assert "every note of the session, card notes included, with its reply" in text


# --- the round pass: keep, answer, drop and assume (SDD §3 row "reading tool")

def test_the_round_pass_describes_the_readings_of_a_version_2_page():
    found = _section(ROUND_PASS_MD.read_text("utf-8"), "## Read the questions and the settled notes")
    for word in ("`questions_to_read`", "`settled_notes_to_read`", "version 2"):
        assert word in found, word
    raw = ROUND_PASS_MD.read_text("utf-8")
    raw = raw[raw.index("## Read the questions and the settled notes"):]
    assert set(re.findall(r"^- `(\w+)`", raw, re.M)) == set(round_document.READINGS_V2)
    for reading, fields in round_document.READINGS_V2.items():
        line = next((part for part in found.split("- ") if part.startswith(f"`{reading}`")), "")
        assert line, reading
        for field in fields:
            assert f"`{field}`" in line, (reading, field)
    builder = (HOME / "scripts" / "round_document.py").read_text("utf-8")
    rules = (PLUGIN / "engine" / "schema" / "invariants.py").read_text("utf-8")
    named = {value: name for name, value in re.findall(r'^([A-Z_]+) = "([a-z-]+)"$', rules, re.M)}
    codes = set(re.findall(r"\(`([a-z]+(?:-[a-z]+)+)`\)", found))
    assert codes >= {"not-a-question", "answer-no-signal", "everyone-answered", "drop-no-reason", "assume-no-card"}
    for code in sorted(codes):
        raised = f'Refusal("{code}"' in builder
        checked = (code in round_document.NAMED_RULES and code in named
                   and re.search(rf"_named\(\s*{named[code]},", rules) is not None)
        assert raised or checked, code


# --- the layout rules live in use-lavish (PRD AC-027)

V2_ORDER = ("the banner", "the notes and replies", "the maps", "the sections", "the worked examples",
            "the questions for others", "the questions of the round", "the settled points", "the earlier banners")


def test_use_lavish_holds_the_version_2_layout():
    text = SKILL_MD.read_text("utf-8")
    first = _section(text, "#### What goes first on a version 2 page")
    places = [first.find(part) for part in V2_ORDER]
    assert -1 not in places and places == sorted(places), dict(zip(V2_ORDER, places))
    sections = _section(text, "#### Sections and change lines")
    for fact in ("`not_reached`", "`merged_into`", "`reason`", "`links`", "`section`", "only the entries that changed",
                 "`change`", "`unchanged-entry`", "newest first", "never folds"):
        assert fact in sections, fact
    schema = json.loads((PLUGIN / "engine" / "schema" / "page-v2.schema.json").read_text("utf-8"))
    for cause in schema["$defs"]["change_line"]["properties"]["cause"]["enum"]:
        assert f"`{cause}`" in sections, cause
    asks = _section(text, "#### The questions block")
    for fact in ("1 block", "link to its section", "`after`", "filter"):
        assert fact in asks, fact


def test_use_lavish_holds_the_layout_of_version_0_and_1():
    """Ruling D-39, moved with the layout: the session notes table holds every note, card notes included."""
    layout = _section(SKILL_MD.read_text("utf-8"), "#### What goes first on a version 0 or 1 page")
    assert "every note of the session, card notes included" in layout and "one fold per round" in layout
    assert "stand on no card" not in layout


VISUALIZE = PLUGIN / "skills" / "visualize"
LAYOUT_WORDS = ("## Page layout", "## Controls the engine adds", "lays out the page", "Settled by earlier rounds",
                "Earlier banners", "copy bar", "tab title",
                # where a part sits on the page (review finding f5); a component's own looks may say "at the end"
                "the engine puts", "goes first", "page order", "top of the page", "bottom of the page",
                "on the page, above", "first on the page", "last on the page", "maps section")
# where a page part sits relative to another page part (review finding r1-g5-2)
PLACEMENT = re.compile(r"\b(above|below|after|before) (the )?(notes|replies|maps|banners?|round banner|sections|cards|"
                       r"questions)\b", re.I)


def _flat(path):
    return " ".join(path.read_text("utf-8").split())


def test_visualize_holds_no_page_layout_rule():
    """Decision D-22: visualize holds the pictures; each layout rule lives in use-lavish alone."""
    found = [(path.name, word) for path in sorted(VISUALIZE.rglob("*.md"))
             for word in LAYOUT_WORDS if word.casefold() in _flat(path).casefold()]
    found += [(path.name, match.group(0)) for path in sorted(VISUALIZE.rglob("*.md"))
              for match in PLACEMENT.finditer(_flat(path))]
    assert not found, found
    layout = SKILL_MD.read_text("utf-8")
    for heading in ("#### Title and tab", "#### Controls the engine adds"):
        assert heading + "\n" in layout, heading
