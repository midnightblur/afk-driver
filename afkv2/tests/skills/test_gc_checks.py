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
