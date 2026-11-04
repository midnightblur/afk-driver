"""The refusal checks of gc: the forge state of the branch's changes, uncommitted files, commits outside the change, and the platform."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(AFKV2 / "skills" / "gc" / "scripts"))
sys.path.insert(0, str(AFKV2 / "ports"))

import gc_checks  # noqa: E402
from gc_repo import FEATURE, build_gc_repo, git  # noqa: E402

HEAD_OLD, HEAD_NEW = "1" * 40, "2" * 40


@pytest.fixture
def repo(tmp_path):
    return build_gc_repo(tmp_path)


class Forge:
    """An in-process fake of the forge port: one canned answer, each call kept."""

    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def __call__(self, verb, payload, cwd):
        self.calls.append((verb, payload, cwd))
        return self.answer


def change(number, state, head=HEAD_OLD, target="main"):
    return {"id": str(number), "url": f"https://forge.test/c/{number}", "state": state, "head_sha": head, "target": target}


def listed(*changes):
    return {"ok": True, "changes": list(changes), "count": len(changes)}


def check_with(monkeypatch, answer, **options):
    fake = Forge(answer)
    monkeypatch.setattr(gc_checks, "call_forge", fake)
    return gc_checks.check_change("C:/repo", FEATURE, **options), fake


def test_one_merged_change_passes_and_gives_its_head_commit(monkeypatch):
    result, fake = check_with(monkeypatch, listed(change(7, "merged")), forge="github")
    assert result["refusal"] is None
    assert result["change"] == {"number": 7, "url": "https://forge.test/c/7", "state": "merged",
                                "head_sha": HEAD_OLD, "target": "main"}
    assert fake.calls == [("change-list", {"branch": FEATURE, "forge": "github"}, "C:/repo")]


def test_the_newest_merged_change_gives_the_head_commit_past_a_closed_one(monkeypatch):
    answer = listed(change(9, "closed", "3" * 40), change(8, "merged", HEAD_NEW), change(4, "merged", HEAD_OLD))
    result, _ = check_with(monkeypatch, answer)
    assert result["refusal"] is None
    assert (result["change"]["number"], result["change"]["head_sha"]) == (8, HEAD_NEW)


@pytest.mark.parametrize("changes, link", [
    ([change(7, "opened")], "https://forge.test/c/7"),
    ([change(7, "closed")], "https://forge.test/c/7"),
    ([change(9, "opened", HEAD_NEW), change(7, "merged")], "https://forge.test/c/9"),
    ([change(9, "merged", HEAD_NEW), change(7, "opened")], "https://forge.test/c/9"),
    ([change(7, "draft")], "https://forge.test/c/7"),
    ([change(7, "")], "https://forge.test/c/7"),
    ([], None),
])
def test_any_other_forge_answer_refuses_not_merged_with_the_answer_and_the_link(monkeypatch, changes, link):
    result, _ = check_with(monkeypatch, listed(*changes))
    refusal = result["refusal"]
    assert refusal["code"] == "not-merged"
    assert refusal["link"] == link
    assert refusal["answer"] == [{"number": int(item["id"]), "state": item["state"], "url": item["url"]} for item in changes]
    merged = [int(item["id"]) for item in changes if item["state"] == "merged"]
    assert (result["change"] or {}).get("number") == (merged[0] if merged else None)


def test_a_failed_forge_call_refuses_forge_failed_with_the_error(monkeypatch):
    error = {"code": "auth", "reason": "gh is not signed in"}
    result, _ = check_with(monkeypatch, {"ok": False, "error": error})
    assert result["refusal"] == {"code": "forge-failed", "reason": "the forge call failed: auth: gh is not signed in",
                                 "error": error}
    assert result["change"] is None


@pytest.mark.parametrize("answer", [
    {"ok": True},
    {"ok": True, "changes": "none"},
    {"ok": True, "changes": [{"id": "x7", "state": "merged", "head_sha": HEAD_OLD}]},
    {"ok": True, "changes": [change(7, "merged", head="")]},
    {"ok": True, "changes": [change(7, "merged", head="abc")]},
])
def test_an_answer_with_no_readable_change_or_no_head_commit_refuses_forge_failed(monkeypatch, answer):
    result, _ = check_with(monkeypatch, answer)
    assert result["refusal"]["code"] == "forge-failed"
    assert result["refusal"]["error"]["code"] == "bad-answer"
    assert result["change"] is None


def test_the_real_forge_command_runs_in_the_repository_and_its_refusal_is_forge_failed(repo):
    result = gc_checks.check_change(repo.feature, FEATURE, forge="not-a-forge")
    assert result["refusal"]["code"] == "forge-failed"
    assert result["refusal"]["error"]["code"] == "no-forge"


def write(path, text="x\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_a_clean_worktree_passes_with_no_ignored_file(repo):
    result = gc_checks.check_clean(repo.feature)
    assert result == {"refusal": None, "worktree": str(repo.feature), "absent": False, "files": [],
                      "ignored": {"count": 0, "first": []}}


def test_each_uncommitted_and_untracked_file_refuses_by_its_name(repo):
    write(repo.feature / "feature.txt", "changed\n")
    write(repo.feature / "new dir" / "a new file.txt")
    write(repo.feature / "staged.txt")
    git(repo.feature, "add", "staged.txt")
    git(repo.feature, "mv", "feature.txt", "moved.txt")
    result = gc_checks.check_clean(repo.feature)
    assert result["files"] == ["moved.txt", "new dir/a new file.txt", "staged.txt"]
    assert result["refusal"]["code"] == "uncommitted"
    assert result["refusal"]["files"] == result["files"]
    assert "moved.txt" in result["refusal"]["reason"]


def test_ignored_files_are_no_refusal_and_the_check_gives_their_count_and_the_first_5(repo):
    repo.commit(repo.feature, ".gitignore", "*.log\nbuild/\n", "ignore")
    for number in range(7):
        write(repo.feature / f"a{number}.log")
    write(repo.feature / "build" / "out" / "one.bin")
    write(repo.feature / "build" / "two.bin")
    result = gc_checks.check_clean(repo.feature)
    assert result["refusal"] is None
    assert result["ignored"] == {"count": 8, "first": ["a0.log", "a1.log", "a2.log", "a3.log", "a4.log"]}


def test_an_absent_worktree_reads_absent_not_an_error(repo, tmp_path):
    missing = tmp_path / "gone-run"
    result = gc_checks.check_clean(missing)
    assert result == {"refusal": None, "worktree": str(missing), "absent": True, "files": [],
                      "ignored": {"count": 0, "first": []}}


def tip(repo, ref):
    return git(repo.main, "rev-parse", ref)


def short(repo, commit):
    return git(repo.main, "rev-parse", "--short", commit)


def test_tips_at_the_change_head_pass_and_every_branch_tip_is_given(repo):
    head = tip(repo, FEATURE)
    result = gc_checks.check_tips(repo.main, FEATURE, head)
    assert result["refusal"] is None
    assert result["run_branch"] == FEATURE + "-run"
    assert result["tips"] == {"feature branch": head, "remote feature branch": head,
                              "run branch": tip(repo, FEATURE + "-run"), "remote run branch": tip(repo, FEATURE + "-run")}
    assert result["absent"] == []


def test_a_tip_older_than_the_change_head_passes(repo):
    older = tip(repo, FEATURE)
    head = repo.commit(repo.feature, "more.txt", "more\n", "more work")
    git(repo.feature, "push", "-q", "origin", FEATURE)
    git(repo.feature, "reset", "-q", "--hard", older)
    result = gc_checks.check_tips(repo.main, FEATURE, head)
    assert result["refusal"] is None
    assert result["tips"]["feature branch"] == older


def test_a_local_commit_after_the_merge_refuses_with_its_short_id_and_title(repo):
    head = tip(repo, FEATURE)
    late = repo.commit(repo.feature, "late.txt", "late\n", "a late fix")
    result = gc_checks.check_tips(repo.main, FEATURE, head)
    refusal = result["refusal"]
    assert refusal["code"] == "outside-commits"
    assert refusal["branches"] == [{"item": "feature branch", "branch": FEATURE, "tip": late,
                                    "commits": [{"id": short(repo, late), "title": "a late fix"}]}]
    assert short(repo, late) in refusal["reason"] and "a late fix" in refusal["reason"]


def test_a_remote_commit_this_clone_never_fetched_refuses_with_its_short_id_and_title(repo, tmp_path):
    head = tip(repo, FEATURE)
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", "-b", FEATURE, str(repo.remote), str(other))
    for key, value in (("user.name", "o"), ("user.email", "o@t.test"), ("commit.gpgsign", "false")):
        git(other, "config", key, value)
    pushed = repo.commit(other, "pushed.txt", "pushed\n", "pushed from elsewhere")
    git(other, "push", "-q", "origin", FEATURE)
    result = gc_checks.check_tips(repo.main, FEATURE, head)
    assert result["tips"]["remote feature branch"] == pushed
    assert result["refusal"]["branches"] == [{"item": "remote feature branch", "branch": FEATURE, "tip": pushed,
                                              "commits": [{"id": short(repo, pushed), "title": "pushed from elsewhere"}]}]


def test_an_absent_run_branch_reads_absent_not_an_error(repo):
    git(repo.main, "worktree", "remove", "--force", str(repo.run))
    git(repo.main, "branch", "-D", FEATURE + "-run")
    git(repo.main, "push", "-q", "origin", "--delete", FEATURE + "-run")
    result = gc_checks.check_tips(repo.main, FEATURE, tip(repo, FEATURE))
    assert result["refusal"] is None
    assert (result["tips"]["run branch"], result["tips"]["remote run branch"]) == ("", "")
    assert result["absent"] == ["run branch", "remote run branch"]


def test_no_change_head_leaves_each_feature_tip_unchecked_and_refuses(repo):
    result = gc_checks.check_tips(repo.main, FEATURE, None)
    refusal = result["refusal"]
    assert refusal["code"] == "outside-commits"
    assert [branch["item"] for branch in refusal["branches"]] == ["feature branch", "remote feature branch"]
    assert all(branch["commits"] is None for branch in refusal["branches"])


def test_windows_passes_the_platform_check():
    assert gc_checks.check_platform("nt") == {"refusal": None, "system": "nt"}


def test_another_system_refuses_not_windows_for_each_worktree_removal():
    refusal = gc_checks.check_platform("posix")["refusal"]
    assert refusal["code"] == "not-windows"
    assert "afkv2 runs on Windows only" in refusal["reason"]


def test_the_platform_check_reads_this_system_by_default():
    import os
    assert gc_checks.check_platform()["system"] == os.name
