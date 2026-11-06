"""The grill's guides on version 2 (SDD §3 row "grill"; SDD §6 the moves of a question for others; SDD §7 the
meeting, coming-back and no-page flows; PLAN.md decision D-26).

The grill holds the content of a session: sections, stories, worked examples and questions for others. The quality
of the rules is proved by a dogfood run; these tests pin where each rule lives, that it agrees with the code, and
that the grill holds no page-layout rule.
"""

import ast
import inspect
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


def _raw(text, heading):
    """The text under `heading` up to the next heading of the same or a higher level, line by line."""
    level, title = heading.split(" ", 1)
    found = re.search(rf"^{level} +{re.escape(title.strip())}\n", text, re.M)
    assert found, f"no heading {heading!r}"
    rest = text[found.end():]
    stop = re.search(rf"^#{{1,{len(level)}}} ", rest, re.M)
    return rest[:stop.start()] if stop else rest


def _section(text, heading):
    """The text under `heading` up to the next heading of the same or a higher level, on 1 line."""
    return _flat(_raw(text, heading))


def _row(text, first_cell):
    """The 1 table row of `text` whose first cell is `first_cell`."""
    rows = [line for line in text.splitlines() if line.startswith(f"| {first_cell} |")]
    assert len(rows) == 1, (first_cell, rows)
    return rows[0]


def _step(n):
    """Step `n` of SKILL.md, up to the next step, on 1 line."""
    text = SKILL_MD.read_text("utf-8")
    start = re.search(rf"^{n}\. \*\*", text, re.M).start()
    stop = re.search(rf"^{n + 1}\. \*\*", text[start:], re.M)
    return _flat(text[start:start + stop.start()] if stop else text[start:])


def _questions_raw():
    return _raw(ROUNDS_MD.read_text("utf-8"), "### Questions for others")


def _questions():
    return _flat(_questions_raw())


def _content_raw():
    return _raw(ROUNDS_MD.read_text("utf-8"), "## The session's content")


# --- the content of a session lives in the page document (PRD AC-025; SDD §3 row "grill")

def test_the_session_content_names_each_list_of_the_page_document():
    content = _section(ROUNDS_MD.read_text("utf-8"), "## The session's content")
    for name in round_document.ENTRY_LISTS:
        assert f"`{name}`" in content, name
    kinds = SCHEMA["example"]["properties"]["kind"]["enum"]
    assert kinds == ["frequent", "edge", "risky"] and "its `kind` (frequent, edge or risky)" in content
    assert "with or without a page" in content
    assert "\"The session's content\"" in _step(4)


def test_the_guides_name_each_field_the_builder_requires_of_a_new_entry():
    """A new entry without a required field is refused by the document check (review findings f1, f17, f28): each
    list's row names its own fields; a part of a question is a row of the questions table."""
    content, parts = _content_raw(), _questions_raw()
    for name, kind in round_document.ENTRY_LISTS.items():
        row = _row(content, f"`{name}`")
        for field in sorted(set(SCHEMA[kind]["required"]) - {"id", "changes"}):
            if kind == "question" and field not in ENGINE_FIELDS:
                assert "always required" in _row(parts, f"`{field}`"), field
            else:
                assert f"`{field}`" in row, (name, field)
    assert "`state: open`" in _questions()
    for state in ("`not_reached`", "`current`"):
        assert state in _row(content, "`sections`"), state


def test_each_sent_entry_carries_its_own_id():
    """Review finding f15: `_merge_entries` refuses an entry with no `id` as `bad-entry`."""
    content = _flat(_content_raw())
    assert "Each entry you send carries an `id`" in content and "never reuse" in content
    builder = (SKILLS / "use-lavish" / "scripts" / "round_document.py").read_text("utf-8")
    assert 'raise Refusal("bad-entry", f"{kind}: an entry without an id' in builder


def test_a_merge_or_a_removal_of_a_section_points_to_the_page_skill():
    """Review finding f16: the schema takes `merged` and `removed`; the page skill holds their fields."""
    row = _row(_content_raw(), "`sections`")
    assert '"Sections and change lines" of `/afkv2:use-lavish`' in row
    states = SCHEMA["section"]["properties"]["state"]["enum"]
    assert {"merged", "removed"} <= set(states)
    for state in ("merge", "removal"):
        assert state in row, state
    page = (SKILLS / "use-lavish" / "SKILL.md").read_text("utf-8")
    assert "#### Sections and change lines\n" in page and "`merged_into`" in page


# --- each note read for every meaning (PRD AC-013, AC-014, AC-028)

