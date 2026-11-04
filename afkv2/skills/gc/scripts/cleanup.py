"""The gc script: `cleanup.py list [--repo <folder>] [--branch <name>]`. One JSON answer; exit 0 ok, 1 refused, 2 unreadable input.

`list` fixes the target in the feature worktree and answers the list the developer says yes to."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
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
NOW = tuple(item for _, item, when in ITEMS if when == "now")
PASSABLE = ("not-merged", "forge-failed", "uncommitted", "outside-commits")
NEVER_PASSED = ("not-windows", "in-use", "in-use-or-no-right")
PLAIN_NAME = re.compile(r"[A-Za-z0-9._/-]+")
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
    return Path(out.splitlines()[0].removeprefix("worktree ")).resolve()


def later_command(main, branch):
    """The later command: one PowerShell line that runs finish from the main checkout."""
    def quoted(text):
        return '"' + str(text).replace("`", "``").replace("$", "`$") + '"'

    name = branch if PLAIN_NAME.fullmatch(branch) else "'" + branch.replace("'", "''") + "'"
    return f"& {quoted(sys.executable)} {quoted(Path(__file__).resolve())} finish --repo {quoted(main)} --branch {name}"


def _checked(main, *args):
    code, out, error = _git(main, *args)
    if code != 0:
        raise Refusal("git-failed", f"git {' '.join(args[:2])}: {error}")
    return out


def _remove_run_worktree(main, target, lease):
    return folder_remove.remove_worktree_folder(main, target["run_worktree"])["result"]


def _remove_local_branch(main, name, lease):
    code, now, _ = _git(main, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}^{{commit}}")
    if code != 0 or not now:
        return "already gone"
    if now != lease:
        raise Refusal("tip-moved", f"{name} moved from {lease[:12] or 'none'} to {now[:12]} after the check; it stays")
    _checked(main, "branch", "-D", name)
    return "removed"


def _remove_remote_branch(main, remote, name, lease, absent):
    """`git push --delete` with a lease on the checked tip: the remote refuses when the tip moved (ADR-0004)."""
    ref = f"refs/heads/{name}"
    lines = _checked(main, "ls-remote", remote, ref).splitlines()
    if not any(line.split("	")[-1] == ref for line in lines):
        return absent
    code, _, error = _git(main, "push", "--quiet", f"--force-with-lease={ref}:{lease}", remote, "--delete", ref)
    if code != 0:
        raise Refusal("remote-refused", f"the remote refused the delete of {remote}/{name}: {error}")
    return "removed"


def _remove_item(main, target, item, lease):
    if item == "run worktree":
        return _remove_run_worktree(main, target, lease)
    if item == "run branch":
        return _remove_local_branch(main, target["run_branch"], lease)
    branch = target["run_branch"] if item == "remote run branch" else target["feature_branch"]
    absent = "none" if item == "remote run branch" and not lease else "already gone"
    return _remove_remote_branch(main, target["remote"], branch, lease, absent)


def _failure(error):
    if isinstance(error, Refusal):
        return {**error.extra, "code": error.code, "reason": error.reason}
    if isinstance(error, subprocess.TimeoutExpired):
        return {"code": "timed-out", "reason": f"{' '.join(error.cmd[:3])} ran past {error.timeout} s"}
    return {"code": "internal", "reason": f"{type(error).__name__}: {error}"}


def _entry(fresh_items, item, tip):
    shown = fresh_items[item]
    link = shown["link"] if shown["tip"] == tip else None
    return {"id": shown["id"], "item": item, "name": shown["name"], "tip": tip, "link": link}


def remove_step(cwd, branch, receipt, yes=()):
    """Remove the `now` items of the stored target of `branch`, after the developer's yes on the list with `receipt`.
    Runs from any folder of the repository. A list that differs from a fresh one refuses `stale-list` with it.
    The order: run worktree, local run branch, remote run branch, remote feature branch; then the target is saved
    `waiting` with what is left, and the answer gives the later command.

    `yes` names the refusals of the list the developer goes past for this run; a refusal it does not name refuses
    `refused`. Not-Windows and a folder in use stay refused whatever `yes` names."""
    unknown = sorted(set(yes) - set(PASSABLE) - set(NEVER_PASSED))
    if unknown:
        raise Refusal("bad-payload", f"--yes names no refusal gc knows: {', '.join(unknown)}; "
                                     f"name one of {', '.join(PASSABLE)}")
    target = _stored(cwd, branch)
    main = main_checkout(cwd)
    with gc_target.take_lock(main, branch):
        target = _stored(main, branch)
        fresh, fresh_tips = _listing(target["feature_worktree"], branch, cwd=main)
        fresh["receipt"] = gc_target.receipt_of(fresh)
        if target["state"] == "waiting":  # The developer said yes to the stored target, as list shows it.
            shown, change, tips, pending = _shown(target), target["change"], target["tips"], list(target["left"])
            kept = {"listed_at": target["listed_at"]}
        else:
            shown, change, tips, pending, kept = fresh, fresh["change"], fresh_tips, [item for _, item, _ in ITEMS], {}
        if receipt != shown["receipt"]:
            raise Refusal("stale-list", "the list changed after the yes; nothing was removed; answer the new list",
                          list=shown)
        held = [refusal for refusal in fresh["refusals"] if refusal["code"] not in yes or refusal["code"] in NEVER_PASSED]
        if held:
            codes = ", ".join(refusal["code"] for refusal in held)
            raise Refusal("refused", f"refused: {codes}; nothing was removed; go past a refusal only with the developer's "
                                     "yes, and never past not-windows", refusals=held)
        items = {entry["item"]: entry for entry in fresh["items"]}
        removed, failed = [], None
        for item in (item for item in NOW if item in pending):
            lease, start = tips.get(item), time.monotonic()
            try:
                result = _remove_item(main, target, item, lease)
            except Exception as error:  # Each delete stands alone: a failure keeps what went before and stops.
                failed = {**_failure(error), **_entry(items, item, lease)}
                break
            removed.append({**_entry(items, item, lease), "result": result, "seconds": round(time.monotonic() - start, 2)})
            pending.remove(item)
        gc_target.write_target(main, gc_target.new_target(
            branch, target["feature_worktree"], change, tips, receipt, run_branch=target["run_branch"],
            run_worktree=target["run_worktree"], remote=target["remote"], state="waiting", left=pending, **kept))
        waiting = [_entry(items, item, tips.get(item)) for item in pending if item not in NOW]
        if failed:
            raise Refusal("partial", f"removed {len(removed)}; the {failed['item']} failed: {failed['reason']}; "
                                     "fix the cause and run gc again for what is left",
                          removed=removed, failed=failed, left=pending, waiting=waiting)
        return {"branch": branch, "change": change, "removed": removed, "waiting": waiting,
                "later": later_command(main, branch), "state": "waiting"}


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
