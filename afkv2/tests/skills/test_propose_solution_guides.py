"""The design skill guides on the new flow (SDD §3 rows S-1, S-4, S-6 to S-8; SDD §14 row "second-provider slot").

SKILL.md names each command it runs in a fenced `sh step=...` block; these tests pin the steps of the ticket read, the
solution proposers, the side questions and the note copy, and run the proposers plan and the build through the stated
commands. The visualize guide shows a level section, a critical section and the caption rule (PRD AC-004, AC-008).
"""

import json
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parents[1]
SKILLS = PLUGIN / "skills"
SKILL_DIR = SKILLS / "propose-solution"
SKILL_MD = SKILL_DIR / "SKILL.md"
ASPECTS_MD = SKILL_DIR / "ASPECTS.md"
VISUALIZE_MD = SKILLS / "visualize" / "SKILL.md"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import design_round as dr  # noqa: E402
import proposers  # noqa: E402
import section_rules  # noqa: E402
from test_propose_solution import CAT_A, STEP, World, aspect_card, layer_card, round_of  # noqa: E402

FENCE = re.compile(r"```json fragment=(\w+)\n(.*?)\n```", re.S)


def _skill():
    return SKILL_MD.read_text("utf-8")


def _steps():
    return dict(STEP.findall(_skill()))


def _step(n):
    """The text of numbered step `n` of SKILL.md, up to the next numbered step."""
    text = _skill()
    start = re.search(rf"^{n}\. \*\*", text, re.M).start()
    stop = re.search(rf"^{n + 1}\. \*\*", text, re.M)
    return text[start:stop.start() if stop else len(text)]


def _verb(command, script):
    match = re.search(rf'/scripts/{script}" (\w+)', command)
    return match.group(1) if match else None


# --- step 2: the ticket read, passed to the build (PRD AC-036)

def test_step_2_reads_the_ticket_and_the_build_passes_it():
    steps = _steps()
    read = steps["read-ticket"]
    assert "../grill-requirements/scripts/read_ticket.py" in read and '--out "<ticket file>"' in read
    assert (SKILL_DIR / "../grill-requirements/scripts/read_ticket.py").resolve().is_file()
    assert "```sh step=read-ticket" in _step(2)
    assert '--ticket-file "<ticket file>"' in steps["build"]


def test_the_stated_build_shows_the_ticket_card_in_round_1(tmp_path):
    world = World(tmp_path)
    started = world.run("start", ticket_key="PROJ-1")
    ticket = world.file("ticket.json", {"key": "PROJ-1", "title": "Order export", "description": "Export orders."})
    world.run("build", doc=started["doc"], session=started["session"], ticket_key=started["ticket"],
              round_input=world.file("round.json", round_of(aspect_card("entities"))), ticket_file=ticket)
    items = world.doc(started)["rounds"][0]["items"]
    assert [item["id"] for item in items] == ["i-ticket", "a-entities"]


# --- step 3: the phase proposers, by plan, start, wait, critique, wait, cleanup (PRD AC-017)

PROPOSER_STEPS = ["proposers-plan", "proposers-start", "proposers-wait", "proposers-critique", "proposers-cleanup"]


def test_step_3_runs_each_proposers_verb_in_order():
    steps = _steps()
    assert [_verb(steps[name], "proposers.py") for name in PROPOSER_STEPS] == ["plan", "start", "wait", "critique",
                                                                                 "cleanup"]
    assert set(_verb(steps[name], "proposers.py") for name in PROPOSER_STEPS) == set(proposers.VERBS)
    step = _step(3)
    assert "| `proposers` |" in step and all(f"```sh step={name}" in step for name in PROPOSER_STEPS)
    order = [step.lower().index(f"run `{verb}`") for verb in ("plan", "start", "wait", "critique", "cleanup")]
    assert order == sorted(order) and "then `wait` again" in step
    assert '--brief "<brief>"' in steps["proposers-start"] and "--base" in steps["proposers-start"]


def test_step_3_reconciles_by_r_1_to_r_5():
    rows = re.findall(r"^ *\| (R-\d) ", _step(3), re.M)
    assert rows == ["R-1", "R-2", "R-3", "R-4", "R-5"]
    reconcile = next(line for line in _step(3).splitlines() if "| R-4 " in line)
    for fact in ("never the pane output", "both critiques accept in writing", "fork card", "`by`", "`cleanup`"):
        assert fact in reconcile, fact


def test_step_3_names_each_proposer_failure_the_script_records():
    sentence = next(line for line in _step(3).splitlines() if "is a proposer failure" in line)
    named = set(re.findall(r"`([a-z]+(?:-[a-z]+)+)`", sentence.split("is a proposer failure")[0]))
    assert named == proposers.FAILURES
    assert f"`{dr.PROPOSER_FAILED}`" in sentence