def test_each_note_is_read_for_every_meaning():
    reading = _section(ROUNDS_MD.read_text("utf-8"), "## Read each note")
    for fact in ("Read each note for every meaning it holds", "| a thought about another part, or a new idea |",
                 "| the developer cannot answer, or names who would |", "| guidance for the whole session | a steer",
                 "is the developer's lean", "the section records it as a lean, not as settled",
                 "answer rule AR-05 of `/afkv2:use-lavish`"):
        assert fact in reading, fact
    assert "| AR-05 |" in (SKILLS / "use-lavish" / "SKILL.md").read_text("utf-8")


# --- questions for others: how one joins the list (PRD AC-028, AC-029)

def test_a_question_joins_by_a_cannot_answer_note_or_an_accepted_proposal_card():
    found = _questions()
    for fact in ("A note says the developer cannot answer, or names who would", "origin: {note:",
                 "propose it on a `confirm` card", "only after the developer accepts that card", "origin: {card:",
                 "A proposal card that stays open or gets another mark adds nothing"):
        assert fact in found, fact
    origins = {key for option in SCHEMA["origin"]["anyOf"] for key in option["required"]}
    assert origins == {"note", "card"}


def test_the_questions_heading_has_1_space():
    """Review finding f6."""
    assert "\n### Questions for others\n" in ROUNDS_MD.read_text("utf-8")


def test_each_part_of_a_question_for_others_is_named():
    """Review findings f7, f18, f27: each part is a row of the questions table, not of another table."""
    found, table = _questions(), _questions_raw()
    parts = set(SCHEMA["question"]["properties"]) - ENGINE_FIELDS
    assert parts, "the schema names the parts of a question"
    for part in sorted(parts):
        _row(table, f"`{part}`")
    assert "`several` is `true`" in found and "`everyone`" in found


RULE = "The text names no internal decision, no plan term and no id"
# An id of the page or the plan: R-2, N-2-i-x, AR-05, D-26, AC-028, i-format, s-intro, q-1.
PAGE_ID = re.compile(r"\b(?:[A-Z]{1,3}-\d+|[a-z]{1,2}-[a-z0-9][\w-]*)\b")


def test_the_visible_text_of_a_question_names_no_internal_term():
    """Review finding f11: the rule stands, and the section's own text holds no id."""
    found = _questions()
    assert RULE in found
    assert "Explain a term this session made up where it first appears" in found
    rest = re.sub(r"answer rule AR-\d\d of `/afkv2:use-lavish`", "", found.replace(RULE, ""))
    assert not PAGE_ID.search(rest), PAGE_ID.search(rest).group(0)
    assert PAGE_ID.search("a follow-up of N-2-i-format") and not PAGE_ID.search("a sign-off of a follow-up")


# --- order, and the round after an answer (PRD AC-035, AC-038, AC-042)

def test_order_and_the_round_after_an_answer():
    """Review findings f4, f5: the page skill holds the order and AR-08, the round pass holds `answer_from`; the
    grill keeps only its own actions."""
    found = _questions()
    page = (SKILLS / "use-lavish" / "SKILL.md").read_text("utf-8")
    assert "A new question goes to the end; a follow-up goes right after the question it follows, by `after`" in page
    assert "| AR-08 | Update every point the change touches" in page
    assert '"The questions block" of `/afkv2:use-lavish`' in found
    for fact in ("To place a follow-up, send it with `after`", "send the question again with `after`",
                 "from the next round on", "`answer`, `drop` and `assume`", "../use-lavish/ROUND-PASS.md",
                 "answer rule AR-08 of `/afkv2:use-lavish`", "the `answer` reading",
                 "give each point it touches a `confirm` card"):
        assert fact in found, fact
    for gone in ("goes to the end", "goes right after", "each section the answer changes",
                 "with `carries` naming its old card"):
        assert gone not in found, gone
    round_pass = _flat((SKILLS / "use-lavish" / "ROUND-PASS.md").read_text("utf-8"))
    assert "change line with cause `answer_from`" in round_pass
    assert parts_v2.CAUSES["answer_from"] == "an answer from"
    assert "answer_from" in SCHEMA["change_line"]["properties"]["cause"]["enum"]


def test_a_section_changed_by_an_assumed_answer_takes_cause_answer():
    """Review finding f26: `answer_from` needs an answered question; an assumed one is `assumed`."""
    assert "takes a change line with cause `answer` and the accepted `card`" in _questions()
    rules = (PLUGIN / "engine" / "schema" / "invariants.py").read_text("utf-8")
    assert '"answer": "card"' in rules
    assert 'line["cause"] == "answer_from" and asked is not None and asked["state"] != "answered"' in rules


