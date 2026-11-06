"""The grill's guides on version 2 (SDD §3 row "grill"; SDD §6 the moves of a question for others; SDD §7 the
meeting, coming-back and no-page flows; PLAN.md decision D-26).

The grill holds the content of a session: sections, stories, worked examples and questions for others. The quality
of the rules is proved by a dogfood run; these tests pin where each rule lives, that it agrees with the code, and
that the grill holds no page-layout rule.
"""

import json
import re
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
HOME = PLUGIN / "skills" / "grill"
SKILLS = PLUGIN / "skills"
for _folder in (HOME / "scripts", SKILLS / "use-lavish" / "scripts", PLUGIN / "engine"):
    sys.path.insert(0, str(_folder))

import round_document  # noqa: E402
from shell import parts_v2  # noqa: E402

SKILL_MD = HOME / "SKILL.md"
ROUNDS_MD = HOME / "ROUNDS.md"
LOG_FORMAT_MD = HOME / "GRILL-LOG-FORMAT.md"
SCHEMA = json.loads((PLUGIN / "engine" / "schema" / "page-v2.schema.json").read_text("utf-8"))["$defs"]
# The fields of a question that the engine or the reading tool writes, not the agent's parts of the question.
ENGINE_FIELDS = {"id", "origin", "state", "answer", "dropped", "assumption", "changes"}


def _flat(text):
    return " ".join(text.split())


def _section(text, heading):
    """The text under `heading` up to the next heading of the same or a higher level, on 1 line."""
    level = heading.split(" ", 1)[0]
    start = text.index(heading + "\n")
    rest = text[start + len(heading) + 1:]
    stop = re.search(rf"^#{{1,{len(level)}}} ", rest, re.M)
    return _flat(rest[:stop.start()] if stop else rest)


def _step(n):
    """Step `n` of SKILL.md, up to the next step, on 1 line."""
    text = SKILL_MD.read_text("utf-8")
    start = re.search(rf"^{n}\. \*\*", text, re.M).start()
    stop = re.search(rf"^{n + 1}\. \*\*", text[start:], re.M)
    return _flat(text[start:start + stop.start()] if stop else text[start:])


def _questions():
    return _section(ROUNDS_MD.read_text("utf-8"), "###  Questions for others")


# --- the content of a session lives in the page document (PRD AC-025; SDD §3 row "grill")

def test_the_session_content_names_each_list_of_the_page_document():
    content = _section(ROUNDS_MD.read_text("utf-8"), "## The session's content")
    for name in round_document.ENTRY_LISTS:
        assert f"`{name}`" in content, name
    for kind in ("frequent", "edge", "risky"):
        assert kind in content, kind
    assert "with or without a page" in content
    assert "\"The session's content\"" in _step(4)


def test_the_guides_name_each_field_the_builder_requires_of_a_new_entry():
    """A new entry without a required field is refused by the document check (review finding f1)."""
    content = _section(ROUNDS_MD.read_text("utf-8"), "## The session's content")
    for name, kind in round_document.ENTRY_LISTS.items():
        for field in sorted(set(SCHEMA[kind]["required"]) - {"id", "changes"}):
            assert f"`{field}`" in content, (name, field)
    assert "`state: open`" in _questions()
    for state in ("`not_reached`", "`current`"):
        assert state in content, state


# --- each note read for every meaning (PRD AC-013, AC-014, AC-028)

def test_each_note_is_read_for_every_meaning():
    reading = _section(ROUNDS_MD.read_text("utf-8"), "## Read each note")
    for fact in ("every meaning", "another part", "cannot answer", "steer", "lean", "AR-05"):
        assert fact in reading, fact
    assert "| AR-05 |" in (SKILLS / "use-lavish" / "SKILL.md").read_text("utf-8")


# --- questions for others: how one joins the list (PRD AC-028, AC-029)

def test_a_question_joins_by_a_cannot_answer_note_or_an_accepted_proposal_card():
    found = _questions()
    for fact in ("cannot answer", "names who would", "origin: {note:", "propose it on a `confirm` card",
                 "only after the developer accepts that card", "origin: {card:", "adds nothing"):
        assert fact in found, fact
    origins = {key for option in SCHEMA["origin"]["anyOf"] for key in option["required"]}
    assert origins == {"note", "card"}


def test_each_part_of_a_question_for_others_is_named():
    found = _questions()
    parts = set(SCHEMA["question"]["properties"]) - ENGINE_FIELDS
    assert parts, "the schema names the parts of a question"
    for part in sorted(parts):
        assert f"| `{part}` |" in ROUNDS_MD.read_text("utf-8"), part
    assert "`several: true`" in found and "`everyone`" in found


