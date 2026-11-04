"""The live round trip of gc on one forge: `gc_round_trip.py --forge github|gitlab [--repo <folder of the clone>]`.

The developer runs it by hand, once per forge, before gc merges. A hands-off build never runs it. In a clone of the
project the script allows for that forge, it makes scratch branches under `afkv2-gc-live/`: a target, a feature
branch with one commit in its worktree, and an orphan run branch in its run worktree. It opens a change from the
feature branch into the target and merges it: on GitHub by a squash merge, on GitLab by a push of its commit to the
target. Then it runs gc list, remove and finish, checks that each item gc listed is gone and what stays, and checks
that the forge still serves the commit of each deleted branch's link. At the end, also after a failure, it closes a
change it did not merge and deletes each scratch branch and worktree it made that is still there. Each run leaves
one merged change in the project's list. One JSON answer; exit 0 passed, 1 failed, 2 bad input."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

AFKV2 = Path(__file__).resolve().parents[2]
CLEANUP = AFKV2 / "skills" / "gc" / "scripts" / "cleanup.py"
FORGE = AFKV2 / "ports" / "forge" / "forge_cli.py"
PLUGIN_REPOSITORY = AFKV2.parent
sys.path.insert(0, str(AFKV2 / "ports"))
sys.path.insert(0, str(AFKV2 / "scripts"))

import afkv2_config  # noqa: E402
from tracker import envelope  # noqa: E402
from tracker.envelope import Refusal  # noqa: E402

FORGES = ("github", "gitlab")
GITLAB_PROJECT_SHA256 = "9641736ab3f2e8a9a58c5e6aacfd858d55cd09d1ff876fdfb305e438190b855e"  # the GitLab test project, by hash
SCRATCH = "afkv2-gc-live/"
SCRATCH_NAME = re.compile(re.escape(SCRATCH) + r"[A-Za-z0-9][A-Za-z0-9-]*")
FILE = "afkv2-gc-live.txt"
COMMAND_LIMIT = 600
MERGE_WAIT, POLL = 180, 5
CHANGE_URL = re.compile(r"https://\S+?(?:/-/merge_requests|/pull)/(\d+)")
COMMIT_FORM = {"github": "/commit/", "gitlab": "/-/commit/"}
BRANCH_ITEMS = ("remote feature branch", "feature branch")


def run_command(args, cwd, stdin=None):
    """(exit code, output, error) of one command. No command reads the terminal."""
    feed = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}
    try:
        done = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=COMMAND_LIMIT, **feed)
    except subprocess.TimeoutExpired:
        return 124, "", f"ran past {COMMAND_LIMIT} s"
    except OSError as error:
        return 127, "", str(error)
    return done.returncode, done.stdout.strip(), done.stderr.strip()


def scratch_branch(name):
    """`name` when it is a scratch branch of this script: the prefix, then letters, digits and `-`. Every branch the
    script creates, pushes or deletes passes here first."""
    if not SCRATCH_NAME.fullmatch(name or ""):
        raise Refusal("not-scratch", f"{name!r} is outside the scratch prefix {SCRATCH}: the round trip writes no "
                                     "other branch", branch=name)
    return name


def github_project():
    """This plugin's GitHub project: `tracker.repo` of the plugin repository's `.afkv2/config.json`, with a
    `github-issues` tracker."""
    config = afkv2_config.read_config(PLUGIN_REPOSITORY)
    tracker = (config.get("tracker") if config.get("ok") else None) or {}
    repo = tracker.get("repo") if tracker.get("kind") == "github-issues" else None
    if not isinstance(repo, str) or not repo.strip():
        failure = (config.get("error") or {}).get("reason")
        raise Refusal("no-project", f"the config of {PLUGIN_REPOSITORY} names no github-issues tracker repo: the "
                                    "GitHub round trip knows its project only from there"
                                    + (f"; {failure}" if failure else ""), step="project")
    return repo.strip().lower()


def allowed_project(forge, host, path):
    """GitHub: this plugin's repository. GitLab: the GitLab test project only."""
    if forge == "github":
        return host == "github.com" and path.lower() == github_project()
    return host == "gitlab.com" and hashlib.sha256(path.lower().encode("utf-8")).hexdigest() == GITLAB_PROJECT_SHA256