# --- the open questions as Markdown (PRD AC-043)

def test_the_open_questions_print_as_markdown_in_order_filtered_by_role():
    found = _questions()
    for fact in ("**As text.**", "print the open questions for others as Markdown in chat", "in list order",
                 "only the questions whose `who` holds that role or `everyone`", "with every part it holds",
                 "No ids: a link names its section by title"):
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
    assert "def _upgrade(" in (SKILLS / "use-lavish" / "scripts" / "round_document.py").read_text("utf-8")


def test_the_upgrade_rule_covers_a_resume_and_a_take_over():
    """Review finding f3: a resumed old-schema page needs `upgrade: true` as well."""
    assert "On a resume and on a take-over, a page whose `schema` is `afkv2.page/0` or `afkv2.page/1`" in _step(1)


def test_a_take_over_keeps_the_round_0_words_of_the_first_run(tmp_path):
    """Review finding f23: `Round 0` is a single row, so a second `row` replaces it."""
    assert "After a take-over, write its old words first, then a blank line and the new input" in _step(3)
    import grill_log
    assert "Round 0" in grill_log.SINGLE_KINDS
    log = tmp_path / "GRILL-LOG.md"
    grill_log.ensure_section(log, "T-1")
    grill_log.write_row(log, "Round 0", "first")
    grill_log.write_row(log, "Round 0", "second")
    rows = [line for line in log.read_text("utf-8").splitlines() if line.startswith("- Round 0: ")]
    assert rows == ['- Round 0: "second"']


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
    # review finding f6: both lists come on every pass, so an empty list means nothing, not "not computed"
    for text in (back, _step(9)):
        assert "Every pass of `gate` answers `stale` and `changed`" in text and "each list that is not empty" in text
        assert "after a take-over, the answer adds" not in text.casefold()


# --- the end check on a version 2 page (PRD AC-019, AC-044, AC-045)

END_CHECK = {  # each code of the version 2 end check, with a page part that fails it and one that passes
    "question-open": ({"questions": [{"id": "q-1", "question": "Which?", "who": ["tester"], "state": "open"}]},
                      {"questions": [{"id": "q-1", "question": "Which?", "who": ["tester"], "state": "answered"}]}),
    "drop-no-reason": ({"questions": [{"id": "q-1", "question": "Which?", "who": ["tester"], "state": "dropped",
                                       "dropped": {"reason": " "}}]},
                       {"questions": [{"id": "q-1", "question": "Which?", "who": ["tester"], "state": "dropped",
                                       "dropped": {"reason": "out of scope"}}]}),
    "story-without-example": ({"stories": [{"id": "st-1", "text": "Import a file."}], "examples": []},
                              {"stories": [{"id": "st-1", "text": "Import a file."}],
                               "examples": [{"id": f"ex-{k}", "title": k, "kind": k, "stories": ["st-1"]}
                                            for k in ("frequent", "edge", "risky")]}),
    "kind-missing": ({"examples": [{"id": "ex-1", "title": "a", "kind": "frequent", "stories": []}]},
                     {"examples": [{"id": f"ex-{k}", "title": k, "kind": k, "stories": []}
                                   for k in ("frequent", "edge", "risky")]}),
}


def test_the_log_format_states_the_end_check_of_a_version_2_page():
    """Review findings f15, f20: the check raises each code the format states, under the condition it names."""
    import grill_log
    gate = _section(LOG_FORMAT_MD.read_text("utf-8"), "## Exit gate")
    for code, (failing, passing) in END_CHECK.items():
        assert f"`{code}`" in gate, code
        assert any(line.startswith(f"{code}: ") for line in grill_log._v2_failures(failing)), code
        assert not grill_log._v2_failures(passing), (code, grill_log._v2_failures(passing))
    assert "answered, dropped with a reason or assumed" in gate


# --- the grill holds no page-layout rule (PRD AC-027)

LAYOUT = re.compile(r"section order|page order|goes first|first on the page|\babove the\b|\bbelow the\b|folded|"
                    r"collapsed|\bsidebar\b|\bat the (?:top|bottom)\b|(?:top|bottom|side) of the page|"
                    r"the engine puts|\b(?:left|right) column\b", re.I)