def test_the_visible_text_of_a_question_names_no_internal_term():
    found = _questions()
    assert "no internal decision, no plan term and no id" in found
    assert "made up" in found


# --- order, and the round after an answer (PRD AC-035, AC-038, AC-042)

def test_order_and_the_round_after_an_answer():
    found = _questions()
    for fact in ("goes to the end", "`after`", "from the next round on", "`answer`", "`drop`", "`assume`",
                 "../use-lavish/ROUND-PASS.md"):
        assert fact in found, fact
    for fact in ("each settled or open point the answer touches returns as a `confirm` card", "`carries`",
                 "cause `answer_from`", "an answer from"):
        assert fact in found, fact
    assert parts_v2.CAUSES["answer_from"] == "an answer from"
    assert "answer_from" in SCHEMA["change_line"]["properties"]["cause"]["enum"]


# --- the open questions as Markdown (PRD AC-043)

def test_the_open_questions_print_as_markdown_in_order_filtered_by_role():
    found = _questions()
    for fact in ("as text", "Markdown", "open questions for others", "in list order", "`who`", "`everyone`",
                 "every part it holds", "No ids"):
        assert fact in found, fact


# --- a grill without a page (PRD AC-026; SDD §7 the no-page flow)

def test_without_a_page_the_grill_asks_round_by_round_in_chat_from_the_same_files():
    chat = _section(ROUNDS_MD.read_text("utf-8"), "## Without a page")
    for fact in ("round by round in chat", "only the context it needs", "`build`", "`raw_file`",
                 "engine/prompt_lines.py", "the same verdict"):
        assert fact in chat, fact
    assert (PLUGIN / "engine" / "prompt_lines.py").is_file()
    show = _step(5)
    assert '"Without a page"' in show and "with every card id" not in show


# --- coming back to a finished grill (PRD AC-048 to AC-052; SDD §7 the coming-back flow)

def test_coming_back_takes_the_finished_page_over_and_upgrades_an_old_page():
    start = _step(1)
    for fact in ("`takeover`", "Take over a page", "`afkv2.page/0`", "`afkv2.page/1`", "settled points",
                 "`upgrade: true`", "cause `finding`", '"Coming back"'):
        assert fact in start, fact
    assert "def finished_session(" in (HOME / "scripts" / "grill_start.py").read_text("utf-8")
    assert 'round_input.get("upgrade")' in (SKILLS / "use-lavish" / "scripts" / "round_document.py").read_text("utf-8")


def test_a_pass_after_a_take_over_names_stale_and_changed():
    """Consumes 0008: the 2 lists the end check answers after a take-over (decision D-26)."""
    back = _section(ROUNDS_MD.read_text("utf-8"), "## Coming back")
    for fact in ("`stale`", "possibly out of date", "`changed`", "stays settled unless the new input touches it",
                 "passes again"):
        assert fact in back, fact
    for document, skill in (("`PRD.md`", "to-prd"), ("`adr/requirements/`", "to-prd"),
                            ("`SDD.md`", "propose-solution"), ("`adr/design/`", "propose-solution"),
                            ("`plan/PLAN.md`", "to-subtasks")):
        assert document in back and f"/afkv2:{skill}" in back, document
        assert (SKILLS / skill / "SKILL.md").is_file(), skill
    gate = (HOME / "scripts" / "grill_log.py").read_text("utf-8")
    assert '"stale": _later_documents(' in gate and '"changed": _changed(' in gate
    assert '"Coming back"' in _step(9)


# --- the end check on a version 2 page (PRD AC-019, AC-044, AC-045)

def test_the_log_format_states_the_end_check_of_a_version_2_page():
    gate = _section(LOG_FORMAT_MD.read_text("utf-8"), "## Exit gate")
    for code in ("question-open", "drop-no-reason", "story-without-example", "kind-missing"):
        assert f"`{code}`" in gate, code
        assert f'"{code}"' in (HOME / "scripts" / "grill_log.py").read_text("utf-8"), code
    assert "answered, dropped with a reason or assumed" in gate


# --- the grill holds no page-layout rule (PRD AC-027)

LAYOUT = re.compile(r"section order|page order|goes first|\babove the\b|\bbelow the\b|folded|top of the page", re.I)


def test_the_grill_holds_no_page_layout_rule():
    for path in HOME.glob("*.md"):
        text = path.read_text("utf-8")
        assert not LAYOUT.search(text), (path.name, LAYOUT.search(text).group(0))
    assert re.search(r"^\| Kind \| Use it when \|$", ROUNDS_MD.read_text("utf-8"), re.M)
