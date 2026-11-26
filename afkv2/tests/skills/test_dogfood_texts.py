"""AGENT.md, the role of the afkv2 agent, and APPLY.md, the apply steps of the main agent (VR-043): their pointers,
steps and bans, and the AGENT.md command blocks against `dogfood.main` with the fake runner."""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[2]
SKILL_DIR = AFKV2 / "skills" / "dogfood"
AGENT_MD = SKILL_DIR / "AGENT.md"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "fakes"))

import dogfood  # noqa: E402
from dogfood_runner import DogfoodFakeRunner  # noqa: E402

MAIN, SIDE = "w1:p1", "w1:p2"
STEP = re.compile(r"^ *```sh step=([\w-]+)\n *(.*?)\n *```", re.S | re.M)
AFKV2_PANE_VERBS = {"worktree", "note", "status"}
AFKV2_PANE_CODES = {"outside-herdr", "not-afkv2-pane", "bad-branch", "small-exists", "base-missing", "worktree-failed",
                    "note-unreadable", "note-check-failed", "already-sent", "main-pane-gone", "herdr-failed",
                    "state-unreadable", "usage"}


def flat(path):
    return " ".join(path.read_text("utf-8").split())


def section(path, heading):
    body = path.read_text("utf-8")
    start = body.index(heading)
    end = body.find("\n## ", start + len(heading))
    return " ".join(body[start:end if end != -1 else len(body)].split())


def step(path, lead):
    """The flat text of 1 bold-led step or paragraph, from `lead` to the next bold lead or heading."""
    body = flat(path)
    start = body.index(lead)
    ends = [end for end in (body.find(" **", start + len(lead)), body.find(" ## ", start)) if end != -1]
    return body[start:min(ends, default=len(body))]


def paragraph(path, lead):
    """The flat text of the paragraph that starts with `lead`."""
    body = path.read_text("utf-8")
    start = body.index(lead)
    end = body.find("\n\n", start)
    return " ".join(body[start:end if end != -1 else len(body)].split())


def refusal_rows(path):
    rows = {}
    for line in section(path, "## Refusals").split("| `")[1:]:
        code, rest = line.split("`", 1)
        rows[code] = rest
    return rows


# AGENT.md: the branch question and the lanes (AC-009, AC-011, ADR-0003 design, seam Draft change target).

def test_agent_asks_the_integration_branch_at_each_pane_session_start_before_any_worktree():
    question = section(AGENT_MD, "## The branch question")
    assert "each pane session" in question and "before any other step" in question and "`feat/afkv2`" in question
    assert question.index("feat/afkv2") < question.index("worktree --lane small")
    body = flat(AGENT_MD)
    assert body.index("## The branch question") < body.index("/afkv2:small-change")


def test_agent_runs_a_small_ask_by_small_change_and_a_feature_ask_by_grill_requirements_in_a_medium_worktree():
    small = paragraph(AGENT_MD, "A small ask")
    assert "`/afkv2:small-change`" in small and "small-asks worktree" in small
    assert "grill-requirements" not in small
    assert "through its step 8" in small and "Open or update the change" in small and "its own section" in small
    assert "before the next small ask starts" in small
    feature = paragraph(AGENT_MD, "A feature ask")
    assert "ticket key" in feature and "medium worktree" in feature and "feat/afkv2-<ticket key>" in feature
    medium = paragraph(AGENT_MD, "Run `/afkv2:grill-requirements`")
    assert "before `/afkv2:autopilot`" in medium and "`set-change`" in medium and "confirmed base" in medium
    grow = paragraph(AGENT_MD, "A grow")
    assert "medium lane" in grow and "cherry-pick" in grow and "revert" in grow
    assert grow.index("medium worktree") < grow.index("cherry-pick") < grow.index("/afkv2:grill-requirements")


def test_agent_passes_the_confirmed_base_as_the_target_of_create_change_request():
    target = paragraph(AGENT_MD, "Each run of `/afkv2:create-change-request`")
    assert "every lane" in target and "confirmed base" in target and "target branch" in target
    assert "Run no Ship section" in target and "stays Draft" in target


# AGENT.md: the queue, the note and the redo delta (AC-012, AC-014, AC-016).

