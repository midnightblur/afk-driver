"""dogfood.py worktree and note, the 2 verbs of the afkv2 pane: worktree on real git, note on the fake runner."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AFKV2 / "skills" / "dogfood" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "fakes"))

import dogfood  # noqa: E402
from dogfood_runner import DogfoodFakeRunner, herdr_error  # noqa: E402
from proposer_engine import HerdrRunner  # noqa: E402

MAIN, SIDE = "w1:p1", "w1:p2"
BASE = "feat/base"


def _git(cwd, *args):
    done = subprocess.run(["git", "-c", "user.name=afkv2 test", "-c", "user.email=afkv2@example.invalid", "-C",
                           str(cwd), *args], capture_output=True, text=True, check=True, stdin=subprocess.DEVNULL)
    return done.stdout.strip()


def _same(left, right):
    return os.path.normcase(os.path.realpath(left)) == os.path.normcase(os.path.realpath(right))


@pytest.fixture
def world(tmp_path):
    """The env of the afkv2 pane, a plugin source and the state file of its session."""
    source = tmp_path / "plugin source"
    source.mkdir()
    env = {"HERDR_ENV": "1", "HERDR_PANE_ID": SIDE, "HERDR_BIN_PATH": "C:/fake/herdr/herdr.exe",
           "LOCALAPPDATA": str(tmp_path / "local")}
    data = tmp_path / "local" / "afkv2"
    data.mkdir(parents=True)
    state = {"version": 1, "main_pane": MAIN, "agent": "dogfood-abcd", "afkv2_pane": SIDE, "harness": "claude",
             "source": str(source), "base": None, "worktrees": [], "notes": [], "wrap_reported": False,
             "started": "2026-11-26T17:00:00+00:00"}
    path = data / f"dogfood-{MAIN.replace(':', '_')}.json"
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return {"env": env, "source": source, "data": data, "state_file": path, "tmp": tmp_path}


@pytest.fixture
def repo(world):
    """The plugin source as a real git repository with the base branch."""
    source = world["source"]
    _git(source, "-c", "init.defaultBranch=trunk", "init", "-q")
    (source / "README.md").write_text("plugin\n", encoding="utf-8")
    _git(source, "add", "README.md")
    _git(source, "commit", "-q", "-m", "first")
    _git(source, "branch", BASE)
    _git(source, "branch", "taken")
    return source


def run(world, argv, runner=None, env=None):
    env = env if env is not None else world["env"]
    runner = runner if runner is not None else DogfoodFakeRunner(env, main_pane=MAIN)
    out = []
    code = dogfood.main(argv, env, runner, out=out.append)
    assert len(out) == 1
    return code, json.loads(out[0]), runner


def state(world):
    return json.loads(world["state_file"].read_text(encoding="utf-8"))


def at(monkeypatch, minute):
    monkeypatch.setattr(dogfood, "_clock", lambda: datetime(2026, 11, 26, 17, minute, 5, tzinfo=timezone.utc))


# worktree, on real git.

def test_worktree_small_makes_the_df_branch_from_the_base_and_a_repeat_answers_the_recorded_worktree(
        world, repo, monkeypatch):
    at(monkeypatch, 30)
    code, answer, _ = run(world, ["worktree", "--lane", "small", "--base", BASE], HerdrRunner())

    branch = "feat/afkv2-df-20261126-1730"
    assert code == 0 and answer["ok"] and (answer["branch"], answer["lane"]) == (branch, "small")
    expected = repo.parent / f"{repo.name}-worktrees" / "feat-afkv2-df-20261126-1730"
    assert _same(answer["path"], expected) and (Path(answer["path"]) / "README.md").is_file()
    assert _git(repo, "rev-parse", branch) == _git(repo, "rev-parse", BASE)
    assert _git(answer["path"], "branch", "--show-current") == branch
    recorded = state(world)
    assert recorded["base"] == BASE
    [worktree] = recorded["worktrees"]
    assert {key: worktree[key] for key in ("path", "branch", "lane")} == {"path": answer["path"], "branch": branch,
                                                                          "lane": "small"}
    assert worktree["created"].endswith("+00:00")

    before = world["state_file"].read_bytes()
    code, again, _ = run(world, ["worktree", "--lane", "small", "--base", BASE], HerdrRunner())
    assert code == 0 and {key: again[key] for key in ("path", "branch", "lane")} == {
        key: answer[key] for key in ("path", "branch", "lane")}
    assert world["state_file"].read_bytes() == before

    at(monkeypatch, 31)
    code, later, _ = run(world, ["worktree", "--lane", "small", "--base", BASE], HerdrRunner())
    assert (code, later["error"]["code"]) == (1, "small-exists") and answer["path"] in later["error"]["reason"]
    assert world["state_file"].read_bytes() == before
    assert _git(repo, "branch", "--list", "feat/afkv2-df-20261126-1731") == ""


def test_worktree_medium_refusals_leave_the_state_unchanged_and_a_good_one_is_recorded(world, repo, monkeypatch):
    at(monkeypatch, 30)
    folder = repo.parent / f"{repo.name}-worktrees"
    refusals = [
        (["--lane", "medium", "--base", BASE], "bad-branch"),
        (["--lane", "medium", "--base", BASE, "--branch", "bad name"], "bad-branch"),
        (["--lane", "medium", "--base", BASE, "--branch=-x"], "bad-branch"),
        (["--lane", "medium", "--base", BASE, "--branch", "feat/a..b"], "bad-branch"),
        (["--lane", "medium", "--base", BASE, "--branch", "taken"], "bad-branch"),
        (["--lane", "medium", "--base", "gone", "--branch", "feat/afkv2-x"], "base-missing"),
        (["--lane", "medium", "--base", "bad base", "--branch", "feat/afkv2-x"], "bad-branch"),
        (["--lane", "small", "--base", BASE, "--branch", "feat/afkv2-x"], "bad-branch"),
    ]
    before = world["state_file"].read_bytes()
    for args, expected in refusals:
        code, answer, _ = run(world, ["worktree", *args], HerdrRunner())
        assert (code, answer["error"]["code"]) == (1, expected), args
        assert world["state_file"].read_bytes() == before and not folder.exists()

    code, answer, _ = run(world, ["worktree", "--lane", "medium", "--base", BASE, "--branch", "feat/afkv2-x"],
                          HerdrRunner())
    assert code == 0 and (answer["branch"], answer["lane"]) == ("feat/afkv2-x", "medium")
    assert _same(answer["path"], folder / "feat-afkv2-x")
    assert _git(repo, "rev-parse", "feat/afkv2-x") == _git(repo, "rev-parse", BASE)
    recorded = state(world)
    [worktree] = recorded["worktrees"]
    assert recorded["base"] == BASE and worktree["branch"] == "feat/afkv2-x"

    before = world["state_file"].read_bytes()
    code, again, _ = run(world, ["worktree", "--lane", "medium", "--base", BASE, "--branch", "feat/afkv2-x"],
                         HerdrRunner())
    assert code == 0 and again["path"] == answer["path"] and world["state_file"].read_bytes() == before
    _git(repo, "branch", "other-base")
    code, answer, _ = run(world, ["worktree", "--lane", "medium", "--base", "other-base", "--branch", "feat/afkv2-y"],
                          HerdrRunner())
    assert (code, answer["error"]["code"]) == (1, "base-missing") and BASE in answer["error"]["reason"]
    assert world["state_file"].read_bytes() == before


def test_worktree_that_git_refuses_answers_worktree_failed_and_writes_nothing(world, repo, monkeypatch):
    at(monkeypatch, 30)
    blocker = repo.parent / f"{repo.name}-worktrees" / "feat-afkv2-df-20261126-1730"
    blocker.mkdir(parents=True)
    (blocker / "in the way.txt").write_text("x", encoding="utf-8")
    before = world["state_file"].read_bytes()
    code, answer, _ = run(world, ["worktree", "--lane", "small", "--base", BASE], HerdrRunner())
    assert (code, answer["error"]["code"]) == (1, "worktree-failed")
    assert world["state_file"].read_bytes() == before


def guarded(world, *argvs):
    """Each argv refuses from the main pane and an unknown pane, and outside herdr, with no runner call."""
    before = world["state_file"].read_bytes()
    for argv in argvs:
        for pane in (MAIN, "w5:p5"):
            code, answer, runner = run(world, argv, env={**world["env"], "HERDR_PANE_ID": pane})
            assert (code, answer["error"]["code"]) == (1, "not-afkv2-pane") and not runner.calls
        code, answer, runner = run(world, argv, env={**world["env"], "HERDR_ENV": "0"})
        assert (code, answer["error"]["code"]) == (1, "outside-herdr") and not runner.calls
    assert world["state_file"].read_bytes() == before


def test_worktree_runs_only_from_the_afkv2_pane(world):
    guarded(world, ["worktree", "--lane", "small", "--base", BASE])


# note, on the fake runner.

def notes_folder(world):
    return world["data"] / f"dogfood-{MAIN.replace(':', '_')}" / "notes"


@pytest.fixture
def noted(world):
    """A session with 1 listed worktree that holds the changed file, and a valid milestone note in scratch."""
    worktree = world["tmp"] / "wt"
    (worktree / "skills").mkdir(parents=True)
    (worktree / "skills" / "SKILL.md").write_text("x\n", encoding="utf-8")
    recorded = state(world)
    recorded["base"] = BASE
    recorded["worktrees"] = [{"path": str(worktree), "branch": "feat/afkv2-df-20261126-1730", "lane": "small",
                              "created": "2026-11-26T17:30:00+00:00"}]
    world["state_file"].write_text(json.dumps(recorded, indent=2) + "\n", encoding="utf-8")
    note = world["tmp"] / "scratch" / "note.md"
    note.parent.mkdir()
    note.write_text(milestone(worktree), encoding="utf-8")
    return {**world, "worktree": worktree, "note": note}


def milestone(worktree, padding=""):
    return ("afkv2-note v1\nkind: milestone\nask: Add a link to the report\npurpose: try the lane\nchanged:\n"
            f"- {worktree / 'skills' / 'SKILL.md'} | CK-1 | changed | the lane asks once\n"
            f"use: Run the lane once.{padding}\nredo: none\n")


def wrap_note():
    return ("afkv2-note v1\nkind: wrap\nask: Add a link to the report\nchanges:\n"
            "- https://forge.example/pr/7 | feat/x | ask 1\nopen-asks: none\n")


def test_note_checks_stores_prompts_the_main_pane_with_1_line_then_records_and_a_repeat_is_already_sent(noted):
    runner = DogfoodFakeRunner(noted["env"], main_pane=MAIN)
    seen = {}

    def at_prompt(argv):
        seen["file"] = (notes_folder(noted) / "0001.md").is_file()
        seen["records"] = len(state(noted)["notes"])
    runner.on(("agent", "prompt"), at_prompt)

    code, answer, runner = run(noted, ["note", "--note-file", str(noted["note"])], runner)

    assert code == 0 and answer["ok"] and (answer["sent"], answer["id"]) == (True, 1)
    stored = notes_folder(noted) / "0001.md"
    assert _same(answer["path"], stored) and stored.read_bytes() == noted["note"].read_bytes()
    assert seen == {"file": True, "records": 0}
    [prompt] = runner.prompts
    assert prompt["target"] == MAIN and prompt["pane"] == MAIN
    assert "\n" not in prompt["text"] and prompt["text"].endswith(answer["path"])
    [record] = state(noted)["notes"]
    assert record["id"] == 1 and record["path"] == answer["path"] and record["kind"] == "milestone"
    assert record["sha256"] == hashlib.sha256(noted["note"].read_bytes()).hexdigest()
    assert record["paths"] == [str(noted["worktree"] / "skills" / "SKILL.md")]
    assert record["sent_at"].endswith("+00:00") and not state(noted)["wrap_reported"]

    before = noted["state_file"].read_bytes()
    code, again, runner = run(noted, ["note", "--note-file", str(noted["note"])])
    assert (code, again["error"]["code"]) == (1, "already-sent") and not runner.calls
    assert noted["state_file"].read_bytes() == before


def test_a_failing_note_writes_nothing_and_a_wrap_note_sets_wrap_reported(noted):
    noted["note"].write_text("afkv2-note v1\nkind: milestone\nask: x\n", encoding="utf-8")
    before = noted["state_file"].read_bytes()
    code, answer, runner = run(noted, ["note", "--note-file", str(noted["note"])])
    assert (code, answer["error"]["code"]) == (1, "note-check-failed") and not runner.calls
    assert {failure["code"] for failure in answer["failures"]} == {"N-NO-PATH", "N-NO-USE", "N-NO-REDO"}
    assert noted["state_file"].read_bytes() == before and not notes_folder(noted).exists()

    noted["note"].write_text(milestone(noted["worktree"]), encoding="utf-8")
    assert run(noted, ["note", "--note-file", str(noted["note"])])[0] == 0
    noted["note"].write_text(wrap_note(), encoding="utf-8")
    code, answer, runner = run(noted, ["note", "--note-file", str(noted["note"])])
    assert code == 0 and answer["id"] == 2 and _same(answer["path"], notes_folder(noted) / "0002.md")
    recorded = state(noted)
    assert recorded["wrap_reported"] and [note["kind"] for note in recorded["notes"]] == ["milestone", "wrap"]


def test_note_runs_only_from_the_afkv2_pane(noted):
    guarded(noted, ["note", "--note-file", str(noted["note"])])
