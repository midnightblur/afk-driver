"""Main checkout sync: the one mutation a main-checkout session may run (`git pull --ff-only`).

The guard calls `authorize` at PreToolUse; the git backstop calls `allows` for the branch update
and `finish` at committed/aborted. The record is `<common>/afk-session/sync-<session>.json`.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import protected_branch_guard as guard

TTL_SECONDS = 120
MID_OPERATION = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG", "rebase-merge", "rebase-apply",
                 "sequencer")
ZEROS = re.compile(r"^0+$")


def out(root: str, *args: str) -> str | None:
    done = guard.git(Path(root), *args)
    return done.stdout.strip() if done.returncode == 0 else None


def check(place: dict, remote: str | None, branch: str | None) -> tuple[str | None, dict | None]:
    """(refusal cause, None) or (None, record fields) for a sync of this main checkout."""
    root, gitdir = place["root"], Path(place["gitdir"])
    name = guard.branch_of(place)
    if name is None:
        return "the main checkout has a detached or unborn HEAD", None
    busy = [item for item in MID_OPERATION if (gitdir / item).exists()]
    if busy:
        return f"a git operation is in progress in the main checkout ({busy[0]})", None
    configured = out(root, "config", "--get", f"branch.{name}.remote")
    merge = out(root, "config", "--get", f"branch.{name}.merge")
    upstream = out(root, "rev-parse", "--symbolic-full-name", f"{name}@{{u}}")
    if not configured or configured == "." or not merge or not upstream:
        return f"branch `{name}` has no upstream on a remote", None
    default = guard.lookup_module().default_branch(Path(place["common"]), configured)
    is_base = name == default if default else name in ("main", "master")
    if not is_base:
        return f"`{name}` is not the base branch (`{default or 'main'}`)", None
    if remote is not None and (remote, branch) != (configured, merge.removeprefix("refs/heads/")):
        return (f"`git pull --ff-only {remote} {branch}` does not name the upstream "
                f"`{configured} {merge.removeprefix('refs/heads/')}`"), None
    dirty = out(root, "status", "--porcelain", "--untracked-files=no")
    if dirty is None or dirty:
        return "the main checkout has uncommitted changes to tracked files", None
    old = out(root, "rev-parse", f"refs/heads/{name}")
    if not old:
        return f"branch `{name}` does not resolve", None
    return None, {"branch": name, "old": old, "upstream_ref": upstream}


def directory(place: dict) -> Path:
    return Path(place["common"]) / "afk-session"


def authorize(place: dict, fields: dict, session: str) -> None:
    folder = directory(place)
    folder.mkdir(exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9._-]", "_", session) or "nosession"
    target = folder / f"sync-{name}.json"
    data = {**fields, "session": session, "expires": time.time() + TTL_SECONDS}
    temp = target.with_suffix(f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(temp, target)


def live_records(place: dict) -> list[tuple[Path, dict]]:
    """Unexpired records; an expired or unreadable one is deleted on sight."""
    found = []
    for path in directory(place).glob("sync-*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            fresh = float(data["expires"]) > time.time()
        except (OSError, ValueError, KeyError, TypeError):
            fresh, data = False, {}
        if fresh:
            found.append((path, data))
        else:
            path.unlink(missing_ok=True)
    return found


def allows(place: dict, branch: str, old: str, new: str) -> bool:
    """True when a live record covers moving `branch` from `old` to `new`: the upstream commit, a descendant."""
    if ZEROS.match(old) or ZEROS.match(new):
        return False
    for _, data in live_records(place):
        if data.get("branch") != branch or data.get("old") != old:
            continue
        upstream = out(place["root"], "rev-parse", "--verify", "-q", f"{data.get('upstream_ref')}^{{commit}}")
        ancestor = guard.git(Path(place["root"]), "merge-base", "--is-ancestor", old, new).returncode == 0
        if upstream == new and ancestor:
            return True
    return False


def finish(place: dict, lines: list[str]) -> None:
    """Delete the records whose branch this transaction named, then any that expired."""
    named = {parts[2] for parts in (line.split() for line in lines) if len(parts) == 3}
    for path, data in live_records(place):
        if f"refs/heads/{data.get('branch')}" in named:
            path.unlink(missing_ok=True)
