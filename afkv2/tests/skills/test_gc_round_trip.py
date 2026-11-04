"""The live round trip script with git, gh, glab, the forge port and the gc script faked in-process: no command runs and no forge is called."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AFKV2 / "tests" / "live"))

import gc_round_trip as live  # noqa: E402

BASE, MAIN_HEAD = "b" * 40, "a" * 40
GITLAB_PROJECT = "group/test-project"  # a hypothetical project; the script knows its own only by a hash
ORIGINS = {"github": "https://github.com/midnightblur/afk-driver.git", "gitlab": f"git@gitlab.com:{GITLAB_PROJECT}.git"}
PROJECT_PAGES = {"github": "https://github.com/midnightblur/afk-driver", "gitlab": f"https://gitlab.com/{GITLAB_PROJECT}"}
COMMIT_FORMS = {"github": "/commit/", "gitlab": "/-/commit/"}
CHANGE_FORMS = {"github": "/pull/", "gitlab": "/-/merge_requests/"}
NOW = ("run worktree", "run branch", "remote run branch", "remote feature branch")
WRITES = ("git push", "update-ref", "worktree add", "branch -D", "worktree remove", " create", " merge", " close")


def ok(out=""):
    return 0, out, ""


class World:
    """One forge, its remote branches, the local branches and worktree folders, and the gc script, all in-process.
    `fail` maps a text of a command line to the error that command gives; `leave` names an item gc says it removed
    but leaves; `merge_by_push` is False when the forge never marks the change merged."""

    def __init__(self, root, forge, origin=None):
        self.forge, self.origin = forge, origin or ORIGINS[forge]
        self.main = Path(root) / "repo"
        self.main.mkdir()
        self.remote, self.local, self.change, self.commits = {"main": BASE}, {}, None, 0
        self.calls, self.fail, self.leave, self.merge_by_push = [], {}, None, True
        self.headless_reads = 0  # change-list reads that show the new change without its head commit
        self.head, self.push_url, self.after_finish, self.unreported, self.unlinked = MAIN_HEAD, None, None, None, None
        self.feature = self.folder = None
        self.target = False

    def __call__(self, args, cwd, stdin=None):
        args = [str(arg) for arg in args]
        self.calls.append(args)
        line = " ".join(args)
        for text, reason in self.fail.items():
            if text in line:
                return 1, "", reason
        if args[0] == "git":
            return self.git(args[1:])
        if args[0] in ("gh", "glab"):
            return self.cli(args)
        if Path(args[1]).name == "forge_cli.py":
            return self.port(json.loads(stdin))
        assert Path(args[1]).name == "cleanup.py", args
        return self.gc(args[2:])

    def url(self):
        return PROJECT_PAGES[self.forge] + CHANGE_FORMS[self.forge] + "7"

    def link(self, tip):
        return PROJECT_PAGES[self.forge] + COMMIT_FORMS[self.forge] + tip

    def git(self, args):
        if args == ["remote", "get-url", "origin"]:
            return ok(self.origin)
        if args == ["remote", "get-url", "--push", "origin"]:
            return ok(self.push_url or self.origin)
        if args == ["worktree", "list", "--porcelain"]:
            return ok(f"worktree {self.main}\nHEAD {MAIN_HEAD}\nbranch refs/heads/main")
        if args == ["rev-parse", "HEAD"]:
            return ok(self.head)
        if args == ["rev-parse", "FETCH_HEAD"]:
            return ok(BASE)
        if args[0] in ("fetch", "add"):
            return ok()
        if args[:2] == ["worktree", "add"]:
            if args[2] == "-b":
                self.local[args[3]], self.feature, self.folder = args[5], args[3], args[4]
            Path(args[-2] if args[2] == "-b" else args[2]).mkdir(parents=True)
            return ok()
        if args[0] in ("write-tree", "mktree"):
            return ok("e" * 40)
        if args[0] == "commit-tree":
            self.commits += 1
            return ok(f"{self.commits:040x}")
        if args[0] == "update-ref":
            name = args[1].removeprefix("refs/heads/")
            assert self.local.get(name, "") == args[3], args
            self.local[name] = args[2]
            return ok()
        if args[0] == "push":
            return self.push(args)
        if args[0] == "ls-remote":
            name = args[2].removeprefix("refs/heads/")
            return ok(f"{self.remote[name]}\t{args[2]}" if name in self.remote else "")
        if args[:3] == ["rev-parse", "--verify", "--quiet"]:
            name = args[3].removeprefix("refs/heads/")
            return ok(self.local[name]) if name in self.local else (1, "", "")
        if args[:2] == ["worktree", "remove"]:
            shutil.rmtree(args[-1])
            return ok()
        if args[:2] == ["branch", "-D"]:
            del self.local[args[2]]
            return ok()
        raise AssertionError(f"the fake git has no answer for {args}")

    def push(self, args):
        lease = next(arg for arg in args if arg.startswith("--force-with-lease="))
        ref, _, expect = lease.removeprefix("--force-with-lease=").partition(":")
        name = ref.removeprefix("refs/heads/")
        if self.remote.get(name, "") != expect:
            return 1, "", f"stale info for {ref}"
        if "--delete" in args:
            del self.remote[name]
            return ok()
        sha = args[-1].partition(":")[0]
        self.remote[name] = sha
        if self.change and self.merge_by_push and name == self.change["target"] and sha == self.change["head"]                 and self.change.get("ready", True):
            self.change["state"] = "merged"
        return ok()

    def cli(self, args):
        if args[1] == "api":
            sha = args[2].rsplit("/", 1)[1]
            return ok(sha if self.forge == "github" else json.dumps({"id": sha}))
        verb = args[2]
        if verb == "create":
            source = args[args.index("--head" if self.forge == "github" else "--source-branch") + 1]
            target = args[args.index("--base" if self.forge == "github" else "--target-branch") + 1]
            self.change = {"state": "open" if self.forge == "github" else "opened", "target": target,
                           "head": self.remote[source]}
            return ok(f"Creating the change\n{self.url()}\n")
        self.change["state"] = {"merge": "merged", "close": "closed"}[verb]
        return ok()

    def port(self, payload):
        assert payload["branch"] == self.feature, payload
        if self.change is not None and self.headless_reads:
            self.headless_reads -= 1
            self.change["ready"] = False
        elif self.change is not None:
            self.change["ready"] = True
        changes = [] if self.change is None else [
            {"id": "7", "url": self.url(), "state": self.change["state"],
             "head_sha": self.change["head"] if self.change["ready"] else "", "target": self.change["target"]}]
        return ok(json.dumps({"ok": True, "changes": changes, "count": len(changes)}))

    def names(self):
        run = self.feature + "-run"
        return {"run worktree": (self.folder + "-run", None), "run branch": (run, self.local.get(run)),
                "remote run branch": (f"origin/{run}", self.remote.get(run)),
                "remote feature branch": (f"origin/{self.feature}", self.remote.get(self.feature)),
                "feature worktree": (self.folder, None), "feature branch": (self.feature, self.local.get(self.feature))}

    def drop(self, item):
        run = self.feature + "-run"
        if item == self.leave:
            return
        if item in ("run worktree", "feature worktree"):
            shutil.rmtree(self.names()[item][0])
        else:
            holder, name = (self.remote, run) if item == "remote run branch" else (self.remote, self.feature) \
                if item == "remote feature branch" else (self.local, run if item == "run branch" else self.feature)
            del holder[name]

    def removed(self, items):
        names, entries = self.names(), []
        for item in items:
            name, tip = names[item]
            link = self.link(tip) if item in ("remote feature branch", "feature branch") and item != self.unlinked else None
            self.drop(item)
            if item != self.unreported:
                entries.append({"item": item, "name": name, "tip": tip, "link": link, "result": "removed"})
        return entries

    def gc(self, args):
        if args[0] == "list" and "--branch" in args:
            if self.target:
                return ok(json.dumps({"ok": True, "state": "waiting"}))
            return 1, json.dumps({"ok": False, "error": {"code": "no-target", "reason": "no waiting gc target"}}), ""
        if args[0] == "list":
            assert args[args.index("--repo") + 1] == self.folder, args
            self.target = True
            items = [{"item": item, "name": name, "present": True, "tip": tip,
                      "when": "now" if item in NOW else "later"} for item, (name, tip) in self.names().items()]
            return ok(json.dumps({"ok": True, "branch": self.feature, "items": items, "refusals": [], "receipt": "c" * 64,
                                  "state": "listed"}))
        if args[0] == "remove":
            assert args[args.index("--receipt") + 1] == "c" * 64, args
            return ok(json.dumps({"ok": True, "removed": self.removed(NOW), "state": "waiting"}))
        assert args[0] == "finish", args
        removed = self.removed(("feature worktree", "feature branch"))
        self.target = False
        if self.after_finish:
            self.after_finish(self)
        return ok(json.dumps({"ok": True, "removed": removed, "left": [], "state": "done"}))


@pytest.fixture(autouse=True)
def gitlab_project(monkeypatch):
    monkeypatch.setattr(live, "GITLAB_PROJECT_SHA256", hashlib.sha256(GITLAB_PROJECT.encode()).hexdigest())


def round_trip(world, stamp="20261104-120000-abcdef"):
    waits = []
    answer = live.run_round_trip(world.forge, world.main, run=world, stamp=stamp, sleep=waits.append)
    return answer, waits


def ran(world, text):
    return [call for call in world.calls if text in " ".join(call)]


@pytest.mark.parametrize("forge", ["github", "gitlab"])
def test_the_round_trip_lists_removes_finishes_and_checks_each_deleted_branch_link(tmp_path, forge):
    world = World(tmp_path, forge)
    answer, _ = round_trip(world)
    assert answer["ok"], answer
    assert [entry["item"] for entry in answer["removed"]] == [*NOW, "feature worktree", "feature branch"]
    assert [entry["item"] for entry in answer["links"]] == ["remote feature branch", "feature branch"]
    assert all(entry["link"].startswith(PROJECT_PAGES[forge] + COMMIT_FORMS[forge]) for entry in answer["links"])
    assert len(ran(world, f"{'gh' if forge == 'github' else 'glab'} api")) == 2
    assert not world.local and not Path(world.folder).exists() and not Path(world.folder + "-run").exists()
    assert answer["change"]["url"] == world.url() and world.change["state"] == "merged"
    assert not ran(world, "refs/heads/main")


def test_github_merges_the_change_into_the_scratch_target(tmp_path):
    world = World(tmp_path, "github")
    answer, _ = round_trip(world)
    assert answer["ok"], answer
    merge = ran(world, "gh pr merge")
    assert len(merge) == 1 and "--squash" in merge[0] and world.change["target"] == answer["branches"]["target"]


def test_gitlab_marks_the_change_merged_by_a_push_of_its_commit_to_the_scratch_target(tmp_path):
    world = World(tmp_path, "gitlab")
    answer, _ = round_trip(world)
    assert answer["ok"], answer
    target = answer["branches"]["target"]
    assert not ran(world, "glab mr merge")
    pushes = ran(world, f"--force-with-lease=refs/heads/{target}:{BASE}")
    assert len(pushes) == 1 and pushes[0][-1] == f"{world.change['head']}:refs/heads/{target}"


def test_a_change_the_forge_never_shows_merged_fails_after_the_wait(tmp_path):
    world = World(tmp_path, "gitlab")
    world.merge_by_push = False
    answer, waits = round_trip(world)
    assert answer["error"]["code"] == "not-merged" and answer["error"]["step"] == "merge"
    assert sum(waits) >= live.MERGE_WAIT
    assert not ran(world, "cleanup.py")


def test_an_item_gc_listed_but_left_fails_the_run(tmp_path):
    world = World(tmp_path, "github")
    world.leave = "remote run branch"
    answer, _ = round_trip(world)
    assert answer["error"]["code"] == "not-removed" and "remote run branch" in answer["error"]["reason"]


def test_a_deleted_branch_link_the_forge_no_longer_serves_fails_the_run(tmp_path):
    world = World(tmp_path, "gitlab")
    world.fail["glab api"] = "404 Commit Not Found"
    answer, _ = round_trip(world)
    assert answer["error"]["code"] == "link-gone" and "404 Commit Not Found" in answer["error"]["reason"]


@pytest.mark.parametrize("name", ["main", "feat/afkv2", "afkv2-gc-live", "afkv2-gc-live/", "afkv2-gc-live/a/b",
                                  "afkv2-gc-live/../main", "x/afkv2-gc-live/a", "afkv2-gc-live/a b"])
def test_a_branch_name_outside_the_scratch_prefix_is_refused(name):
    with pytest.raises(live.Refusal) as refused:
        live.scratch_branch(name)
    assert refused.value.code == "not-scratch"
    assert live.scratch_branch("afkv2-gc-live/20261104-120000-abcdef-target")


@pytest.mark.parametrize("stamp", ["../main", "a/b", "a b"])
def test_a_run_whose_names_leave_the_scratch_prefix_writes_nothing(tmp_path, stamp):
    world = World(tmp_path, "github")
    answer, _ = round_trip(world, stamp)
    assert answer["error"]["code"] == "not-scratch"
    assert not [call for call in world.calls if any(write in " ".join(call) for write in WRITES)]


@pytest.mark.parametrize("forge, origin", [("github", "https://github.com/someone/afk-driver.git"),
                                           ("github", "https://gitlab.com/midnightblur/afk-driver.git"),
                                           ("gitlab", "git@gitlab.com:group/another-project.git"),
                                           ("gitlab", f"https://github.com/{GITLAB_PROJECT}.git")])
def test_a_clone_of_another_project_is_refused_before_any_write(tmp_path, forge, origin):
    world = World(tmp_path, forge, origin)
    answer, _ = round_trip(world)
    assert answer["error"]["code"] == "wrong-project"
    assert not [call for call in world.calls if any(write in " ".join(call) for write in WRITES)]


def scratch_left(world):
    folders = [folder for folder in (world.folder, world.folder and world.folder + "-run") if folder and Path(folder).exists()]
    return {name for name in world.remote if name != "main"} | set(world.local) | set(folders)


@pytest.mark.parametrize("forge", ["github", "gitlab"])
def test_the_end_deletes_the_scratch_target_and_leaves_the_merged_change(tmp_path, forge):
    world = World(tmp_path, forge)
    answer, _ = round_trip(world)
    assert answer["ok"], answer
    assert answer["cleanup"] == [{"item": "remote branch", "name": answer["branches"]["target"], "result": "removed"}]
    assert world.remote == {"main": BASE} and not scratch_left(world) and world.change["state"] == "merged"


@pytest.mark.parametrize("forge, failing", [("github", "gh pr merge"), ("gitlab", "glab mr create"),
                                            ("github", "cleanup.py remove"), ("gitlab", "-run: origin")])
def test_a_failure_after_the_first_write_deletes_every_scratch_branch_and_worktree(tmp_path, forge, failing):
    world = World(tmp_path, forge)
    world.fail[failing] = "the forge said no"
    answer, _ = round_trip(world)
    assert not answer["ok"] and "the forge said no" in answer["error"]["reason"]
    assert world.remote == {"main": BASE} and not scratch_left(world)
    assert all(entry["result"] in ("removed", "closed") for entry in answer["error"]["cleanup"])
    assert not ran(world, "refs/heads/main")


def test_a_failure_after_the_change_opened_closes_it(tmp_path):
    world = World(tmp_path, "github")
    world.fail["gh pr merge"] = "not mergeable"
    answer, _ = round_trip(world)
    assert {"item": "change", "name": world.url(), "result": "closed"} in answer["error"]["cleanup"]
    assert world.change["state"] == "closed"


def test_a_failure_before_any_write_cleans_nothing(tmp_path):
    world = World(tmp_path, "gitlab")
    world.fail["fetch"] = "no network"
    answer, _ = round_trip(world)
    assert answer["error"]["code"] == "step-failed" and answer["error"]["cleanup"] == []
    assert not ran(world, "ls-remote") and not ran(world, "rev-parse --verify")


def test_a_scratch_branch_the_end_cannot_delete_fails_the_passed_run_and_names_it(tmp_path):
    world = World(tmp_path, "github")
    world.fail["--delete"] = "protected branch"
    answer, _ = round_trip(world)
    assert answer["error"]["code"] == "cleanup-failed" and answer["error"]["report"]["links"]
    target = answer["error"]["report"]["branches"]["target"]
    assert [entry["name"] for entry in answer["error"]["cleanup"] if entry["result"] == "failed"] == [target]
    assert target in answer["error"]["reason"]


def test_gitlab_pushes_to_the_target_only_after_the_forge_shows_the_change_head(tmp_path):
    world = World(tmp_path, "gitlab")
    world.headless_reads = 3
    answer, waits = round_trip(world)
    assert answer["ok"], answer
    assert len(waits) >= 3 and world.change["state"] == "merged"


def test_a_merge_on_github_pins_the_feature_tip(tmp_path):
    world = World(tmp_path, "github")
    answer, _ = round_trip(world)
    merge = ran(world, "gh pr merge")[0]
    assert answer["ok"] and merge[merge.index("--match-head-commit") + 1] == world.change["head"]


@pytest.mark.parametrize("after_finish, said", [
    (lambda world: setattr(world, "head", "d" * 40), "the main checkout moved"),
    (lambda world: world.remote.pop(world.change["target"]), "is gone"),
    (lambda world: world.change.update(state="closed"), "no longer merged"),
    (lambda world: setattr(world, "target", True), "a gc target of"),
])
def test_a_thing_gc_must_leave_that_is_gone_fails_the_run(tmp_path, after_finish, said):
    world = World(tmp_path, "github")
    world.after_finish = after_finish
    answer, _ = round_trip(world)
    assert answer["error"]["code"] == "not-kept" and said in answer["error"]["reason"]


def test_an_item_gc_listed_but_did_not_answer_removed_fails_the_run(tmp_path):
    world = World(tmp_path, "github")
    world.unreported = "run branch"
    answer, _ = round_trip(world)
    assert answer["error"]["code"] == "not-removed" and "listed present, gc answered None" in answer["error"]["reason"]


def test_a_list_with_a_refusal_removes_nothing(tmp_path, monkeypatch):
    world = World(tmp_path, "github")
    listed = world.gc

    def refusing(args):
        code, out, error = listed(args)
        if args[0] == "list" and "--branch" not in args:
            out = json.dumps({**json.loads(out), "refusals": [{"code": "uncommitted", "reason": "a file"}]})
        return code, out, error

    world.gc = refusing
    answer, _ = round_trip(world)
    assert answer["error"]["code"] == "refused" and not ran(world, "cleanup.py remove")


@pytest.mark.parametrize("forge", ["github", "gitlab"])
def test_a_deleted_branch_without_its_link_fails_the_run(tmp_path, forge):
    world = World(tmp_path, forge)
    world.unlinked = "feature branch"
    answer, _ = round_trip(world)
    assert answer["error"]["code"] == "link-gone" and "feature branch" in answer["error"]["reason"]


def test_a_commit_github_no_longer_serves_fails_the_run(tmp_path):
    world = World(tmp_path, "github")
    world.fail["gh api"] = "HTTP 404"
    answer, _ = round_trip(world)
    assert answer["error"]["code"] == "link-gone" and "HTTP 404" in answer["error"]["reason"]


def test_a_push_address_at_another_project_is_refused_before_any_write(tmp_path):
    world = World(tmp_path, "github")
    world.push_url = "https://github.com/someone/else.git"
    answer, _ = round_trip(world)
    assert answer["error"]["code"] == "wrong-project"
    assert not [call for call in world.calls if any(write in " ".join(call) for write in WRITES)]


def test_the_refusal_of_another_project_shows_no_secret_of_its_address(tmp_path):
    world = World(tmp_path, "github", "https://someone:s3cret-token@github.com/someone/else.git")
    answer, _ = round_trip(world)
    assert answer["error"]["code"] == "wrong-project" and "s3cret-token" not in json.dumps(answer)
    assert "github.com/someone/else" in answer["error"]["reason"]