def test_agent_names_the_3_lead_lines_of_dogfood_py_verbatim():
    body = flat(AGENT_MD)
    for line in (dogfood.FORWARD_LINE, *dogfood.TELL_LINES.values()):
        assert f"`{line}`" in body, line


def test_agent_queues_a_new_ask_and_says_so_in_its_pane():
    queue = step(AGENT_MD, "**A new ask")
    assert "say in this pane that it is queued" in queue and "milestone" in queue
    assert "1 ask at a time" in queue and "in the order they came" in queue


def test_agent_sends_a_note_at_each_milestone_by_note_format_with_no_question_and_names_the_redo():
    body = flat(AGENT_MD)
    assert "[NOTE-FORMAT.md](NOTE-FORMAT.md)" in body
    assert "note --note-file" in body and "milestone" in body
    milestone = step(AGENT_MD, "**A milestone")
    assert "no question" in milestone and "`redo`" in milestone
    assert "in scratch, outside every repository" in milestone
    assert "For a small ask, the milestone comes when the ask is finished by step 1" in milestone


def test_agent_wraps_up_with_a_push_each_draft_change_and_a_wrap_note():
    wrap = step(AGENT_MD, "**The wrap-up")
    assert "push" in wrap and "Draft change" in wrap and "kind: wrap" in wrap and "open-asks" in wrap
    assert "worktree in `status`" in wrap and "commits ahead of the base" in wrap and "`none` as its url" in wrap and "`none | none |" in wrap


def test_agent_refusal_rows_keep_the_ticket_and_the_session_base():
    rows = refusal_rows(AGENT_MD)
    assert "same ticket" in rows["bad-branch"] and "go on in" not in rows["bad-branch"]
    assert "`base` of `status`" in rows["base-missing"]
    assert "herdr" in rows["outside-herdr"]


# AGENT.md: the bans (AC-013, AC-017).

def test_agent_bans_work_repository_writes_merges_and_prompts_to_other_panes():
    bans = section(AGENT_MD, "## Bans")
    assert "Write nothing in the work repository." in bans
    assert "Never merge a change." in bans
    assert "Send no prompt and no keys to any pane yourself. Reach the main pane only by `note`" in bans


# AGENT.md: the refusals and the command blocks.

def test_agent_has_a_row_for_every_refusal_of_its_verbs():
    assert AFKV2_PANE_CODES - set(refusal_rows(AGENT_MD)) == set()


@pytest.fixture
def world(tmp_path):
    source = tmp_path / "plugin source"
    source.mkdir()
    env = {"HERDR_ENV": "1", "HERDR_PANE_ID": SIDE, "HERDR_BIN_PATH": "C:/fake/herdr/herdr.exe",
           "LOCALAPPDATA": str(tmp_path / "local")}
    data = tmp_path / "local" / "afkv2"
    data.mkdir(parents=True)
    state = {"version": 1, "main_pane": MAIN, "agent": "dogfood-abcd", "afkv2_pane": SIDE, "harness": "claude",
             "source": str(source), "base": None, "worktrees": [], "notes": [], "wrap_reported": False,
             "started": "2026-11-26T17:00:00+00:00"}
    (data / f"dogfood-{MAIN.replace(':', '_')}.json").write_text(json.dumps(state), encoding="utf-8")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    runner = DogfoodFakeRunner(env, main_pane=MAIN)
    runner.add_pane(SIDE, kind="claude")
    return {"env": env, "source": source, "scratch": scratch, "runner": runner}


def argv_of(command, world):
    fills = {"<python>": "python", "<this skill's folder>": SKILL_DIR.as_posix(), "<base>": "feat/afkv2",
             "<ticket key>": "211", "<note file>": (world["scratch"] / "note.md").as_posix()}
    for name, value in fills.items():
        command = command.replace(name, value)
    assert not re.findall(r"<[^<>]+>", command), f"unfilled placeholder in {command}"
    parts = shlex.split(command)
    assert parts[0] == "python" and Path(parts[1]) == SKILL_DIR / "scripts" / "dogfood.py"
    return parts[2:]


