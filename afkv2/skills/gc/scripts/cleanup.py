"""The gc script: `cleanup.py list [--repo <folder>] [--branch <name>]`. One JSON answer; exit 0 ok, 1 refused, 2 unreadable input.

`list` fixes the target in the feature worktree and answers the list the developer says yes to."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN / "ports"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tracker import envelope  # noqa: E402
from tracker.envelope import Refusal  # noqa: E402

import folder_remove  # noqa: E402
import gc_checks  # noqa: E402
import gc_target  # noqa: E402
from folder_remove import REMOVING_SUFFIX  # noqa: E402

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


def _tips(folder, branch, head, remote):
    """The tip check. A change head the check cannot compare with, one this clone lacks, leaves each feature tip
    unchecked, which refuses `outside-commits` with the reason."""
    try:
        return gc_checks.check_tips(folder, branch, head, remote)
    except Refusal as failed:
        if head is None:
            raise
        reason = failed.reason
    tips = gc_checks.check_tips(folder, branch, None, remote)
    if tips["refusal"]:
        tips["refusal"]["reason"] = f"each feature tip is unchecked: the compare with the change head {head[:12]} failed: {reason}"
    return tips


def _listing(folder, branch, cwd=None):
    """The list of the feature worktree `folder` on `branch`, without its receipt, and the tips of its target.
    git and the forge run in `cwd`, any folder of the repository (default `folder`); the list is the same from each."""
    cwd = folder if cwd is None else cwd
    defaults = gc_target.new_target(branch, str(folder), None, {}, "")
    names, remote = _names(defaults), defaults["remote"]
    forge = gc_checks.check_change(cwd, branch)
    change = forge["change"]
    tips = _tips(cwd, branch, change["head_sha"] if change else None, remote)
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
            leftover = Path(names[item] + REMOVING_SUFFIX)
            entry.update(present=not clean[item]["absent"], tip=None, link=None, ignored=clean[item]["ignored"],
                         leftover=str(leftover) if leftover.is_dir() else None)
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


def _stored(cwd, branch):
    """The stored target of `branch`, `listed` or `waiting`. None refuses `no-target`, another state `bad-target`."""
    target = gc_target.read_target(cwd, branch)
    if target is None:
        raise Refusal("no-target", f"no gc target for {branch}; run gc list in its feature worktree")
    if target["state"] not in STATES:
        path = gc_target.target_path(cwd, branch)
        raise Refusal("bad-target", f"{path} has state {target['state']!r}, not listed or waiting; list again")
    return target


def main_checkout(cwd):
    """The main checkout of the repository `cwd` is in: the first worktree git lists."""
    code, out, error = _git(cwd, "worktree", "list", "--porcelain")
    if code != 0:
        raise Refusal("git-failed", f"git worktree list in {cwd}: {error}")
    return Path(out.splitlines()[0].removeprefix("worktree "))


def remove_step(cwd, branch, receipt, yes=()):
    """Remove the `now` items of the stored target of `branch`, after the developer's yes on the list with `receipt`.
    Runs from any folder of the repository. A list that differs from a fresh one refuses `stale-list` with it."""
    target = _stored(cwd, branch)
    main = main_checkout(cwd)
    with gc_target.take_lock(main, branch):
        target = _stored(main, branch)
        fresh, tips = _listing(target["feature_worktree"], branch, cwd=main)
        fresh["receipt"] = gc_target.receipt_of(fresh)
        if receipt != fresh["receipt"]:
            raise Refusal("stale-list", "the list changed after the yes; nothing was removed; answer the new list",
                          list=fresh)
        return {}


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Refusal("bad-payload", f"{self.prog}: {message}")


def _parser():
    parser = _Parser(prog="cleanup.py", add_help=False)
    steps = parser.add_subparsers(dest="step", required=True, parser_class=_Parser)
    listing = steps.add_parser("list", add_help=False)
    listing.add_argument("--repo", default=".")
    listing.add_argument("--branch")
    return parser


STEPS = {"list": lambda args: list_step(args.repo, branch=args.branch)}


def main(argv=None):
    try:
        args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
        answer = envelope.ok(**STEPS[args.step](args))
    except Refusal as refusal:
        answer = envelope.fail(refusal.code, refusal.reason, **refusal.extra)
    except Exception as error:
        answer = envelope.fail("internal", f"{type(error).__name__}: {error}")
    print(json.dumps(answer))
    return envelope.exit_code(answer)


if __name__ == "__main__":
    sys.exit(main())
