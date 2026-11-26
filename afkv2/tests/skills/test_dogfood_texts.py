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
AFKV2_PANE_CODES = {"not-afkv2-pane", "bad-branch", "small-exists", "base-missing", "worktree-failed",
                    "note-unreadable", "note-check-failed", "already-sent", "main-pane-gone", "herdr-failed",
                    "state-unreadable", "usage"}


def flat(path):
    return " ".join(path.read_text("utf-8").split())


def section(path, heading):
    body = path.read_text("utf-8")
    start = body.index(heading)
    end = body.find("\n## ", start + len(heading))
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
    assert "each pane session" in question and "`feat/afkv2`" in question
    assert question.index("feat/afkv2") < question.index("worktree --lane small")
    body = flat(AGENT_MD)
    assert body.index("## The branch question") < body.index("/afkv2:small-change")


def test_agent_runs_a_small_ask_by_small_change_and_a_feature_ask_by_grill_requirements_in_a_medium_worktree():
    body = flat(AGENT_MD)
    assert "/afkv2:small-change" in body and "small-asks worktree" in body
    assert "/afkv2:grill-requirements" in body and "medium worktree" in body
    assert "worktree --lane medium" in body and "feat/afkv2-<ticket key" in body
    assert "grow" in body and "ticket key" in body


def test_agent_passes_the_confirmed_base_as_the_target_of_create_change_request():
    body = flat(AGENT_MD)
    assert "/afkv2:create-change-request" in body
    assert "target branch" in body and "confirmed base" in body
    assert "its own section" in body


# AGENT.md: the queue, the note and the redo delta (AC-012, AC-014, AC-016).

def test_agent_names_the_3_lead_lines_of_dogfood_py_verbatim():
    body = flat(AGENT_MD)
    for line in (dogfood.FORWARD_LINE, *dogfood.TELL_LINES.values()):
        assert f"`{line}`" in body, line


def test_agent_queues_a_new_ask_and_says_so_in_its_pane():
    body = flat(AGENT_MD)
    queue = body[body.index("**A new ask"):]
    queue = queue[:queue.index("**", len("**A new ask") + 2)]
    assert "queue" in queue and "pane" in queue and "milestone" in queue


def test_agent_sends_a_note_at_each_milestone_by_note_format_with_no_question_and_names_the_redo():
    body = flat(AGENT_MD)
    assert "[NOTE-FORMAT.md](NOTE-FORMAT.md)" in body
    assert "note --note-file" in body and "milestone" in body
    assert "no question" in body and "`redo`" in body
    assert "scratch" in body


def test_agent_wraps_up_with_a_push_each_draft_change_and_a_wrap_note():
    wrap = flat(AGENT_MD)
    wrap = wrap[wrap.index("**The wrap-up"):]
    assert "push" in wrap and "Draft change" in wrap and "kind: wrap" in wrap and "open-asks" in wrap


# AGENT.md: the bans (AC-013, AC-017).

def test_agent_bans_work_repository_writes_merges_and_prompts_to_other_panes():
    bans = section(AGENT_MD, "## Bans")
    assert "work repository" in bans and "Write nothing" in bans
    assert "Never merge" in bans
    assert "main pane" in bans and "no prompt" in bans and "note" in bans


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
    assert answers["worktree-medium"]["branch"] == "feat/afkv2-211"