def test_the_grill_holds_no_page_layout_rule():
    """Review findings f10, f21: every .md under the grill folder, subfolders included."""
    found = [(path.relative_to(HOME).as_posix(), LAYOUT.search(path.read_text("utf-8")).group(0))
             for path in sorted(HOME.rglob("*.md")) if LAYOUT.search(path.read_text("utf-8"))]
    assert not found, found
    for phrase in ("at the top", "collapsed", "in the sidebar", "the engine puts the maps"):
        assert LAYOUT.search(phrase), phrase


def test_the_grill_holds_the_card_kind_table():
    assert re.search(r"^\| Kind \| Use it when \|$", ROUNDS_MD.read_text("utf-8"), re.M)


# --- the shapes the builder refuses (review findings f12, f13, f14)

def _part_row(part):
    return _row(_questions_raw(), f"`{part}`")


def test_each_required_part_of_a_question_is_marked_required():
    required = set(SCHEMA["question"]["required"]) - ENGINE_FIELDS
    assert required >= {"who", "question", "context", "why"}
    for part in sorted(set(SCHEMA["question"]["properties"]) - ENGINE_FIELDS):
        assert ("always required" in _part_row(part)) == (part in required), part


def test_the_choices_row_states_the_shape_the_schema_takes():
    row = _part_row("choices")
    shape = SCHEMA["choices"]
    assert set(shape["required"]) == {"options", "several"}
    assert set(SCHEMA["option"]["required"]) == {"id", "text"}
    options = shape["properties"]["options"]
    for fact in ("`options`", "`id`", "`text`", "`several`", f"{options['minItems']} to {options['maxItems']}"):
        assert fact in row, fact


def test_without_a_page_each_round_is_still_checked_and_scanned_but_a_chat_round_opens_no_page():
    """Review findings f24 and r1-g5-1: each round is checked, rendered and scanned for secrets. A chat round the
    developer asked for runs the engine's check and render without show: show opens the page, and on Codex it
    writes the waiting record that makes the Stop hook wait for a page send."""
    raw = _raw(ROUNDS_MD.read_text("utf-8"), "## Without a page")
    chat = _flat(raw)
    for fact in ("`build` still runs each round", "`present` already checked and rendered the round",
                 "scanned the page and the log for secrets", "do not run `present`", "Stop hook",
                 "Do not run `build --replace` on a round you asked in chat"):
        assert fact in chat, fact
    assert "the page still opens" not in chat
    present = (SKILLS / "use-lavish" / "scripts" / "page_round.py").read_text("utf-8")
    assert '_engine("check", doc)' in present and '"--scan"' in present and '_engine("show", doc)' in present
    import engine
    assert "launcher.write_waiting_record" in inspect.getsource(engine.cmd_show)
    assert "write_waiting_record" not in inspect.getsource(engine.cmd_render)
    lines = re.findall(r'^<python> "<this skill\'s folder>/\.\./\.\./engine/engine\.py" (.+)$', raw, re.M)
    assert len(lines) == 2, lines
    parsed = [engine._parser().parse_args([part.strip('"') for part in line.split()]) for line in lines]
    assert [args.handler for args in parsed] == [engine.cmd_check, engine.cmd_render]
    assert all(args.document == "<doc>" for args in parsed)
    assert parsed[1].notices and parsed[1].scan == ["<log>"]


def test_without_a_page_the_reply_file_names_its_round_and_the_mark_words():
    """Review finding f25: format 1 opens with `[round R-n]`; a mark is `<element id> <mark>`."""
    chat = _section(ROUNDS_MD.read_text("utf-8"), "## Without a page")
    for fact in ("The first line is `[round R-<n>]`", "A mark is a line `<card id> <mark>`",
                 "`MARKS` in `engine/ingest.py`", "an option of a `debate` card is its letter"):
        assert fact in chat, fact
    tree = ast.parse((PLUGIN / "engine" / "ingest.py").read_text("utf-8"))
    marks = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                 and any(getattr(target, "id", None) == "MARKS" for target in node.targets))
    assert {key.value for key in marks.keys} == set(SCHEMA["item"]["properties"]["kind"]["enum"])
    grammar = (PLUGIN / "engine" / "prompt_lines.py").read_text("utf-8")
    assert "first line `[round R-n]`. A mark is `<element id> <mark>`" in _flat(grammar)


def test_without_a_page_the_open_questions_for_others_are_asked_and_answered_in_chat():
    chat = _section(ROUNDS_MD.read_text("utf-8"), "## Without a page")
    for fact in ("each open question for others", "`<question id> tick <option id>`", "a note on the question"):
        assert fact in chat, fact
    grammar = (PLUGIN / "engine" / "prompt_lines.py").read_text("utf-8")
    assert "`<question id> tick <option id> <option id> ...`" in grammar