def project_of(url):
    """(host, project path) of an https, ssh or scp-form remote."""
    url = url.strip()
    if "://" in url:
        parts = urllib.parse.urlsplit(url)
        host, path = parts.hostname or "", parts.path
    else:
        host, _, path = url.rpartition("@")[2].partition(":")
    return host.lower(), path.strip("/").removesuffix(".git")


class RoundTrip:
    """One round trip in the clone whose main checkout is `main`. Every command goes through `run`."""

    def __init__(self, forge, main, run, stamp, sleep, merge_wait):
        self.forge, self.main, self.run, self.sleep, self.merge_wait = forge, Path(main), run, sleep, merge_wait
        self.stamp = stamp
        self.feature = scratch_branch(SCRATCH + stamp)
        self.run_branch, self.target = scratch_branch(self.feature + "-run"), scratch_branch(self.feature + "-target")
        self.folder = Path(str(self.main) + "-worktrees") / ("afkv2-gc-live-" + stamp)
        self.run_folder = Path(str(self.folder) + "-run")
        self.host = self.project = self.change = self.feature_tip = None
        self.folders, self.locals, self.remotes = [], [], []  # what this run made, each noted before it is made

    def call(self, step, args, cwd=None, stdin=None):
        code, out, error = self.run(list(args), str(cwd or self.main), stdin)
        if code != 0:
            raise Refusal("step-failed", f"{step}: {' '.join(str(arg) for arg in args[:3])} exited {code}: {error or out}",
                          step=step)
        return out

    def git(self, step, *args, cwd=None, stdin=None):
        return self.call(step, ["git", *args], cwd, stdin)

    def _push(self, step, sha, name, expect):
        """Push `sha` to the remote branch `name` only while the remote holds `expect` there; empty: no branch."""
        ref = f"refs/heads/{scratch_branch(name)}"
        if name not in self.remotes:
            self.remotes.append(name)
        self.git(step, "push", "--quiet", f"--force-with-lease={ref}:{expect}", "origin", f"{sha}:{ref}")

    def _remote_tip(self, step, name):
        ref = f"refs/heads/{name}"
        lines = self.git(step, "ls-remote", "origin", ref).splitlines()
        return next((line.split("\t")[0] for line in lines if line.split("\t")[-1] == ref), "")

    def _port(self, step, verb, payload):
        out = self.call(step, [sys.executable, str(FORGE), verb], stdin=json.dumps(payload))
        answer = json.loads(out)
        if not answer.get("ok"):
            raise Refusal("step-failed", f"{step}: forge {verb}: {answer.get('error')}", step=step)
        return answer

    def _gc(self, step, *args, cwd=None):
        """One gc step through its command, as the developer runs it. A refused answer fails the run."""
        code, out, error = self.run([sys.executable, str(CLEANUP), *args], str(cwd or self.main), None)
        try:
            answer = json.loads(out)
        except ValueError:
            raise Refusal("step-failed", f"{step}: no JSON answer, exit {code}: {error or out}", step=step) from None
        if step and not answer.get("ok"):
            failure = answer.get("error") or {}
            raise Refusal("gc-failed", f"{step}: {failure.get('code')}: {failure.get('reason')}", step=step,
                          answer=failure)
        return answer

    def read_origin(self):
        """The project of origin. Its fetch and its push address must both name the allowed project. A refusal
        shows only host and path: an address can hold a credential."""
        self.host, self.project = project_of(self.git("project", "remote", "get-url", "origin"))
        pushed = project_of(self.git("project", "remote", "get-url", "--push", "origin"))
        for host, path in ((self.host, self.project), pushed):
            if not allowed_project(self.forge, host, path):
                allowed = "this plugin repository" if self.forge == "github" else "the GitLab test project"
                raise Refusal("wrong-project", f"origin names {host}/{path}: the {self.forge} round trip runs only in a "
                                               f"clone of {allowed}, for fetch and push", step="project")

    def make_branches(self, base):
        """The feature worktree with one commit on the feature branch, the run worktree on an orphan run branch, and
        the target at `base`, each pushed. `commit-tree` makes each commit: a scratch commit runs no commit hook."""
        self.folders.append(self.folder)
        self.locals.append(self.feature)
        self.git("feature worktree", "worktree", "add", "-b", scratch_branch(self.feature), str(self.folder), base)
        (self.folder / FILE).write_text(f"gc live round trip {self.stamp}\n", encoding="utf-8")
        self.git("feature commit", "add", FILE, cwd=self.folder)
        tree = self.git("feature commit", "write-tree", cwd=self.folder)
        self.feature_tip = self.git("feature commit", "commit-tree", tree, "-p", base, "-m",
                                    f"afkv2 gc live round trip {self.stamp}", cwd=self.folder)
        self.git("feature commit", "update-ref", f"refs/heads/{scratch_branch(self.feature)}", self.feature_tip, base, cwd=self.folder)
        empty = self.git("run branch", "mktree", stdin="")
        run_tip = self.git("run branch", "commit-tree", empty, "-m", f"afkv2 gc live run branch {self.stamp}")
        self.locals.append(self.run_branch)
        self.git("run branch", "update-ref", f"refs/heads/{scratch_branch(self.run_branch)}", run_tip, "")
        self.folders.append(self.run_folder)
        self.git("run worktree", "worktree", "add", str(self.run_folder), self.run_branch)
        for name, sha in ((self.target, base), (self.feature, self.feature_tip), (self.run_branch, run_tip)):
            self._push("push", sha, name, "")

    def open_change(self):
        title = f"afkv2 gc live round trip {self.stamp}"
        body = "A scratch change of the gc live round trip. The round trip merges it and deletes its branches."
        if self.forge == "github":
            args = ["gh", "pr", "create", "-R", self.project, "--base", self.target, "--head", self.feature,
                    "--title", title, "--body", body]
        else:
            args = ["glab", "mr", "create", "-R", self.project, "--source-branch", self.feature, "--target-branch",
                    self.target, "--title", title, "--description", body, "--yes"]
        out = self.call("open change", args)
        match = CHANGE_URL.search(out)
        if not match:
            raise Refusal("step-failed", f"open change: no change link in the answer: {out}", step="open change")
        self.change = {"number": int(match[1]), "url": match[0], "state": "open"}

    def _shown(self, step):
        """The change as the forge port lists it, as gc reads it; empty when the list lacks it."""
        answer = self._port(step, "change-list", {"forge": self.forge, "branch": self.feature})
        return next((item for item in answer.get("changes") or []
                     if isinstance(item, dict) and str(item.get("id")) == str(self.change["number"])), {})

    def _wait(self, code, field, value):
        """Read the change until its `field` is `value`, at most `merge_wait` seconds; then refuse `code`."""
        waited = 0
        while (shown := self._shown("merge")).get(field) != value:
            if waited >= self.merge_wait:
                raise Refusal(code, f"after {waited} s the forge shows change {self.change['number']} with {field} "
                                    f"{shown.get(field)!r}, not {value!r}", step="merge")
            self.sleep(POLL)
            waited += POLL

    def merge(self, base):
        """GitHub: a squash merge on the feature tip. GitLab: once the change shows the feature tip as its head, a
        push of that tip to the target, which GitLab marks merged when the change's commits reach its target. Then
        wait until the forge port shows it merged."""
        if self.forge == "github":
            self.call("merge", ["gh", "pr", "merge", str(self.change["number"]), "-R", self.project, "--squash",
                                "--match-head-commit", self.feature_tip])
        else:
            self._wait("no-head", "head_sha", self.feature_tip)
            self._push("merge", self.feature_tip, self.target, base)
        self._wait("not-merged", "state", "merged")
        self.change["state"] = "merged"

    def _still_there(self, item):
        """Whether an item of the list is still there, read from git and the remote itself."""
        if item in ("run worktree", "feature worktree"):
            return (self.run_folder if item == "run worktree" else self.folder).exists()
        name = self.run_branch if item in ("run branch", "remote run branch") else self.feature
        if item.startswith("remote "):
            return bool(self._remote_tip("check removed", name))
        code, _, _ = self.run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"], str(self.main), None)
        return code == 0

    def check_removed(self, listing, removed):
        results = {entry["item"]: entry.get("result") for entry in removed}
        problems = []
        for entry in listing["items"]:
            item = entry["item"]
            if entry.get("present") and results.get(item) != "removed":
                problems.append(f"{item} {entry['name']}: listed present, gc answered {results.get(item)}")
            if self._still_there(item):
                problems.append(f"{item} {entry['name']} is still there")
        if problems:
            raise Refusal("not-removed", "gc left items it listed: " + "; ".join(problems), step="check removed")

    def _served(self, sha):
        """Whether the forge serves commit `sha` of the project, and the error when it does not."""
        if self.forge == "github":
            code, out, error = self.run(["gh", "api", f"repos/{self.project}/commits/{sha}", "--jq", ".sha"],
                                        str(self.main), None)
            return code == 0 and out == sha, error or out
        endpoint = f"projects/{urllib.parse.quote(self.project, safe='')}/repository/commits/{sha}"
        code, out, error = self.run(["glab", "api", endpoint], str(self.main), None)
        try:
            served = code == 0 and json.loads(out).get("id") == sha
        except (ValueError, AttributeError):
            served = False
        return served, error or out

    def check_links(self, removed):
        """Each deleted branch's commit link names this project and the branch tip, and the forge still serves it."""
        links = [entry for entry in removed if entry["item"] in BRANCH_ITEMS and entry.get("tip")]
        if not links:
            raise Refusal("link-gone", "gc deleted no feature branch with a tip, so no commit link is checked",
                          step="check links")
        checked = []
        for entry in links:
            if not entry.get("link"):
                raise Refusal("link-gone", f"gc gave no commit link for the deleted {entry['item']} at "
                                           f"{entry['tip'][:12]}", step="check links")
            expected = f"https://{self.host}/{self.project}{COMMIT_FORM[self.forge]}{entry['tip']}"
            if entry["link"].casefold() != expected.casefold():
                raise Refusal("link-gone", f"the {entry['item']} link {entry['link']} is not {expected}",
                              step="check links")
            served, error = self._served(entry["tip"])
            if not served:
                raise Refusal("link-gone", f"the forge does not serve {entry['link']} of the deleted {entry['item']}: "
                                           f"{error}", step="check links")
            checked.append({"item": entry["item"], "link": entry["link"], "served": True})
        return checked

    def check_stays(self, main_head):
        """What gc must leave: the main checkout's commit, the target, the merged change; and no gc target is left."""
        problems = []
        if self.git("check stays", "rev-parse", "HEAD") != main_head:
            problems.append("the main checkout moved off its commit")
        if not self._remote_tip("check stays", self.target):
            problems.append(f"the scratch target {self.target} is gone")
        if self._shown("check stays").get("state") != "merged":
            problems.append(f"change {self.change['number']} is no longer merged")
        left = self._gc(None, "list", "--repo", str(self.main), "--branch", self.feature)
        if (left.get("error") or {}).get("code") != "no-target":
            problems.append(f"a gc target of {self.feature} is left: {left}")
        if problems:
            raise Refusal("not-kept", "; ".join(problems), step="check stays")
        return ["main checkout commit", f"target {self.target}", f"change {self.change['number']} merged",
                "no gc target"]

    def go(self):
        self.read_origin()
        main_head = self.git("main checkout", "rev-parse", "HEAD")
        self.git("base", "fetch", "--quiet", "--no-tags", "origin", "HEAD")
        base = self.git("base", "rev-parse", "FETCH_HEAD")
        self.make_branches(base)
        self.open_change()
        self.merge(base)
        listing = self._gc("gc list", "list", "--repo", str(self.folder), cwd=self.folder)
        if listing["refusals"]:
            codes = ", ".join(refusal["code"] for refusal in listing["refusals"])
            raise Refusal("refused", f"gc list refused {codes}; a round trip expects none", step="gc list",
                          refusals=listing["refusals"])
        removal = self._gc("gc remove", "remove", "--repo", str(self.main), "--branch", self.feature,
                           "--receipt", listing["receipt"])
        finish = self._gc("gc finish", "finish", "--repo", str(self.main), "--branch", self.feature)
        removed = removal["removed"] + finish["removed"]
        self.check_removed(listing, removed)
        links = self.check_links(removed)
        stays = self.check_stays(main_head)
        return {"forge": self.forge, "project": self.project, "change": dict(self.change),
                "branches": {"feature": self.feature, "run": self.run_branch, "target": self.target},
                "listed": [{"item": entry["item"], "name": entry["name"], "present": entry["present"]}
                           for entry in listing["items"]],
                "removed": removed, "links": links, "stays": stays}


    def _close(self):
        number, verb = str(self.change["number"]), ("pr" if self.forge == "github" else "mr")
        self.call("clean up", ["gh" if self.forge == "github" else "glab", verb, "close", number, "-R", self.project])
        return "closed"

    def _drop_folder(self, folder):
        if not folder.exists():
            return None
        self.git("clean up", "worktree", "remove", "--force", str(folder))
        return "removed"

    def _drop_local(self, name):
        code, _, _ = self.run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"], str(self.main), None)
        if code != 0:
            return None
        self.git("clean up", "branch", "-D", scratch_branch(name))
        return "removed"

    def _drop_remote(self, name):
        tip = self._remote_tip("clean up", name)
        if not tip:
            return None
        ref = f"refs/heads/{scratch_branch(name)}"
        self.git("clean up", "push", "--quiet", f"--force-with-lease={ref}:{tip}", "origin", "--delete", ref)
        return "removed"

    def clean_up(self):
        """Close a change this run opened and did not merge, then remove each worktree, local branch and remote branch
        this run made that is still there. Each step stands alone; the answer names each one done or failed."""
        steps = []
        if self.change and self.change["state"] != "merged":
            steps.append(("change", self.change["url"], self._close))
        steps += [("worktree", str(folder), lambda folder=folder: self._drop_folder(folder)) for folder in self.folders]
        steps += [("branch", name, lambda name=name: self._drop_local(name)) for name in reversed(self.locals)]
        steps += [("remote branch", name, lambda name=name: self._drop_remote(name)) for name in reversed(self.remotes)]
        results = []
        for item, name, action in steps:
            try:
                result = action()
            except Exception as error:
                results.append({"item": item, "name": name, "result": "failed",
                                "reason": error.reason if isinstance(error, Refusal) else f"{type(error).__name__}: {error}"})
                continue
            if result:
                results.append({"item": item, "name": name, "result": result})
        return results


