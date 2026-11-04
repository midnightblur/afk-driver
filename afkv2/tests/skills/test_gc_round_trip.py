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
WRITES = ("push", "update-ref", "worktree add", "branch -D", "worktree remove", " create", " merge", " close")


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
        if args == ["worktree", "list", "--porcelain"]:
            return ok(f"worktree {self.main}\nHEAD {MAIN_HEAD}\nbranch refs/heads/main")
        if args == ["rev-parse", "HEAD"]:
            return ok(MAIN_HEAD)
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
        if self.change and self.merge_by_push and name == self.change["target"] and sha == self.change["head"]:
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
        changes = [] if self.change is None else [
            {"id": "7", "url": self.url(), "state": self.change["state"], "head_sha": self.change["head"],
             "target": self.change["target"]}]
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
            link = self.link(tip) if item in ("remote feature branch", "feature branch") else None
            self.drop(item)
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
