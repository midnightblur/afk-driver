"""The gc script's steps. `list` fixes the target in the feature worktree and answers the list the developer says yes to."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN / "ports"))

from tracker.envelope import Refusal  # noqa: E402

import gc_checks  # noqa: E402
import gc_target  # noqa: E402

GIT_LIMIT = 60
STATES = ("listed", "waiting")
WORKTREES = ("run worktree", "feature worktree")
ITEMS = (("IT-1", "run worktree", "now"), ("IT-2", "run branch", "now"), ("IT-3", "remote run branch", "now"),
         ("IT-4", "remote feature branch", "now"), ("IT-5", "feature worktree", "later"), ("IT-6", "feature branch", "later"))
CHANGE_URL = re.compile(r"(?P<project>.+?)(?P<form>/-/merge_requests|/pull)/\d+/?")
COMMIT_FORM = {"/-/merge_requests": "/-/commit/", "/pull": "/commit/"}


def _git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          stdin=subprocess.DEVNULL, timeout=GIT_LIMIT)
    return done.returncode, done.stdout.strip(), done.stderr.strip()


def commit_link(change_url, commit):
    """The forge page of `commit`, from the link of a GitHub pull request or a GitLab merge request; None for another form."""
    match = CHANGE_URL.fullmatch(change_url or "")
    if not match or not commit:
        return None
    return match["project"] + COMMIT_FORM[match["form"]] + commit


def _names(target):
    remote = target["remote"]
    return {"run worktree": target["run_worktree"], "run branch": target["run_branch"],
            "remote run branch": f"{remote}/{target['run_branch']}", "remote feature branch": f"{remote}/{target['feature_branch']}",
            "feature worktree": target["feature_worktree"], "feature branch": target["feature_branch"]}


def _held(tips, refused):
    """The feature tips the forge holds: the remote one, and a local one that is the remote tip or has no commit outside the change."""
    local, remote = tips["feature branch"], tips["remote feature branch"]
    return {"remote feature branch": bool(remote),
            "feature branch": bool(local) and (local == remote or "feature branch" not in refused)}


def _listing(folder, branch):
    """The list of the feature worktree `folder` on `branch`, without its receipt, and the tips of its target."""
    defaults = gc_target.new_target(branch, str(folder), None, {}, "")
    names, remote = _names(defaults), defaults["remote"]
    forge = gc_checks.check_change(folder, branch)
    change = forge["change"]
    tips = gc_checks.check_tips(folder, branch, change["head_sha"] if change else None, remote)
    clean = {item: gc_checks.check_clean(names[item]) for item in WORKTREES}
    tip_refusal = tips["refusal"]
    refused = [entry["item"] for entry in tip_refusal["branches"]] if tip_refusal else []
    refusals = []
    for refusal, items in ((forge["refusal"], []), *((clean[item]["refusal"], [item]) for item in WORKTREES),
                           (tip_refusal, refused), (gc_checks.check_platform()["refusal"], list(WORKTREES))):
        if refusal:
            refusals.append({**refusal, "items": items})
    base = (change or {}).get("url") or (forge["refusal"] or {}).get("link")
    held = _held(tips["tips"], refused)
    items = []
    for ident, item, when in ITEMS:
        entry = {"id": ident, "item": item, "name": names[item], "when": when}
        if item in WORKTREES:
            entry.update(present=not clean[item]["absent"], tip=None, link=None, ignored=clean[item]["ignored"])
        else:
            commit = tips["tips"][item]
            entry.update(present=bool(commit), tip=commit, link=commit_link(base, commit) if held.get(item) else None)
        items.append(entry)
    listing = {"branch": branch, "feature_worktree": names["feature worktree"], "run_branch": names["run branch"],
               "run_worktree": names["run worktree"], "remote": remote, "change": change, "items": items,
               "refusals": refusals, "state": "listed"}
    return listing, tips["tips"]


def feature_worktree(cwd):
    """(folder, branch) of the linked worktree `cwd` is in. The main checkout, no branch, or a run branch refuses."""
    def refuse(why):
        return Refusal("not-feature-worktree", f"{cwd} {why}; run gc list in the feature worktree, on its feature branch")

    code, out, error = _git(cwd, "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-dir", "--git-common-dir")
    if code != 0:
        raise refuse(f"is not in a git worktree: {error}")
    top, git_dir, common = out.splitlines()
    if Path(git_dir).resolve() == Path(common).resolve():
        raise refuse("is in the main checkout")
    code, branch, _ = _git(cwd, "symbolic-ref", "--quiet", "--short", "HEAD")
    if code != 0 or not branch:
        raise refuse("has no branch checked out")
    if branch.endswith(gc_target.RUN_SUFFIX):
        raise refuse(f"is on the run branch {branch}")
    return Path(top), branch


def _shown(target):
    return {key: value for key, value in target.items() if key != "schema"}


def _waiting(cwd, branch):
    """The stored target of `branch` when it is `waiting`; None when there is none or it is `listed`."""
    target = gc_target.read_target(cwd, branch)
    if target is not None and target["state"] not in STATES:
        path = gc_target.target_path(cwd, branch)
        raise Refusal("bad-target", f"{path} has state {target['state']!r}, not listed or waiting; list again")
    return target if target is not None and target["state"] == "waiting" else None


def list_step(cwd, branch=None, lock=None):
    """With no `branch`: list in the feature worktree `cwd` under the target's lock (`lock` when the caller holds it).
    A `waiting` target is answered as stored. Otherwise run every check, write the target as `listed`, replacing a
    `listed` or broken one, and answer the list with its receipt. With `branch`: only show its `waiting` target."""
    if branch is not None:
        target = _waiting(cwd, branch)
        if target is None:
            raise Refusal("no-target", f"no waiting gc target for {branch}; run gc list in its feature worktree")
        return _shown(target)
    folder, branch = feature_worktree(cwd)
    held = lock or gc_target.take_lock(folder, branch)
    try:
        try:
            target = _waiting(folder, branch)
        except Refusal as broken:
            if broken.code != "bad-target":
                raise
            target = None  # A broken target is replaced: the developer lists again.
        if target is not None:
            return _shown(target)
        listing, tips = _listing(folder, branch)
        listing["receipt"] = gc_target.receipt_of(listing)
        gc_target.write_target(folder, gc_target.new_target(branch, str(folder), listing["change"], tips, listing["receipt"]))
        return listing
    finally:
        if lock is None:
            held.release()
