"""The journal copy of a run: `archive` copies plan/JOURNAL.md into the spec folder on the feature branch, and `start` writes the class."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[1].parent
sys.path.insert(0, str(AFKV2 / "tests" / "autopilot"))
sys.path.insert(0, str(AFKV2 / "skills" / "autopilot" / "scripts"))
sys.path.insert(0, str(AFKV2 / "ports"))

import plan_contract  # noqa: E402
import plan_fixture  # noqa: E402
import start_gate  # noqa: E402
import walk  # noqa: E402
from plan_fixture import contract_text, git  # noqa: E402

COPY = Path("docs") / "runs" / "feat-x-run.md"


@pytest.fixture
def built(tmp_path, monkeypatch):
    found = plan_fixture.build(tmp_path, {"0001-a": contract_text("0001-a"), "0002-b": contract_text("0002-b")})
    monkeypatch.chdir(found.work)
    monkeypatch.setattr(start_gate, "forge_answer", lambda code: {"ok": True, "authenticated": True, "user": "t"})
    return found


def all_done(built):
    for subtask in ("0001-a", "0002-b"):
        plan_contract.write_status(built.plan, subtask, "done")
    git(built.run, "commit", "-qam", "all done")


def verb(name, built, **payload):
    return walk.VERBS[name]({"plan": str(built.plan), **payload})


def test_archive_copies_the_journal_to_the_spec_folder_and_commits_it_on_the_feature_branch(built):
    verb("end", built)
    answer = verb("archive", built)
    copy = built.work / COPY
    assert answer["ok"] and answer["committed"] is True
    assert Path(answer["path"]).resolve() == copy.resolve()
    assert copy.read_bytes() == (built.plan / "JOURNAL.md").read_bytes()
    assert git(built.work, "log", "-1", "--format=%H", "--", COPY.as_posix()) == git(built.work, "rev-parse", "HEAD")
    assert git(built.work, "status", "--porcelain") == ""
    assert git(built.run, "status", "--porcelain") == ""
    assert all(name.startswith("plan/") for name in git(built.run, "ls-tree", "-r", "--name-only", "HEAD").splitlines())


def test_archive_with_no_change_makes_no_commit(built):
    verb("end", built)
    verb("archive", built)
    head = git(built.work, "rev-parse", "HEAD")
    again = verb("archive", built)
    assert again["ok"] and again["committed"] is False
    assert git(built.work, "rev-parse", "HEAD") == head


def test_archive_leaves_other_work_in_the_feature_worktree_alone(built):
    (built.work / "notes.txt").write_text("not mine\n", encoding="utf-8")
    (built.work / "README.md").write_text("changed, not staged\n", encoding="utf-8")
    verb("end", built)
    assert verb("archive", built)["committed"] is True
    assert git(built.work, "show", "--name-only", "--format=", "HEAD").splitlines() == [COPY.as_posix()]
    assert sorted(git(built.work, "status", "--porcelain").splitlines()) == [" M README.md", "?? notes.txt"]


def test_ship_waits_for_archive(built):
    all_done(built)
    assert verb("end", built)["ship"] is False
    assert verb("archive", built)["ship"] is True
    assert verb("end", built)["ship"] is False
    assert verb("archive", built)["ship"] is True


def test_archive_of_an_unfinished_run_does_not_ship(built):
    verb("end", built)
    assert verb("archive", built)["ship"] is False


def test_a_failed_commit_refuses_keeps_ship_false_and_may_run_again(built, tmp_path):
    all_done(built)
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "pre-commit").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    git(built.work, "config", "core.hooksPath", str(hooks))
    verb("end", built)
    with pytest.raises(start_gate.Refusal) as caught:
        verb("archive", built)
    assert caught.value.code == "git-failed"
    assert verb("end", built)["ship"] is False
    git(built.work, "config", "--unset", "core.hooksPath")
    again = verb("archive", built)
    assert again["committed"] is True and again["ship"] is True


def test_archive_with_no_feature_worktree_refuses(built):
    git(built.work, "checkout", "-q", "-b", "other")
    with pytest.raises(start_gate.Refusal) as caught:
        verb("archive", built)
    assert caught.value.code == "no-feature-worktree"


@pytest.mark.parametrize("complexity, logged", [("complex", "complex"), ("mechanical", "mechanical"), ("", "standard"), ("huge", "standard")])
def test_start_writes_the_complexity_class_into_the_journal(tmp_path, monkeypatch, complexity, logged):
    text = contract_text("0001-a").replace("## Complexity\nstandard", f"## Complexity\n{complexity}")
    found = plan_fixture.build(tmp_path, {"0001-a": text})
    monkeypatch.chdir(found.work)
    walk.VERBS["start"]({"plan": str(found.plan), "subtask": "0001-a"})
    lines = (found.plan / "JOURNAL.md").read_text(encoding="utf-8").splitlines()
    assert sum(" | complexity " in line for line in lines) == 1
    assert any(f"| autopilot | 0001-a | complexity {logged} — " in line for line in lines)


def test_a_resumed_start_writes_no_second_class_line(built):
    verb("start", built, subtask="0001-a")
    verb("start", built, subtask="0001-a")
    assert (built.plan / "JOURNAL.md").read_text(encoding="utf-8").count("| complexity ") == 1


def test_an_old_journal_with_no_class_line_still_parses_for_end(built):
    (built.plan / "JOURNAL.md").write_text(walk.JOURNAL_HEADER + "2026-01-01 10:00 | autopilot | 0001-a | developing — old line\n", encoding="utf-8")
    git(built.run, "add", "plan")
    git(built.run, "commit", "-qm", "old journal")
    assert verb("end", built)["ok"]
    assert verb("archive", built)["committed"] is True


def test_the_skill_names_archive():
    text = (AFKV2 / "skills" / "autopilot" / "SKILL.md").read_text(encoding="utf-8")
    assert "`archive`" in text
