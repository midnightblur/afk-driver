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


# close (VR-054, VR-053).

def session_folder(world):
    return world["data"] / f"dogfood-{MAIN.replace(':', '_')}"


def wrapped(world, **extra):
    recorded = {**state(world), "wrap_reported": True, **extra}
    world["state_file"].write_text(json.dumps(recorded, indent=2) + "\n", encoding="utf-8")
    notes = session_folder(world) / "notes"
    notes.mkdir(parents=True, exist_ok=True)
    (notes / "0001.md").write_text("afkv2-note v1\nkind: wrap\n", encoding="utf-8")
    return recorded


def pane_closes(runner):
    return runner.calls_of("pane", "close")


def test_close_refuses_before_the_wrap_note_and_force_on_a_live_pane(world):
    before = world["state_file"].read_bytes()
    for argv in (["close"], ["close", "--force"]):
        code, answer, runner = run(world, argv)
        assert (code, answer["error"]["code"]) == (1, "no-wrap-report") and not pane_closes(runner)
        assert world["state_file"].read_bytes() == before and SIDE in runner.panes
    dead = DogfoodFakeRunner(world["env"], main_pane=MAIN)
    code, answer, runner = run(world, ["close"], dead)
    assert (code, answer["error"]["code"]) == (1, "no-wrap-report") and world["state_file"].read_bytes() == before


def test_close_after_the_wrap_note_closes_the_afkv2_pane_once_and_deletes_the_state_and_the_notes(world):
    recorded = wrapped(world)
    code, answer, runner = run(world, ["close"])
    assert code == 0 and answer == {"ok": True, "pane_closed": True,
                                    "worktrees": [worktree["path"] for worktree in recorded["worktrees"]],
                                    "branches": [worktree["branch"] for worktree in recorded["worktrees"]]}
    assert pane_closes(runner) == [[runner.herdr, "pane", "close", SIDE]] and SIDE not in runner.panes
    assert MAIN in runner.panes
    assert not world["state_file"].exists() and not session_folder(world).exists()
    assert (world["worktree"] / "skills" / "SKILL.md").is_file()

    code, answer, runner = run(world, ["close"])
    assert (code, answer) == (0, {"ok": True, "pane_closed": False, "worktrees": [], "branches": []})
    assert not herdr_calls(runner)


def test_close_with_a_gone_pane_after_the_wrap_and_close_force_on_a_dead_pane_answer_ok(world):
    first = world["state_file"].read_bytes()
    wrapped(world)
    code, answer, runner = run(world, ["close"], DogfoodFakeRunner(world["env"], main_pane=MAIN))
    assert (code, answer["ok"], answer["pane_closed"]) == (0, True, False)
    assert not world["state_file"].exists() and not session_folder(world).exists()

    world["state_file"].write_bytes(first)
    wrapped(world, wrap_reported=False)
    code, answer, runner = run(world, ["close", "--force"], DogfoodFakeRunner(world["env"], main_pane=MAIN))
    assert (code, answer["ok"], answer["pane_closed"]) == (0, True, False) and not pane_closes(runner)
    assert answer["worktrees"] == [str(world["worktree"])]
    assert not world["state_file"].exists() and not session_folder(world).exists()


def _git(cwd, *args):
    done = subprocess.run(["git", "-c", "user.name=afkv2 test", "-c", "user.email=afkv2@example.invalid", "-C",
                           str(cwd), *args], capture_output=True, text=True, check=True, stdin=subprocess.DEVNULL)
    return done.stdout.strip()


def _same(left, right):
    return os.path.normcase(os.path.realpath(left)) == os.path.normcase(os.path.realpath(right))


def test_close_keeps_both_real_git_worktrees_and_their_branches(world):
    source = world["source"]
    _git(source, "-c", "init.defaultBranch=trunk", "init", "-q")
    (source / "README.md").write_text("plugin\n", encoding="utf-8")
    _git(source, "add", "README.md")
    _git(source, "commit", "-q", "-m", "first")
    _git(source, "branch", "feat/base")
    folder = source.parent / f"{source.name}-worktrees"
    worktrees = []
    for lane, branch in (("small", "feat/afkv2-df-20261126-1730"), ("medium", "feat/afkv2-x")):
        path = folder / branch.replace("/", "-")
        _git(source, "worktree", "add", "-q", "-b", branch, str(path), "feat/base")
        worktrees.append({"path": str(path), "branch": branch, "lane": lane, "created": "2026-11-26T17:30:00+00:00"})
    wrapped(world, worktrees=worktrees)

    code, answer, runner = run(world, ["close"])

    assert code == 0 and answer["pane_closed"] and answer["branches"] == [item["branch"] for item in worktrees]
    assert not world["state_file"].exists() and not session_folder(world).exists()
    listed = [line.removeprefix("worktree ") for line in _git(source, "worktree", "list", "--porcelain").splitlines()
              if line.startswith("worktree ")]
    for item in worktrees:
        assert any(_same(path, item["path"]) for path in listed) and (Path(item["path"]) / "README.md").is_file()
        assert _git(source, "rev-parse", "--verify", f"refs/heads/{item['branch']}") == _git(source, "rev-parse",
                                                                                              "feat/base")
        assert _git(item["path"], "branch", "--show-current") == item["branch"]
    assert not [argv for argv in runner.calls if argv[0] == "git"]


# The pane guard on all 7 verbs (VR-016) and the answer contract (VR-019).