def test_step_3_points_at_the_herdr_playbook():
    link = re.search(r"\]\((\.\./herdr/SKILL\.md)\)", _step(3))
    assert link and (SKILL_DIR / link.group(1)).resolve().is_file()


def test_the_stated_plan_answer_goes_into_the_build_as_it_is(tmp_path):
    """Outside herdr the plan answers count 1; that answer is the `proposers` field the build takes (S-1, S-6)."""
    world = World(tmp_path)
    world.env["HERDR_ENV"] = "0"
    started = world.run("start", ticket_key="PROJ-1")
    world.build(started, round_of(*(aspect_card(key) for key in CAT_A)))
    world.run("present", doc=started["doc"], log=started["log"])
    world.accept_all(started)
    assert world.run("next", doc=started["doc"])["phase"] == "proposers"
    plan = world.run("proposers-plan", doc=started["doc"])
    assert plan["count"] == 1 and plan["reason"] in dr.SOLO_REASONS
    assert world.run("next", doc=started["doc"])["phase"] == "draft"
    world.build(started, {**round_of(layer_card("L1")), "proposers": plan})
    banner = world.doc(started)["rounds"][-1]["banner"]["settled"]
    assert any(dr.SOLO_REASONS[plan["reason"]] in line for line in banner), banner


# --- step 6: the side question; step 8: the note copy (PRD AC-037, AC-034)

def test_step_6_answers_a_side_question_and_keeps_the_round_open():
    step = _step(6)
    assert "btw?" in step and "The round stays open" in step
    assert "```sh step=reply" in step and 'page_round.py" reply' in _steps()["reply"]
    grill = dict(STEP.findall((SKILLS / "grill-requirements" / "SKILL.md").read_text("utf-8")))
    assert _steps()["reply"] == grill["reply"]


def test_step_8_copies_the_notes_into_the_log(tmp_path):
    assert "```sh step=sync" in _step(8)
    assert _verb(_steps()["sync"], "design_files.py") == "sync"
    world = World(tmp_path)
    started = world.run("start", ticket_key="PROJ-1")
    world.build(started, round_of(aspect_card("entities")))
    world.run("present", doc=started["doc"], log=started["log"])
    world.answer(started, "a-entities: note: Keep the order id.")
    answer = world.run("sync", doc=started["doc"], log=started["log"])
    assert answer["notes"] == 1
    assert '"Keep the order id."' in (world.repo / started["log"]).read_text("utf-8")


# --- no guide names the deleted second-provider slot (SDD §14)

def test_no_guide_names_the_second_provider_script():
    guides = [*SKILL_DIR.glob("*.md"), *(SKILLS / "visualize").rglob("*.md"), *(SKILLS / "herdr").glob("*.md")]
    named = [path.name for path in guides if re.search(r"second.provider", path.read_text("utf-8"), re.I)]
    assert not named, named
    assert "second-provider" not in _steps()


# --- the large-data aspect points to the performance section (PRD AC-014)

def test_the_large_data_aspect_points_to_the_performance_section():
    row = next(line for line in ASPECTS_MD.read_text("utf-8").splitlines() if "| `large-data` |" in line)
    assert "`sec-performance`" in row
    assert dr.group_keys("aspect")[-1] == "large-data"


# --- the visualize guide: a level section, a critical section, the caption rule (PRD AC-004, AC-006, AC-008)

def _guide_section(heading):
    """The text under `heading` up to the next heading of the same or a higher level."""
    text = VISUALIZE_MD.read_text("utf-8")
    start = text.index(heading + "\n") + len(heading)
    level = len(heading.split(" ", 1)[0])
    stop = re.search(rf"^#{{1,{level}}} ", text[start:], re.M)
    return text[start:start + stop.start()] if stop else text[start:]


def _fragment(heading):
    found = [(level, json.loads(body)) for level, body in FENCE.findall(_guide_section(heading))]
    assert len(found) == 1 and found[0][0] == "component", found
    return found[0][1]


def test_the_caption_rule_names_each_picture_type():
    rule = " ".join(_guide_section("## Captions").split())
    for part in ("1-line caption", '"What to see"', "`title`", "`caption`", "`section-caption`"):
        assert part in rule, part
    for kind in section_rules.PICTURES:
        assert f"`{kind}`" in rule, kind


@pytest.mark.parametrize("heading", ["### A level section", "### A critical section"])
def test_each_section_example_follows_the_section_rules(heading):
    body = _fragment(heading)
    level = {"id": "sec-l2", "body": _fragment("### A level section")}
    entry = level if heading == "### A level section" else {"id": "sec-crit-cancel", "body": body, "links": ["sec-l2"]}
    sections = [entry] if entry is level else [entry, level]
    assert section_rules.check_sections(sections) == []
    assert "../propose-solution/DRAFT.md" in _guide_section("## Design sections")
