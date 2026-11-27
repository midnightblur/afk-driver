"""The dogfood SKILL.md, read by the main agent: its refusal map, its command blocks against `dogfood.main` with the
fake runner, the 1 exception to playbook rule H-8, feedback, the apply pointer, the wrap-up, and unique names."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[2]
SKILL_DIR = AFKV2 / "skills" / "dogfood"
SKILL_MD = SKILL_DIR / "SKILL.md"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "fakes"))
sys.path.insert(0, str(AFKV2 / "scripts"))

import dogfood  # noqa: E402
import plugin_check  # noqa: E402
from dogfood_runner import DogfoodFakeRunner  # noqa: E402

MAIN = "w1:p1"
STEP = re.compile(r"^ *```sh step=([\w-]+)\n *(.*?)\n *```", re.S | re.M)
MAIN_VERBS = {"start", "status", "tell", "check-note", "close"}
AFKV2_PANE_CODES = {"not-afkv2-pane", "small-exists", "bad-branch", "base-missing", "worktree-failed",
                    "already-sent", "main-pane-gone"}


def text():
    return SKILL_MD.read_text("utf-8")


def steps():
    return dict(STEP.findall(text()))


def section(heading):
    body = text()
    start = body.index(heading)
    end = body.find("\n## ", start + len(heading))
    return body[start:end if end != -1 else len(body)]


def refusal_rows():
    """{code: (meaning, next action)} of the Refusals table."""
    rows = {}
    for line in section("## Refusals").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0].startswith("`"):
            rows[cells[0].strip("`")] = (cells[1], cells[2])
    return rows


# The refusal map (VR-021: AC-002, AC-003).

def test_the_refusals_map_outside_herdr_no_source_and_source_broken_to_their_repairs():
    rows = refusal_rows()
    assert "start herdr" in rows["outside-herdr"][1] and "again" in rows["outside-herdr"][1]
    for code in ("no-source", "source-broken"):
        assert "/afkv2:setup" in rows[code][1] and "again" in rows[code][1]
    assert "starts nothing" in section("## Refusals")


def test_every_refusal_a_main_pane_verb_can_answer_has_a_row():
    source = (SKILL_DIR / "scripts" / "dogfood.py").read_text("utf-8")
    raised = set(re.findall(r'Refusal\(\s*"([a-z-]+)"', source)) | {"usage"}
    assert raised - AFKV2_PANE_CODES - set(refusal_rows()) == set()


# The command blocks (VR-021): each runs against main with the fake runner, with no argument error.

@pytest.fixture
def world(tmp_path):
    source = tmp_path / "plugin source"
    (source / "afkv2" / ".claude-plugin").mkdir(parents=True)
    (source / "afkv2" / ".claude-plugin" / "plugin.json").write_text('{"name": "afkv2"}', encoding="utf-8")
    env = {"HERDR_ENV": "1", "HERDR_PANE_ID": MAIN, "LOCALAPPDATA": str(tmp_path / "local"),
           "ProgramFiles": str(tmp_path / "program files")}
    data = tmp_path / "local" / "afkv2"
    data.mkdir(parents=True)
    (data / "install.txt").write_text(f"installed 2026-11-26T00:00:00+00:00\nsource {source}\n", encoding="utf-8")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    files = {"ask file": "Make step 4 of small-change clearer.",
             "text file": "The trial failed: KeyError 'lane' at line 12 of the output.",
             "note file": "afkv2-note v1\nkind: wrap\nask: step 4\nchanges:\n- https://x/pull/1 | feat/x | step 4\n"
                          "open-asks: none\n"}
    for name, body in files.items():
        (scratch / name.replace(" ", "-")).write_text(body, encoding="utf-8")
    return {"env": env, "data": data, "scratch": scratch, "runner": DogfoodFakeRunner(env)}


def argv_of(step, world):
    """The arguments after the script path of 1 command block, its placeholders filled."""
    command = steps()[step]
    for name in ("ask file", "text file", "note file"):
        command = command.replace(f"<{name}>", (world["scratch"] / name.replace(" ", "-")).as_posix())
    command = command.replace("<python>", "python").replace("<this skill's folder>", SKILL_DIR.as_posix())
    assert not re.findall(r"<[^<>]+>", command), f"{step}: unfilled placeholder"
    parts = shlex.split(command)
    assert parts[0] == "python" and Path(parts[1]) == SKILL_DIR / "scripts" / "dogfood.py", step
    return parts[2:]


def run(step, world):
    out = []
    code = dogfood.main(argv_of(step, world), world["env"], world["runner"], out=out.append)
    answer = json.loads(out[0])
    assert answer.get("error", {}).get("code") != "usage", (step, answer)
    return code, answer


def test_the_blocks_name_only_main_pane_verbs_and_cover_each():
    verbs = {shlex.split(command)[2] for command in steps().values()}
    assert verbs == MAIN_VERBS


def test_each_command_block_runs_against_main_with_the_fake_runner(world):
    assert set(steps()) == {"start", "status", "check-note", "feedback", "wrap", "close", "close-force"}
    assert run("close-force", world) == (0, {"ok": True, "pane_closed": False, "worktrees": [], "branches": []})
    code, opened = run("start", world)
    assert code == 0 and opened["status"] == "opened"
    assert run("status", world)[1]["state"]["agent"] == opened["agent"]
    for step, kind in (("feedback", "feedback"), ("wrap", "wrap")):
        assert run(step, world) == (0, {"ok": True, "sent": True, "kind": kind})
    code, checked = run("check-note", world)
    assert code == 0 and checked["note"]["kind"] == "wrap"
    state_file = world["data"] / f"dogfood-{MAIN.replace(':', '_')}.json"
    state = json.loads(state_file.read_text("utf-8"))
    state_file.write_text(json.dumps({**state, "wrap_reported": True}), encoding="utf-8")
    code, closed = run("close", world)
    assert code == 0 and closed["pane_closed"] is True and not state_file.exists()


# The 1 exception to playbook rule H-8 (VR-055: AC-029).

def test_the_skill_states_the_1_exception_to_playbook_rule_h8():
    body = " ".join(text().split())
    assert "H-8" in body and "../herdr-playbook/SKILL.md" in body
    assert "the afkv2 pane stays open after each milestone and each result until the wrap-up" in body
    assert "herdr pane close" not in body


# Feedback, the apply pointer and the wrap-up (AC-025, AC-027).

def test_feedback_goes_by_tell_with_the_evidence():
    step = section("## Steps")
    feedback = step[step.index("**Feedback"):]
    feedback = feedback[:feedback.index("\n\n", feedback.index("step=feedback"))]
    assert "evidence" in feedback and "tell --kind feedback" in steps()["feedback"]


def test_a_note_is_checked_then_applied_by_apply_md():
    step = section("## Steps")
    note = step[step.index("**A note"):]
    assert note.index("step=check-note") < note.index("APPLY.md")
    assert "[APPLY.md](APPLY.md)" in note


def test_the_wrap_request_ends_the_turn_and_the_wrap_note_closes():
    body = text()
    request = body[body.index("**Wrap-up"):body.index("**The wrap note")]
    assert "step=wrap" in request and "step=close" not in request and "ends" in request
    wrap_note = section("**The wrap note")
    assert "open ask" in wrap_note and wrap_note.index("Draft change") < wrap_note.index("step=close")
    note = body[body.index("**A note"):body.index("**Feedback")]
    assert "`kind` `wrap`: step 6" in note


def test_an_undelivered_prompt_is_not_sent_again():
    body = " ".join(text().split())
    assert "`submitted` `false`" in body and "`sent` `unconfirmed`" in body
    assert "send nothing again" in body and "look at the afkv2 pane" in body


def test_the_wrap_up_tells_wrap_then_closes():
    body = text()
    assert body.index("step=wrap") < body.index("step=close\n") < body.index("step=close-force")
    assert "tell --kind wrap" in steps()["wrap"] and steps()["close"].endswith("close")


# The plugin check and unique names (VR-022).

def test_the_skill_passes_the_plugin_check_and_its_modules_have_unique_names():
    head = text().split("\n")[:3]
    assert head[0] == "---" and head[1] == "name: dogfood" and head[2].startswith("description: /afkv2:dogfood")
    assert plugin_check.run_checks() == []
    tree = subprocess.run(["git", "-C", str(AFKV2.parent), "ls-files"], capture_output=True, text=True,
                          check=True).stdout.splitlines()
    names = [Path(path).name for path in tree]
    for name in ("dogfood.py", "dogfood_note.py", "test_dogfood_skill.py", "test_dogfood_start.py",
                 "test_dogfood_note.py", "test_dogfood_pane_verbs.py", "test_dogfood_main_verbs.py"):
        assert names.count(name) == 1, name