def with_source(world):
    """The install record and the plugin manifest that start needs."""
    (world["source"] / "afkv2" / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (world["source"] / "afkv2" / ".claude-plugin" / "plugin.json").write_text('{"name": "afkv2"}', encoding="utf-8")
    (world["data"] / "install.txt").write_text(f"installed 2026-11-26T00:00:00+00:00\nsource {world['source']}\n",
                                               encoding="utf-8")
    world["env"]["ProgramFiles"] = str(world["tmp"] / "program files")


def all_verbs(world):
    note = world["tmp"] / "note.md"
    note.write_text(milestone(world["worktree"]), encoding="utf-8")
    return {
        "start": ["start", "--ask-file", str(world["text"])],
        "status": ["status"],
        "worktree": ["worktree", "--lane", "small", "--base", "feat/base"],
        "note": ["note", "--note-file", str(note)],
        "tell": ["tell", "--kind", "feedback", "--text-file", str(world["text"])],
        "check-note": ["check-note", "--note-file", str(note)],
        "close": ["close"],
    }


def test_each_of_the_7_verbs_runs_only_from_its_permitted_pane_and_takes_no_target_pane(world):
    with_source(world)
    verbs = all_verbs(world)
    assert set(verbs) == set(dogfood.VERBS)
    before = world["state_file"].read_bytes()
    denied = {SIDE: ("start", "tell", "check-note", "close"), MAIN: ("worktree", "note"),
              THIRD: ("worktree", "note")}
    for pane in (MAIN, SIDE, THIRD):
        env = {**world["env"], "HERDR_PANE_ID": pane}
        for verb in denied[pane]:
            code, answer, runner = run(world, verbs[verb], env=env)
            expected = "in-afkv2-pane" if pane == SIDE else "not-afkv2-pane"
            assert (code, answer["error"]["code"]) == (1, expected), (pane, verb)
            assert not runner.calls, (pane, verb)
        code, answer, runner = run(world, verbs["status"], env=env)
        assert code == 0 and answer["state"] == (None if pane == THIRD else state(world)) and not runner.calls
    assert world["state_file"].read_bytes() == before

    third = {**world["env"], "HERDR_PANE_ID": THIRD}
    for verb in ("tell", "check-note"):
        code, answer, runner = run(world, verbs[verb], env=third)
        assert (code, answer["error"]["code"]) == (1, "no-pane") and not runner.calls
    code, answer, runner = run(world, verbs["close"], env=third)
    assert (code, answer["pane_closed"]) == (0, False) and not runner.calls

    for verb, argv in verbs.items():
        for extra in (["--pane", SIDE], ["--target", SIDE], [f"--pane={SIDE}"]):
            code, answer, runner = run(world, [*argv, *extra])
            assert (code, answer["error"]["code"]) == (2, "usage") and not runner.calls, (verb, extra)
    subparsers = next(action for action in dogfood._parser()._actions if action.dest == "verb")
    for verb, parser in subparsers.choices.items():
        options = [option for action in parser._actions for option in action.option_strings]
        assert not [option for option in options if "pane" in option or "target" in option], verb
    assert world["state_file"].read_bytes() == before


def check_contract(code, answer):
    assert isinstance(answer, dict) and isinstance(answer.get("ok"), bool)
    if answer["ok"]:
        assert code == 0 and "error" not in answer
    else:
        assert code in (1, 2) and isinstance(answer["error"]["code"], str) and answer["error"]["code"]
        assert isinstance(answer["error"]["reason"], str) and answer["error"]["reason"]


def test_every_verb_prints_1_json_object_with_ok_and_exits_0_1_or_2(world):
    with_source(world)
    verbs = all_verbs(world)
    side = {**world["env"], "HERDR_PANE_ID": SIDE}
    third = {**world["env"], "HERDR_PANE_ID": THIRD}

    def side_runner():
        runner = DogfoodFakeRunner(side, main_pane=MAIN, branches=("feat/base",))
        runner.add_pane(SIDE, kind="claude", name=AGENT)
        return runner
    cases = [
        (verbs["start"], third, DogfoodFakeRunner(third), 0), (verbs["start"], side, None, 1),
        (verbs["status"], world["env"], None, 0),
        (["worktree", "--lane", "medium", "--base", "feat/base", "--branch", "feat/afkv2-y"], side, side_runner(), 0),
        (["worktree", "--lane", "medium", "--base", "feat/base"], side, None, 1),
        (verbs["note"], side, side_runner(), 0), (verbs["note"], world["env"], None, 1),
        (verbs["tell"], world["env"], None, 0),
        (["tell", "--kind", "wrap", "--text-file", str(world["tmp"] / "absent.md")], world["env"], None, 2),
        (verbs["check-note"], world["env"], None, 0),
        (["check-note", "--note-file", str(world["tmp"] / "absent.md")], world["env"], None, 2),
        (verbs["close"], world["env"], None, 1),
        (["close"], {**world["env"], "HERDR_PANE_ID": "w1:p9"}, None, 0),
        (["close", "--bad"], world["env"], None, 2),
    ]
    for argv, env, given, expected in cases:
        code, answer, used = run(world, argv, given, env)
        check_contract(code, answer)
        assert code == expected, (argv, answer)
        if argv[0] != "close":
            assert not [call for call in pane_closes(used) if call[-1] == SIDE], argv

    world["state_file"].write_text("{broken", encoding="utf-8")
    for verb, argv in verbs.items():
        code, answer, _ = run(world, argv)
        check_contract(code, answer)
        assert (code, answer["error"]["code"]) == (2, "state-unreadable"), verb
