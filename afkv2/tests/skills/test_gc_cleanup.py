"""The gc script's steps on the scratch repository, with an in-process fake of the forge port."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(AFKV2 / "skills" / "gc" / "scripts"))
sys.path.insert(0, str(AFKV2 / "ports"))

import cleanup  # noqa: E402
import gc_checks  # noqa: E402
import gc_target  # noqa: E402
from gc_repo import FEATURE, RUN, build_gc_repo, git  # noqa: E402

GITHUB = "https://github.test/o/r"
GITLAB = "https://gitlab.test/g/p"


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


def change(number, state, head, url=None):
    return {"id": str(number), "url": url or f"{GITHUB}/pull/{number}", "state": state, "head_sha": head, "target": "main"}


def listed(*changes):
    return {"ok": True, "changes": list(changes), "count": len(changes)}


def forge(monkeypatch, answer):
    fake = Forge(answer)
    monkeypatch.setattr(gc_checks, "call_forge", fake)
    return fake


def tip(repo, ref):
    return git(repo.main, "rev-parse", ref)


def merged(repo, monkeypatch, url=None):
    """The forge answers one merged change whose head is the feature tip."""
    return forge(monkeypatch, listed(change(7, "merged", tip(repo, FEATURE), url)))


def same(path, other):
    return Path(path).resolve() == Path(other).resolve()


def by_item(answer):
    return {item["item"]: item for item in answer["items"]}


def test_list_in_the_feature_worktree_answers_the_change_each_item_the_receipt_and_the_state(repo, monkeypatch):
    fake = merged(repo, monkeypatch)
    feature, run = tip(repo, FEATURE), tip(repo, RUN)
    answer = cleanup.list_step(repo.feature)
    assert answer["change"] == {"number": 7, "url": f"{GITHUB}/pull/7", "state": "merged", "head_sha": feature, "target": "main"}
    assert fake.calls[0][0] == "change-list" and fake.calls[0][1]["branch"] == FEATURE
    assert [(item["id"], item["item"], item["when"], item["present"]) for item in answer["items"]] == [
        ("IT-1", "run worktree", "now", True), ("IT-2", "run branch", "now", True),
        ("IT-3", "remote run branch", "now", True), ("IT-4", "remote feature branch", "now", True),
        ("IT-5", "feature worktree", "later", True), ("IT-6", "feature branch", "later", True)]
    items = by_item(answer)
    assert same(items["run worktree"]["name"], repo.run) and same(items["feature worktree"]["name"], repo.feature)
    assert (items["run branch"]["name"], items["remote run branch"]["name"]) == (RUN, f"origin/{RUN}")
    assert (items["feature branch"]["name"], items["remote feature branch"]["name"]) == (FEATURE, f"origin/{FEATURE}")
    assert [items[name]["tip"] for name in ("run branch", "remote run branch", "remote feature branch", "feature branch")] == [
        run, run, feature, feature]
    assert items["run worktree"]["tip"] is None and items["feature worktree"]["tip"] is None
    assert items["feature worktree"]["ignored"] == {"count": 0, "first": []}
    assert answer["refusals"] == []
    assert answer["state"] == "listed"
    assert answer["receipt"] == gc_target.receipt_of(answer)


def test_a_feature_tip_the_forge_holds_gets_its_link_and_a_run_branch_tip_gets_none(repo, monkeypatch):
    merged(repo, monkeypatch)
    feature = tip(repo, FEATURE)
    items = by_item(cleanup.list_step(repo.feature))
    assert items["feature branch"]["link"] == items["remote feature branch"]["link"] == f"{GITHUB}/commit/{feature}"
    assert items["run branch"]["link"] is None and items["remote run branch"]["link"] is None
    assert items["run worktree"]["link"] is None and items["feature worktree"]["link"] is None


def test_a_gitlab_change_gives_a_gitlab_commit_link(repo, monkeypatch):
    merged(repo, monkeypatch, url=f"{GITLAB}/-/merge_requests/7")
    feature = tip(repo, FEATURE)
    assert by_item(cleanup.list_step(repo.feature))["feature branch"]["link"] == f"{GITLAB}/-/commit/{feature}"


def test_a_local_feature_tip_past_the_change_head_is_not_on_the_forge_and_gets_no_link(repo, monkeypatch):
    merged(repo, monkeypatch)
    pushed = tip(repo, FEATURE)
    repo.commit(repo.feature, "late.txt", "late\n", "a late commit")
    items = by_item(cleanup.list_step(repo.feature))
    assert items["feature branch"]["link"] is None
    assert items["remote feature branch"]["link"] == f"{GITHUB}/commit/{pushed}"


def test_list_writes_the_target_as_listed_with_the_answers_receipt(repo, monkeypatch):
    merged(repo, monkeypatch)
    answer = cleanup.list_step(repo.feature)
    target = gc_target.read_target(repo.main, FEATURE)
    assert target["state"] == "listed" and target["left"] == []
    assert target["receipt"] == answer["receipt"]
    assert target["change"] == answer["change"]
    assert target["tips"] == {"feature branch": tip(repo, FEATURE), "remote feature branch": tip(repo, FEATURE),
                              "run branch": tip(repo, RUN), "remote run branch": tip(repo, RUN)}
    assert same(target["feature_worktree"], repo.feature) and same(target["run_worktree"], repo.run)
    assert (target["feature_branch"], target["run_branch"]) == (FEATURE, RUN)
    assert "listed_at" not in answer


def test_each_refusal_comes_with_its_detail_and_the_items_it_concerns(repo, monkeypatch):
    forge(monkeypatch, listed(change(9, "opened", tip(repo, FEATURE))))
    (Path(repo.run) / "notes.txt").write_text("not committed\n", encoding="utf-8")
    answer = cleanup.list_step(repo.feature)
    codes = {refusal["code"]: refusal for refusal in answer["refusals"]}
    assert codes["not-merged"]["items"] == [] and codes["not-merged"]["link"] == f"{GITHUB}/pull/9"
    assert codes["uncommitted"]["items"] == ["run worktree"] and codes["uncommitted"]["files"] == ["notes.txt"]
    assert codes["outside-commits"]["items"] == ["feature branch", "remote feature branch"]
    assert answer["change"] is None
    assert gc_target.read_target(repo.main, FEATURE)["change"] is None


def test_a_commit_outside_the_change_head_refuses_on_its_branch_only(repo, monkeypatch):
    merged(repo, monkeypatch)
    repo.commit(repo.feature, "late.txt", "late\n", "a late commit")
    refusals = cleanup.list_step(repo.feature)["refusals"]
    assert [(refusal["code"], refusal["items"]) for refusal in refusals] == [("outside-commits", ["feature branch"])]
    assert refusals[0]["branches"][0]["commits"][0]["title"] == "a late commit"


def test_ignored_files_are_given_under_their_worktree_and_are_no_refusal(repo, monkeypatch):
    merged(repo, monkeypatch)
    common = Path(git(repo.main, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    (common / "info").mkdir(exist_ok=True)
    (common / "info" / "exclude").write_text("*.log\n", encoding="utf-8")
    (Path(repo.feature) / "build.log").write_text("log\n", encoding="utf-8")
    answer = cleanup.list_step(repo.feature)
    assert by_item(answer)["feature worktree"]["ignored"] == {"count": 1, "first": ["build.log"]}
    assert answer["refusals"] == []


def test_a_system_that_is_not_windows_refuses_each_worktree_removal(repo, monkeypatch):
    merged(repo, monkeypatch)
    real = gc_checks.check_platform
    monkeypatch.setattr(gc_checks, "check_platform", lambda: real("posix"))
    refusals = cleanup.list_step(repo.feature)["refusals"]
    assert [(refusal["code"], refusal["items"]) for refusal in refusals] == [("not-windows", ["run worktree", "feature worktree"])]


def test_an_absent_branch_or_worktree_reads_absent(repo, monkeypatch):
    merged(repo, monkeypatch)
    git(repo.main, "push", "-q", "origin", "--delete", FEATURE)
    git(repo.main, "worktree", "remove", "--force", str(repo.run))
    items = by_item(cleanup.list_step(repo.feature))
    assert (items["remote feature branch"]["present"], items["remote feature branch"]["tip"]) == (False, "")
    assert items["remote feature branch"]["link"] is None
    assert items["run worktree"]["present"] is False
    assert items["run branch"]["present"] is True