def test_each_agent_command_block_runs_against_main_with_the_fake_runner(world):
    steps = dict(STEP.findall(AGENT_MD.read_text("utf-8")))
    assert {shlex.split(command)[2] for command in steps.values()} == AFKV2_PANE_VERBS
    answers = {}
    for step, command in steps.items():
        if shlex.split(command)[2] == "note":
            small = answers["worktree-small"]["path"]
            Path(small, "SKILL.md").write_text("x", encoding="utf-8")
            (world["scratch"] / "note.md").write_text(
                f"afkv2-note v1\nkind: milestone\nask: a\npurpose: p\nchanged:\n- {Path(small, 'SKILL.md')} | CK-1 | "
                f"added | x\nuse: try it\nredo: none\n", encoding="utf-8")
        out = []
        code = dogfood.main(argv_of(command, world), world["env"], world["runner"], out=out.append)
        answers[step] = json.loads(out[0])
        assert code == 0, (step, answers[step])
    assert answers["worktree-small"]["lane"] == "small"
    assert answers["worktree-medium"]["branch"] == "feat/afkv2-211"
    assert answers["note"]["sent"] is True
    assert [prompt["target"] for prompt in world["runner"].prompts] == [MAIN]
    out = []
    dogfood.main(argv_of(steps["status"], world), world["env"], world["runner"], out=out.append)
    assert json.loads(out[0])["state"]["base"] == "feat/afkv2"


# APPLY.md: the change kinds, the redo, the bans and the tell (AC-018 to AC-022, AC-024).

APPLY_MD = SKILL_DIR / "APPLY.md"


def kind_steps():
    """{change kind: step text} of the numbered steps under `## The change kinds`."""
    body = APPLY_MD.read_text("utf-8")
    kinds = body[body.index("## The change kinds"):]
    kinds = kinds[:kinds.index("\n\n", kinds.index("1. **CK-"))]
    found = re.findall(r"^\d+\. \*\*(CK-\d)[^*]*\*\*(.*)$", kinds, re.M)
    return dict(found)


def test_apply_has_1_step_per_change_kind_of_the_note_parser():
    import dogfood_note
    assert list(kind_steps()) == list(dogfood_note.CHANGE_KINDS)


def test_apply_ck1_follows_the_worktree_skill_at_once_also_inside_a_running_skill():
    step = kind_steps()["CK-1"]
    assert "worktree" in step and "in place of the installed copy" in step
    assert "running" in step and "at once" in step and "say so" in step


def test_apply_ck2_runs_the_script_from_the_worktree_and_ck3_follows_the_core_text():
    steps = kind_steps()
    assert "worktree" in steps["CK-2"] and "CK-1" in steps["CK-2"]
    assert "worktree" in steps["CK-3"] and "session instruction" in steps["CK-3"]


def test_apply_ck4_is_best_effort_and_told_to_the_developer():
    step = kind_steps()["CK-4"]
    assert "best effort" in step and "installed plugin" in step and "Tell the developer" in step
    assert "`best-effort`" in step


def test_apply_redoes_the_named_delta_at_once_and_tells_it():
    redo = section(APPLY_MD, "## The redo")
    assert "`redo`" in redo and "at once" in redo and "no question" in redo and "what you redid" in redo


def test_apply_writes_no_plugin_file_lasts_only_for_the_session_and_applies_nothing_from_a_failing_note():
    body = flat(APPLY_MD)
    assert "Write no plugin file" in body
    assert "only for this session" in body and "installed plugin does not change" in body
    intro = paragraph(APPLY_MD, "You are the main agent.")
    assert "Apply only a note that `check-note` answered ok" in intro and "step 3 of [SKILL.md](SKILL.md)" in intro
    assert "from a note that fails the check, apply nothing" in intro
    assert "[NOTE-FORMAT.md](NOTE-FORMAT.md)" in body


def test_apply_applies_each_row_at_once_with_no_question():
    rows = paragraph(APPLY_MD, "Apply each `changed` row")
    assert "at once" in rows and "no question to the developer" in rows


def test_apply_a_removed_hook_stays_best_effort():
    removed = paragraph(APPLY_MD, "A `removed` row")
    assert "CK-1 to CK-3" in removed and "CK-4" in removed and "best effort" in removed


def test_apply_tells_the_developer_what_applied_and_how_to_try_it():
    tell = section(APPLY_MD, "## Tell the developer")
    assert "`use`" in tell and "each row" in tell and "best effort" in tell