def main_checkout(repo, run):
    code, out, error = run(["git", "worktree", "list", "--porcelain"], str(repo), None)
    if code != 0 or not out.startswith("worktree "):
        raise Refusal("bad-payload", f"{repo} is not in a git repository: {error or out}")
    return Path(out.splitlines()[0].removeprefix("worktree "))


def run_round_trip(forge, repo, run=run_command, stamp=None, sleep=time.sleep, merge_wait=MERGE_WAIT):
    """One live round trip of gc on `forge` in the clone that holds `repo`; the answer of the run."""
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-" + secrets.token_hex(3)
    trip = None
    try:
        try:
            if forge not in FORGES:
                raise Refusal("bad-payload", f"--forge is {forge!r}, not one of {', '.join(FORGES)}")
            trip = RoundTrip(forge, main_checkout(repo, run), run, stamp, sleep, merge_wait)
            answer = envelope.ok(**trip.go())
        except Refusal as refusal:
            answer = envelope.fail(refusal.code, refusal.reason, **refusal.extra)
        except Exception as error:
            answer = envelope.fail("internal", f"{type(error).__name__}: {error}")
    finally:  # Also on an interrupt: the scratch branches go.
        cleanup = trip.clean_up() if trip else []
    if not answer["ok"]:
        answer["error"]["cleanup"] = cleanup
        return answer
    failed = [entry for entry in cleanup if entry["result"] == "failed"]
    if failed:
        shown = "; ".join(f"{entry['item']} {entry['name']}: {entry['reason']}" for entry in failed)
        return envelope.fail("cleanup-failed", f"the round trip passed, but the end left: {shown}; delete these by hand",
                             report=answer, cleanup=cleanup)
    return {**answer, "cleanup": cleanup}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="gc_round_trip.py")
    parser.add_argument("--forge", required=True, choices=FORGES)
    parser.add_argument("--repo", default=".")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    answer = run_round_trip(args.forge, args.repo)
    print(json.dumps(answer, indent=1))
    return envelope.exit_code(answer)


if __name__ == "__main__":
    sys.exit(main())
