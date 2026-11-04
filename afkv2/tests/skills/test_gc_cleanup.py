"""The gc script's steps on the scratch repository, with an in-process fake of the forge port."""

from __future__ import annotations

import json
import subprocess
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
PLATFORM = gc_checks.check_platform
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


def refused(code, step, *args, **kwargs):
    with pytest.raises(cleanup.Refusal) as caught:
        step(*args, **kwargs)
    assert caught.value.code == code
    return caught.value


@pytest.mark.parametrize("where", ["main", "run", "detached", "subfolder of main"])
def test_list_outside_a_feature_worktree_refuses_not_feature_worktree_and_writes_no_target(repo, monkeypatch, where):
    fake = merged(repo, monkeypatch)
    folder = {"main": repo.main, "run": repo.run, "detached": repo.feature, "subfolder of main": Path(repo.main) / "sub"}[where]
    if where == "detached":
        git(repo.feature, "checkout", "-q", "--detach")
    if where == "subfolder of main":
        folder.mkdir()
    refusal = refused("not-feature-worktree", cleanup.list_step, folder)
    assert str(folder) in refusal.reason or Path(folder).name in refusal.reason
    assert fake.calls == []
    for branch in (FEATURE, RUN, "HEAD", "main"):
        assert gc_target.read_target(repo.main, branch) is None


def test_list_from_a_subfolder_of_the_feature_worktree_fixes_the_worktree_itself(repo, monkeypatch):
    merged(repo, monkeypatch)
    sub = Path(repo.feature) / "sub"
    sub.mkdir()
    answer = cleanup.list_step(sub)
    assert same(answer["feature_worktree"], repo.feature)


def stored(repo, **fields):
    """Write a target of the feature branch as an earlier run left it."""
    head = tip(repo, FEATURE)
    target = gc_target.new_target(FEATURE, str(repo.feature),
                                  {"number": 7, "url": f"{GITHUB}/pull/7", "state": "merged", "head_sha": head, "target": "main"},
                                  {"feature branch": head}, "c" * 64, **fields)
    gc_target.write_target(repo.main, target)
    return target


def shown(target):
    return {key: value for key, value in target.items() if key != "schema"}


def test_a_second_list_replaces_a_listed_target(repo, monkeypatch):
    merged(repo, monkeypatch)
    stored(repo)
    answer = cleanup.list_step(repo.feature)
    target = gc_target.read_target(repo.main, FEATURE)
    assert answer["receipt"] != "c" * 64 and target["receipt"] == answer["receipt"] and target["state"] == "listed"


def test_list_answers_a_waiting_target_as_stored_with_no_forge_call_and_no_write(repo, monkeypatch):
    fake = merged(repo, monkeypatch)
    target = stored(repo, state="waiting", left=["feature worktree", "feature branch"])
    assert cleanup.list_step(repo.feature) == shown(target)
    assert fake.calls == []
    assert gc_target.read_target(repo.main, FEATURE) == target


