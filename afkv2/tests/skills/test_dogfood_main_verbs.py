"""dogfood.py tell, check-note and close, the verbs of the main pane, and the pane guard on all 7 verbs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AFKV2 / "skills" / "dogfood" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "fakes"))

import dogfood  # noqa: E402
from dogfood_runner import DogfoodFakeRunner, herdr_error  # noqa: E402

MAIN, SIDE, THIRD = "w1:p1", "w1:p2", "w1:p3"
AGENT = "dogfood-abcd"


@pytest.fixture
def world(tmp_path):
    """The env of the main pane, the state file of a live session with 1 worktree, and a text file."""
    source = tmp_path / "plugin source"
    source.mkdir()
    worktree = tmp_path / "wt"
    (worktree / "skills").mkdir(parents=True)
    (worktree / "skills" / "SKILL.md").write_text("x\n", encoding="utf-8")
    env = {"HERDR_ENV": "1", "HERDR_PANE_ID": MAIN, "HERDR_BIN_PATH": "C:/fake/herdr/herdr.exe",
           "LOCALAPPDATA": str(tmp_path / "local")}
    data = tmp_path / "local" / "afkv2"
    data.mkdir(parents=True)
    state = {"version": 1, "main_pane": MAIN, "agent": AGENT, "afkv2_pane": SIDE, "harness": "claude",
             "source": str(source), "base": "feat/base",
             "worktrees": [{"path": str(worktree), "branch": "feat/afkv2-df-20261126-1730", "lane": "small",
                            "created": "2026-11-26T17:30:00+00:00"}],
             "notes": [], "wrap_reported": False, "started": "2026-11-26T17:00:00+00:00"}
    path = data / f"dogfood-{MAIN.replace(':', '_')}.json"
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    text = tmp_path / "scratch" / "text.md"
    text.parent.mkdir()
    text.write_text("The trial failed: KeyError 'lane' at line 12.", encoding="utf-8")
    return {"env": env, "source": source, "data": data, "state_file": path, "tmp": tmp_path, "worktree": worktree,
            "text": text}


def live(world, env=None):
    """A fake runner where the afkv2 agent of the state runs in its pane."""
    runner = DogfoodFakeRunner(env or world["env"], main_pane=MAIN)
    runner.add_pane(SIDE, kind="claude", name=AGENT)
    return runner


def run(world, argv, runner=None, env=None):
    env = env if env is not None else world["env"]
    runner = runner if runner is not None else live(world, env)
    out = []
    code = dogfood.main(argv, env, runner, out=out.append)
    assert len(out) == 1
    return code, json.loads(out[0]), runner


def state(world):
    return json.loads(world["state_file"].read_text(encoding="utf-8"))


def herdr_calls(runner):
    return [argv for argv in runner.calls if argv[0] == runner.herdr]


# tell (VR-046).

def test_tell_sends_1_prompt_for_feedback_and_for_wrap_and_writes_no_state(world):
    before = world["state_file"].read_bytes()
    for kind, lead in (("feedback", dogfood.TELL_LINES["feedback"]), ("wrap", dogfood.TELL_LINES["wrap"])):
        code, answer, runner = run(world, ["tell", "--kind", kind, "--text-file", str(world["text"])])
        assert (code, answer) == (0, {"ok": True, "sent": True, "kind": kind})
        [prompt] = runner.prompts
        assert prompt["target"] == AGENT and prompt["pane"] == SIDE
        assert prompt["text"] == f"{lead}\n\n{world['text'].read_text(encoding='utf-8')}"
        assert not runner.keys
    assert world["state_file"].read_bytes() == before


def test_tell_refuses_a_text_of_0_or_8001_characters_and_sends_8000(world):
    for size, expected in ((0, (2, "text-unreadable")), (8001, (2, "text-unreadable")), (8000, (0, None))):
        world["text"].write_text("é" * size, encoding="utf-8")
        code, answer, runner = run(world, ["tell", "--kind", "feedback", "--text-file", str(world["text"])])
        if expected[1]:
            assert (code, answer["error"]["code"]) == expected and not herdr_calls(runner)
        else:
            assert code == 0 and len(runner.prompts) == 1
    for content in (b"\xff\xfe bad", None):
        path = world["tmp"] / "other.md"
        if content is not None:
            path.write_bytes(content)
        code, answer, runner = run(world, ["tell", "--kind", "wrap", "--text-file", str(path)])
        assert (code, answer["error"]["code"]) == (2, "text-unreadable") and not herdr_calls(runner)


def test_a_stalled_tell_gets_exactly_1_enter_and_no_resend(world):
    runner = live(world)
    runner.panes[SIDE]["stall"] = True
    runner.on(("pane", "read"), lambda argv: runner.screens.update({SIDE: runner.prompts[-1]["text"]}))
    code, answer, runner = run(world, ["tell", "--kind", "feedback", "--text-file", str(world["text"])], runner)
    assert (code, answer["sent"]) == (0, True) and len(runner.prompts) == 1
    assert runner.keys == [(SIDE, ["enter"])]

    runner = live(world)
    runner.panes[SIDE]["stall"] = True
    runner.answer(("agent", "wait"), herdr_error("timeout"))
    code, answer, runner = run(world, ["tell", "--kind", "feedback", "--text-file", str(world["text"])], runner)
    assert (code, answer["sent"]) == (0, "unconfirmed") and len(runner.prompts) == 1 and not runner.keys


def test_tell_to_a_dialog_answers_prompt_blocked_and_no_pane_answers_no_pane(world):
    argv = ["tell", "--kind", "feedback", "--text-file", str(world["text"])]
    runner = live(world)
    runner.panes[SIDE]["blocked"] = True
    code, answer, runner = run(world, argv, runner)
    assert (code, answer["error"]["code"]) == (1, "prompt-blocked") and not runner.prompts and not runner.keys

    code, answer, runner = run(world, argv, DogfoodFakeRunner(world["env"], main_pane=MAIN))
    assert (code, answer["error"]["code"]) == (1, "no-pane") and not runner.prompts

    for herdr_code in ("agent_not_found", "pane_not_found"):
        runner = live(world)
        runner.answer(("agent", "prompt"), herdr_error(herdr_code))
        code, answer, runner = run(world, argv, runner)
        assert (code, answer["error"]["code"]) == (1, "no-pane")

    runner = live(world)
    runner.answer(("agent", "prompt"), herdr_error("server_down"))
    code, answer, runner = run(world, argv, runner)
    assert (code, answer["error"]["code"]) == (1, "herdr-failed")

    world["state_file"].unlink()
    code, answer, runner = run(world, argv)
    assert (code, answer["error"]["code"]) == (1, "no-pane") and not herdr_calls(runner)


# check-note (VR-041).

def milestone(worktree):
    return ("afkv2-note v1\nkind: milestone\nask: Add a link to the report\npurpose: try the lane\nchanged:\n"
            f"- {worktree / 'skills' / 'SKILL.md'} | CK-1 | changed | the lane asks once\n"
            "use: Run the lane once.\nredo: none\n")


def snapshot(folder):
    return sorted((str(path), path.stat().st_mtime_ns) for path in folder.rglob("*"))


def test_check_note_answers_the_parsed_note_or_its_failures_and_writes_nothing(world):
    notes = world["data"] / f"dogfood-{MAIN.replace(':', '_')}" / "notes"
    notes.mkdir(parents=True)
    note = notes / "0001.md"
    note.write_text(milestone(world["worktree"]), encoding="utf-8")
    before = snapshot(world["data"])

    code, answer, runner = run(world, ["check-note", "--note-file", str(note)])
    assert code == 0 and answer["ok"] and not runner.calls
    assert answer["note"] == json.loads(json.dumps(dogfood.dogfood_note.parse(note.read_text(encoding="utf-8"))))
    assert answer["note"]["kind"] == "milestone"
    assert [row["path"] for row in answer["note"]["changed"]] == [str(world["worktree"] / "skills" / "SKILL.md")]

    note.write_text("afkv2-note v1\nkind: milestone\nask: x\n", encoding="utf-8")
    before = snapshot(world["data"])
    code, answer, runner = run(world, ["check-note", "--note-file", str(note)])
    assert (code, answer["error"]["code"]) == (1, "note-check-failed") and not runner.calls
    assert {failure["code"] for failure in answer["failures"]} == {"N-NO-PATH", "N-NO-USE", "N-NO-REDO"}
    assert all(set(failure) >= {"code", "where", "reason"} for failure in answer["failures"])
    assert snapshot(world["data"]) == before

    outside = world["tmp"] / "elsewhere"
    (outside / "skills").mkdir(parents=True)
    (outside / "skills" / "SKILL.md").write_text("x\n", encoding="utf-8")
    note.write_text(milestone(outside), encoding="utf-8")
    before = snapshot(world["data"])
    code, answer, runner = run(world, ["check-note", "--note-file", str(note)])
    assert (code, answer["error"]["code"]) == (1, "note-check-failed")
    assert {failure["code"] for failure in answer["failures"]} == {"N-PATH-OUTSIDE"}
    assert snapshot(world["data"]) == before


def test_check_note_refuses_an_unreadable_note_and_a_pane_with_no_session(world):
    for content in (b"\xff\xfe bad", b"x" * (16 * 1024 + 1), None):
        path = world["tmp"] / "other.md"
        path.unlink(missing_ok=True)
        if content is not None:
            path.write_bytes(content)
        code, answer, runner = run(world, ["check-note", "--note-file", str(path)])
        assert (code, answer["error"]["code"]) == (2, "note-unreadable") and not runner.calls
    note = world["tmp"] / "note.md"
    note.write_text(milestone(world["worktree"]), encoding="utf-8")
    world["state_file"].unlink()
    before = snapshot(world["data"])
    code, answer, runner = run(world, ["check-note", "--note-file", str(note)])
    assert (code, answer["error"]["code"]) == (1, "no-pane") and not runner.calls
    assert snapshot(world["data"]) == before