@pytest.mark.parametrize("text", ["{not json", '{"schema": "afkv2.gc/9"}'])
def test_list_in_the_feature_worktree_replaces_a_broken_target(repo, monkeypatch, text):
    merged(repo, monkeypatch)
    path = gc_target.target_path(repo.main, FEATURE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    answer = cleanup.list_step(repo.feature)
    assert gc_target.read_target(repo.main, FEATURE)["receipt"] == answer["receipt"]


@pytest.mark.parametrize("where", ["main", "feature", "run"])
def test_list_with_a_branch_shows_a_waiting_target_from_anywhere(repo, monkeypatch, where):
    fake = merged(repo, monkeypatch)
    target = stored(repo, state="waiting", left=["feature branch"])
    assert cleanup.list_step(getattr(repo, where), branch=FEATURE) == shown(target)
    assert fake.calls == []


@pytest.mark.parametrize("state", ["listed", None])
def test_list_with_a_branch_refuses_no_target_unless_waiting_and_never_fixes_one(repo, monkeypatch, state):
    fake = merged(repo, monkeypatch)
    before = stored(repo, state=state) if state else None
    refused("no-target", cleanup.list_step, repo.main, branch=FEATURE)
    assert gc_target.read_target(repo.main, FEATURE) == before
    assert fake.calls == []


@pytest.mark.parametrize("state", ["done", "removing"])
def test_list_with_a_branch_refuses_bad_target_for_a_state_it_does_not_know(repo, monkeypatch, state):
    merged(repo, monkeypatch)
    stored(repo, state=state)
    refused("bad-target", cleanup.list_step, repo.main, branch=FEATURE)


def test_list_refuses_locked_while_another_run_holds_the_target(repo, monkeypatch):
    fake = merged(repo, monkeypatch)
    with gc_target.take_lock(repo.main, FEATURE):
        refused("locked", cleanup.list_step, repo.feature)
    assert fake.calls == [] and gc_target.read_target(repo.main, FEATURE) is None


def test_list_under_a_lock_its_caller_holds_keeps_that_lock(repo, monkeypatch):
    merged(repo, monkeypatch)
    with gc_target.take_lock(repo.main, FEATURE) as lock:
        cleanup.list_step(repo.feature, lock=lock)
        refused("locked", gc_target.take_lock, repo.main, FEATURE)
    gc_target.take_lock(repo.main, FEATURE).release()


def run_cli(capsys, *argv):
    code = cleanup.main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def test_a_forge_failure_is_a_refusal_in_the_list_and_list_exits_0(repo, monkeypatch, capsys):
    forge(monkeypatch, {"ok": False, "error": {"code": "auth", "reason": "gh is not signed in"}})
    code, answer = run_cli(capsys, "list", "--repo", str(repo.feature))
    assert code == 0 and answer["ok"] is True
    assert [(refusal["code"], refusal["items"]) for refusal in answer["refusals"]][0] == ("forge-failed", [])
    assert "gh is not signed in" in answer["refusals"][0]["reason"]
    assert answer["change"] is None
    assert answer["receipt"] == gc_target.receipt_of({key: value for key, value in answer.items() if key != "ok"})


def test_the_list_command_runs_in_the_current_folder_by_default(repo, monkeypatch, capsys):
    merged(repo, monkeypatch)
    monkeypatch.chdir(repo.feature)
    code, answer = run_cli(capsys, "list")
    assert code == 0 and same(answer["feature_worktree"], repo.feature)


def test_a_list_error_exits_1_with_its_code(repo, monkeypatch, capsys):
    merged(repo, monkeypatch)
    code, answer = run_cli(capsys, "list", "--repo", str(repo.main))
    assert code == 1 and answer["error"]["code"] == "not-feature-worktree"
    code, answer = run_cli(capsys, "list", "--repo", str(repo.main), "--branch", FEATURE)
    assert code == 1 and answer["error"]["code"] == "no-target"


@pytest.mark.parametrize("argv", [[], ["unknown"], ["list", "--colour"], ["list", "--branch"]])
def test_unreadable_arguments_exit_2(capsys, argv):
    code, answer = run_cli(capsys, *argv)
    assert code == 2 and answer["ok"] is False and answer["error"]["code"] in ("bad-payload", "unknown-verb")


def test_a_change_head_this_clone_lacks_leaves_each_feature_tip_unchecked_as_a_refusal(repo, monkeypatch):
    forge(monkeypatch, listed(change(7, "merged", "1" * 40)))
    answer = cleanup.list_step(repo.feature)
    refusal = next(refusal for refusal in answer["refusals"] if refusal["code"] == "outside-commits")
    assert refusal["items"] == ["feature branch", "remote feature branch"]
    assert "1" * 12 in refusal["reason"] and "unchecked" in refusal["reason"]
    assert answer["change"]["head_sha"] == "1" * 40
    assert gc_target.read_target(repo.main, FEATURE)["receipt"] == answer["receipt"]


def test_a_leftover_gc_removing_folder_is_listed_under_its_worktree(repo, monkeypatch):
    merged(repo, monkeypatch)
    leftover = Path(str(repo.run) + ".gc-removing")
    (leftover / "half").mkdir(parents=True)
    git(repo.main, "worktree", "remove", "--force", str(repo.run))
    items = by_item(cleanup.list_step(repo.feature))
    assert same(items["run worktree"]["leftover"], leftover) and items["run worktree"]["present"] is False
    assert items["feature worktree"]["leftover"] is None
    assert all("leftover" not in item for name, item in items.items() if name not in ("run worktree", "feature worktree"))


def test_the_script_runs_as_a_command_and_finds_its_sibling_modules_in_isolated_mode(tmp_path):
    done = subprocess.run([sys.executable, "-I", str(Path(cleanup.__file__)), "list", "--repo", str(tmp_path), "--branch", FEATURE],
                          capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60, cwd=tmp_path)
    answer = json.loads(done.stdout)
    assert done.returncode == 1 and answer["error"]["code"] in ("git-failed", "no-target")


# gc remove


@pytest.fixture
def windows(monkeypatch):
    """The folder removal runs on Windows only: elsewhere, the tests stand in for it."""
    import folder_remove
    real = gc_checks.check_platform
    monkeypatch.setattr(gc_checks, "check_platform", lambda: real("nt"))
    monkeypatch.setattr(folder_remove, "WINDOWS", True)


def remote_heads(repo):
    return {line.split("\t")[1].removeprefix("refs/heads/"): line.split("\t")[0]
            for line in git(repo.main, "ls-remote", str(repo.remote), "refs/heads/*").splitlines() if line}


def local_heads(repo):
    return set(git(repo.main, "for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines())


def untouched(repo):
    """Every item of the work is still there."""
    assert Path(repo.run).is_dir() and Path(repo.feature).is_dir()
    assert {FEATURE, RUN} <= local_heads(repo) and {FEATURE, RUN} <= set(remote_heads(repo))


def test_remove_with_a_receipt_that_does_not_match_a_fresh_list_refuses_stale_list_with_it_and_removes_nothing(repo, monkeypatch, windows):
    fake = merged(repo, monkeypatch)
    receipt = cleanup.list_step(repo.feature)["receipt"]
    repo.commit(repo.feature, "late.txt", "late\n", "a late commit")
    refusal = refused("stale-list", cleanup.remove_step, repo.main, FEATURE, receipt)
    fresh = refusal.extra["list"]
    assert fresh["receipt"] != receipt and fresh["receipt"] == gc_target.receipt_of(fresh)
    assert [entry["code"] for entry in fresh["refusals"]] == ["outside-commits"]
    assert len(fake.calls) == 2
    untouched(repo)
    assert gc_target.read_target(repo.main, FEATURE)["state"] == "listed"


def test_remove_with_no_stored_target_refuses_no_target(repo, monkeypatch, windows):
    fake = merged(repo, monkeypatch)
    refused("no-target", cleanup.remove_step, repo.main, FEATURE, "c" * 64)
    assert fake.calls == []
    untouched(repo)


def test_remove_refuses_locked_while_another_run_holds_the_target(repo, monkeypatch, windows):
    fake = merged(repo, monkeypatch)
    receipt = cleanup.list_step(repo.feature)["receipt"]
    with gc_target.take_lock(repo.main, FEATURE):
        refused("locked", cleanup.remove_step, repo.main, FEATURE, receipt)
    assert len(fake.calls) == 1
    untouched(repo)


def steps(monkeypatch):
    """Record each delete gc runs, in order: the folder removal, and each git branch delete or push."""
    import folder_remove
    done, real_folder, real_git = [], folder_remove.remove_worktree_folder, cleanup._git

    def folder(repo, path):
        done.append(("folder", Path(path).name))
        return real_folder(repo, path)

    def run_git(cwd, *args):
        if args[0] in ("branch", "push"):
            done.append((args[0], args[-1]))
        return real_git(cwd, *args)

    monkeypatch.setattr(folder_remove, "remove_worktree_folder", folder)
    monkeypatch.setattr(cleanup, "_git", run_git)
    return done


def worktrees(repo):
    return [Path(line.removeprefix("worktree ")).resolve() for line in
            git(repo.main, "worktree", "list", "--porcelain").splitlines() if line.startswith("worktree ")]


def outcome(answer):
    return [(entry["id"], entry["item"], entry["result"], entry["tip"]) for entry in answer["removed"]]


def later_command(repo):
    script = Path(cleanup.__file__).resolve()
    return f'& "{sys.executable}" "{script}" finish --repo "{Path(repo.main).resolve()}" --branch {FEATURE}'


def test_remove_deletes_the_now_items_in_order_and_saves_the_target_waiting_with_the_later_items(repo, monkeypatch, windows):
    fake = merged(repo, monkeypatch)
    feature, run = tip(repo, FEATURE), tip(repo, RUN)
    receipt = cleanup.list_step(repo.feature)["receipt"]
    done = steps(monkeypatch)
    answer = cleanup.remove_step(repo.main, FEATURE, receipt)
    assert done == [("folder", "feature-run"), ("branch", RUN), ("push", f"refs/heads/{RUN}"), ("push", f"refs/heads/{FEATURE}")]
    assert outcome(answer) == [("IT-1", "run worktree", "removed", None), ("IT-2", "run branch", "removed", run),
                               ("IT-3", "remote run branch", "removed", run), ("IT-4", "remote feature branch", "removed", feature)]
    links = {entry["item"]: entry["link"] for entry in answer["removed"] + answer["waiting"]}
    assert links == {"run worktree": None, "run branch": None, "remote run branch": None,
                     "remote feature branch": f"{GITHUB}/commit/{feature}", "feature worktree": None,
                     "feature branch": f"{GITHUB}/commit/{feature}"}
    assert all(isinstance(entry["seconds"], (int, float)) and entry["seconds"] >= 0 for entry in answer["removed"])
    assert [(entry["id"], entry["item"], entry["tip"]) for entry in answer["waiting"]] == [
        ("IT-5", "feature worktree", None), ("IT-6", "feature branch", feature)]
    assert answer["later"] == later_command(repo)
    assert answer["change"]["number"] == 7 and answer["state"] == "waiting"
    assert len(fake.calls) == 2
    assert not Path(repo.run).exists() and not Path(str(repo.run) + ".gc-removing").exists()
    assert Path(repo.run).resolve() not in worktrees(repo)
    assert local_heads(repo) == {"main", FEATURE} and set(remote_heads(repo)) == {"main"}
    target = gc_target.read_target(repo.main, FEATURE)
    assert (target["state"], target["left"], target["receipt"]) == ("waiting", ["feature worktree", "feature branch"], receipt)
    assert target["tips"]["remote feature branch"] == feature


def test_remove_run_from_the_feature_worktree_acts_on_the_same_stored_target(repo, monkeypatch, windows):
    merged(repo, monkeypatch)
    receipt = cleanup.list_step(repo.feature)["receipt"]
    answer = cleanup.remove_step(repo.feature, FEATURE, receipt)
    assert [entry["result"] for entry in answer["removed"]] == ["removed"] * 4
    assert answer["later"] == later_command(repo)


def test_remove_deletes_an_orphan_run_branch_and_a_squash_merged_feature_branch(repo, monkeypatch, windows):
    git(repo.main, "merge", "-q", "--squash", FEATURE)
    git(repo.main, "commit", "-qm", "the feature, squashed")
    git(repo.main, "push", "-q", "origin", "main")
    merged(repo, monkeypatch)
    receipt = cleanup.list_step(repo.feature)["receipt"]
    cleanup.remove_step(repo.main, FEATURE, receipt)
    assert RUN not in local_heads(repo) and set(remote_heads(repo)) == {"main"}


def test_an_absent_item_reads_already_gone_and_no_remote_run_branch_reads_none(repo, monkeypatch, windows):
    merged(repo, monkeypatch)
    git(repo.main, "push", "-q", "origin", "--delete", FEATURE, RUN)
    git(repo.main, "worktree", "remove", "--force", str(repo.run))
    git(repo.main, "branch", "-D", RUN)
    receipt = cleanup.list_step(repo.feature)["receipt"]
    answer = cleanup.remove_step(repo.main, FEATURE, receipt)
    assert outcome(answer) == [("IT-1", "run worktree", "already gone", None), ("IT-2", "run branch", "already gone", ""),
                               ("IT-3", "remote run branch", "none", ""), ("IT-4", "remote feature branch", "already gone", "")]
    assert gc_target.read_target(repo.main, FEATURE)["left"] == ["feature worktree", "feature branch"]


def test_a_refusal_not_named_in_yes_refuses_refused_and_removes_nothing(repo, monkeypatch, windows):
    merged(repo, monkeypatch)
    (Path(repo.run) / "notes.txt").write_text("not committed\n", encoding="utf-8")
    receipt = cleanup.list_step(repo.feature)["receipt"]
    refusal = refused("refused", cleanup.remove_step, repo.main, FEATURE, receipt)
    assert [(entry["code"], entry["items"]) for entry in refusal.extra["refusals"]] == [("uncommitted", ["run worktree"])]
    untouched(repo)
    assert gc_target.read_target(repo.main, FEATURE)["state"] == "listed"


def test_yes_past_each_refusal_of_the_list_goes_ahead_for_that_run(repo, monkeypatch, windows):
    forge(monkeypatch, listed(change(9, "opened", tip(repo, FEATURE))))
    (Path(repo.run) / "notes.txt").write_text("not committed\n", encoding="utf-8")
    shown = cleanup.list_step(repo.feature)
    receipt = shown["receipt"]
    refusal = refused("refused", cleanup.remove_step, repo.main, FEATURE, receipt, yes=["not-merged", "uncommitted"])
    assert [entry["code"] for entry in refusal.extra["refusals"]] == ["outside-commits"]
    untouched(repo)
    answer = cleanup.remove_step(repo.main, FEATURE, receipt, yes=["not-merged", "uncommitted", "outside-commits"])
    assert [entry["result"] for entry in answer["removed"]] == ["removed"] * 4
    assert answer["change"] is None and gc_target.read_target(repo.main, FEATURE)["change"] is None
    assert {entry["item"]: entry["link"] for entry in answer["removed"] + answer["waiting"]} == {
        item["item"]: item["link"] for item in shown["items"]}


def test_not_windows_stays_refused_whatever_yes_names(repo, monkeypatch):
    merged(repo, monkeypatch)
    real = gc_checks.check_platform
    monkeypatch.setattr(gc_checks, "check_platform", lambda: real("posix"))
    receipt = cleanup.list_step(repo.feature)["receipt"]
    refusal = refused("refused", cleanup.remove_step, repo.main, FEATURE, receipt,
                      yes=["not-windows", "in-use", "in-use-or-no-right"])
    assert [entry["code"] for entry in refusal.extra["refusals"]] == ["not-windows"]
    untouched(repo)


def test_yes_with_a_code_gc_does_not_know_is_unreadable(repo, monkeypatch, windows):
    fake = merged(repo, monkeypatch)
    receipt = cleanup.list_step(repo.feature)["receipt"]
    refused("bad-payload", cleanup.remove_step, repo.main, FEATURE, receipt, yes=["everything"])
    assert len(fake.calls) == 1
    untouched(repo)


def test_a_failed_remote_delete_keeps_what_went_before_exits_partial_and_a_second_run_removes_only_what_is_left(repo, monkeypatch, windows):
    fake = merged(repo, monkeypatch)
    feature, run = tip(repo, FEATURE), tip(repo, RUN)
    git(repo.remote, "config", "receive.denyDeletes", "true")
    receipt = cleanup.list_step(repo.feature)["receipt"]
    partial = refused("partial", cleanup.remove_step, repo.main, FEATURE, receipt)
    assert outcome(partial.extra) == [("IT-1", "run worktree", "removed", None), ("IT-2", "run branch", "removed", run)]
    failed = partial.extra["failed"]
    assert (failed["id"], failed["item"], failed["code"], failed["tip"]) == ("IT-3", "remote run branch", "remote-refused", run)
    assert "remote run branch" in partial.reason and failed["reason"] in partial.reason
    left = ["remote run branch", "remote feature branch", "feature worktree", "feature branch"]
    assert partial.extra["left"] == left
    assert not Path(repo.run).exists() and RUN not in local_heads(repo)
    assert remote_heads(repo) == {"main": tip(repo, "main"), FEATURE: feature, RUN: run}
    target = gc_target.read_target(repo.main, FEATURE)
    assert (target["state"], target["left"], target["receipt"]) == ("waiting", left, receipt)

    git(repo.remote, "config", "receive.denyDeletes", "false")
    shown = cleanup.list_step(repo.feature)
    refused("stale-list", cleanup.remove_step, repo.main, FEATURE, "c" * 64)
    done = steps(monkeypatch)
    answer = cleanup.remove_step(repo.main, FEATURE, shown["receipt"])
    assert done == [("push", f"refs/heads/{RUN}"), ("push", f"refs/heads/{FEATURE}")]
    assert outcome(answer) == [("IT-3", "remote run branch", "removed", run), ("IT-4", "remote feature branch", "removed", feature)]
    assert set(remote_heads(repo)) == {"main"}
    assert gc_target.read_target(repo.main, FEATURE)["left"] == ["feature worktree", "feature branch"]
    assert len(fake.calls) == 4


def test_a_push_after_the_check_makes_its_remote_delete_fail_and_the_pushed_commit_stays(repo, monkeypatch, windows):
    import folder_remove
    merged(repo, monkeypatch)
    receipt = cleanup.list_step(repo.feature)["receipt"]
    real, pushed = folder_remove.remove_worktree_folder, []

    def push_then_remove(main, folder):
        pushed.append(repo.commit(repo.feature, "late.txt", "late\n", "a push after the check"))
        git(repo.feature, "push", "-q", "origin", FEATURE)
        return real(main, folder)

    monkeypatch.setattr(folder_remove, "remove_worktree_folder", push_then_remove)
    partial = refused("partial", cleanup.remove_step, repo.main, FEATURE, receipt)
    assert [entry["item"] for entry in partial.extra["removed"]] == ["run worktree", "run branch", "remote run branch"]
    assert (partial.extra["failed"]["item"], partial.extra["failed"]["code"]) == ("remote feature branch", "remote-refused")
    assert remote_heads(repo)[FEATURE] == pushed[0]
    assert gc_target.read_target(repo.main, FEATURE)["left"] == ["remote feature branch", "feature worktree", "feature branch"]


def test_a_run_worktree_in_use_stays_with_its_branch_and_every_later_item(repo, monkeypatch, windows):
    import folder_remove
    merged(repo, monkeypatch)
    receipt = cleanup.list_step(repo.feature)["receipt"]

    def in_use(main, folder):
        raise cleanup.Refusal("in-use", f"a process uses {folder} as its working folder; nothing was touched",
                              folder=str(folder), winerror=32)

    monkeypatch.setattr(folder_remove, "remove_worktree_folder", in_use)
    partial = refused("partial", cleanup.remove_step, repo.main, FEATURE, receipt, yes=["in-use"])
    assert partial.extra["removed"] == [] and partial.extra["failed"]["code"] == "in-use"
    assert partial.extra["left"] == [item for _, item, _ in cleanup.ITEMS]
    untouched(repo)


@pytest.mark.parametrize("folder", ["relative", "another repository"])
def test_a_run_worktree_that_is_not_an_absolute_linked_worktree_of_the_repository_is_left_alone(repo, monkeypatch, windows, folder):
    merged(repo, monkeypatch)
    if folder == "another repository":
        git(repo.main, "worktree", "remove", "--force", str(repo.run))
        Path(repo.run).mkdir()
        git(repo.run, "init", "-q")
    receipt = cleanup.list_step(repo.feature)["receipt"]
    if folder == "relative":
        target = gc_target.read_target(repo.main, FEATURE)
        gc_target.write_target(repo.main, {**target, "run_worktree": "feature-run"})
    partial = refused("partial", cleanup.remove_step, repo.main, FEATURE, receipt)
    assert (partial.extra["failed"]["item"], partial.extra["failed"]["code"]) == ("run worktree", "not-a-worktree")
    assert partial.extra["removed"] == [] and Path(repo.run).is_dir()
    assert RUN in local_heads(repo)


def test_the_remove_command_answers_one_json_object_and_exits_0_ok_1_refused(repo, monkeypatch, windows, capsys):
    merged(repo, monkeypatch)
    (Path(repo.run) / "notes.txt").write_text("not committed\n", encoding="utf-8")
    receipt = cleanup.list_step(repo.feature)["receipt"]
    code, answer = run_cli(capsys, "remove", "--repo", str(repo.main), "--branch", FEATURE, "--receipt", "c" * 64)
    assert code == 1 and answer["error"]["code"] == "stale-list" and answer["error"]["list"]["receipt"] == receipt
    code, answer = run_cli(capsys, "remove", "--repo", str(repo.main), "--branch", FEATURE, "--receipt", receipt)
    assert code == 1 and answer["error"]["code"] == "refused"
    code, answer = run_cli(capsys, "remove", "--repo", str(repo.main), "--branch", FEATURE, "--receipt", receipt,
                           "--yes", "uncommitted,not-merged", "--yes", "outside-commits")
    assert code == 0 and answer["ok"] is True and [entry["result"] for entry in answer["removed"]] == ["removed"] * 4
    assert answer["later"] == later_command(repo)


def test_the_remove_command_runs_in_the_current_folder_by_default(repo, monkeypatch, windows, capsys):
    merged(repo, monkeypatch)
    receipt = cleanup.list_step(repo.feature)["receipt"]
    monkeypatch.chdir(repo.main)
    code, answer = run_cli(capsys, "remove", "--branch", FEATURE, "--receipt", receipt)
    assert code == 0 and answer["state"] == "waiting"


@pytest.mark.parametrize("argv", [["remove"], ["remove", "--branch", FEATURE], ["remove", "--receipt", "c" * 64],
                                  ["remove", "--branch", FEATURE, "--receipt", "c" * 64, "--yes", "everything"]])
def test_unreadable_remove_arguments_exit_2(capsys, argv):
    code, answer = run_cli(capsys, *argv)
    assert code == 2 and answer["error"]["code"] == "bad-payload"


# gc finish


def waiting(repo, monkeypatch, yes=()):
    """list and remove as the session runs them: the target is left `waiting` with the feature worktree and branch."""
    fake = merged(repo, monkeypatch)
    receipt = cleanup.list_step(repo.feature)["receipt"]
    cleanup.remove_step(repo.main, FEATURE, receipt, yes=yes)
    return fake


def gone(repo):
    """The target file and its lock file are deleted."""
    return not gc_target.target_path(repo.main, FEATURE).exists() and not gc_target.lock_path(repo.main, FEATURE).exists()


def test_finish_removes_the_feature_worktree_then_the_local_feature_branch_and_deletes_the_target(repo, monkeypatch, windows):
    fake = waiting(repo, monkeypatch)
    feature = tip(repo, FEATURE)
    done = steps(monkeypatch)
    answer = cleanup.finish_step(repo.main, FEATURE)
    assert done == [("folder", "feature"), ("branch", FEATURE)]
    assert [(entry["id"], entry["item"], entry["result"], entry["tip"], entry["link"]) for entry in answer["removed"]] == [
        ("IT-5", "feature worktree", "removed", None, None),
        ("IT-6", "feature branch", "removed", feature, f"{GITHUB}/commit/{feature}")]
    assert all(isinstance(entry["seconds"], (int, float)) and entry["seconds"] >= 0 for entry in answer["removed"])
    assert (answer["left"], answer["state"], answer["change"]["number"]) == ([], "done", 7)
    assert len(fake.calls) == 2
    assert not Path(repo.feature).exists() and not Path(str(repo.feature) + ".gc-removing").exists()
    assert Path(repo.feature).resolve() not in worktrees(repo)
    assert local_heads(repo) == {"main"}
    assert gone(repo)


def test_finish_with_a_branch_already_gone_reads_already_gone(repo, monkeypatch, windows):
    waiting(repo, monkeypatch)
    git(repo.main, "worktree", "remove", "--force", str(repo.feature))
    git(repo.main, "branch", "-D", FEATURE)
    answer = cleanup.finish_step(repo.main, FEATURE)
    assert [(entry["item"], entry["result"], entry["tip"]) for entry in answer["removed"]] == [
        ("feature worktree", "already gone", None), ("feature branch", "already gone", "")]
    assert gone(repo)


def still_waiting(repo, before):
    """finish removed nothing: both feature items stay and the target is as it was."""
    assert Path(repo.feature).is_dir() and FEATURE in local_heads(repo)
    assert gc_target.read_target(repo.main, FEATURE) == before


@pytest.mark.parametrize("where", ["the folder", "a subfolder"])
def test_finish_inside_the_folder_it_removes_refuses_inside_folder_and_removes_nothing(repo, monkeypatch, windows, where):
    waiting(repo, monkeypatch)
    before = gc_target.read_target(repo.main, FEATURE)
    here = Path(repo.feature) if where == "the folder" else Path(repo.feature) / "sub"
    here.mkdir(exist_ok=True)
    monkeypatch.chdir(here)
    refusal = refused("inside-folder", cleanup.finish_step, repo.main, FEATURE)
    assert "leave the folder first" in refusal.reason and same(refusal.extra["folder"], repo.feature)
    monkeypatch.undo()
    still_waiting(repo, before)


def test_finish_refuses_no_target_and_not_waiting_for_a_listed_target(repo, monkeypatch, windows):
    refused("no-target", cleanup.finish_step, repo.main, FEATURE)
    merged(repo, monkeypatch)
    cleanup.list_step(repo.feature)
    before = gc_target.read_target(repo.main, FEATURE)
    refusal = refused("not-waiting", cleanup.finish_step, repo.main, FEATURE)
    assert "listed" in refusal.reason
    still_waiting(repo, before)


def test_finish_refuses_locked_while_another_run_holds_the_target(repo, monkeypatch, windows):
    waiting(repo, monkeypatch)
    before = gc_target.read_target(repo.main, FEATURE)
    with gc_target.take_lock(repo.main, FEATURE):
        refused("locked", cleanup.finish_step, repo.main, FEATURE)
    still_waiting(repo, before)


def test_finish_on_a_system_that_is_not_windows_refuses_not_windows_and_removes_nothing(repo, monkeypatch, windows):
    import folder_remove
    waiting(repo, monkeypatch)
    before = gc_target.read_target(repo.main, FEATURE)
    monkeypatch.setattr(gc_checks, "check_platform", lambda: PLATFORM("posix"))
    monkeypatch.setattr(folder_remove, "WINDOWS", False)
    refused("not-windows", cleanup.finish_step, repo.main, FEATURE)
    still_waiting(repo, before)
