#!/usr/bin/env python3
"""Remove a worktree the plugin made, or prune the ones whose session is gone.

    remove-worktree.py --path <dir> [--force]   remove one plugin-made worktree
    remove-worktree.py --prune [--repo <dir>]   remove every stale one of a repository

Only a worktree with an owner record (`<common>/afk-worktrees/<name>.json`, written by
`create-worktree --name`) is ever touched. A clean worktree with no unpushed commit is
removed, and its branch with it when the branch has no commit of its own. Anything else
is kept and the resume and remove commands are printed. `--force` removes a kept one:
the human's call. A stale worktree is one whose recorded owner process is dead; an
unknown owner is kept. Exit is 0 unless the call is malformed, so a hook never fails.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV = dict(os.environ, AFK_WORKTREE_OP="1")


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, env=ENV, timeout=120)


def owner_module():
    spec = importlib.util.spec_from_file_location("afk_worktree_owner", HERE / "worktree_owner.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def same(a: str | Path, b: str | Path) -> bool:
    return os.path.normcase(os.path.realpath(str(a))) == os.path.normcase(os.path.realpath(str(b)))


def common_dir(where: Path) -> Path | None:
    while not where.is_dir() and where.parent != where:
        where = where.parent
    done = git(where, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(done.stdout.strip()) if done.returncode == 0 and done.stdout.strip() else None


def records(common: Path) -> list[tuple[Path, dict]]:
    found = []
    for path in sorted((common / "afk-worktrees").glob("*.json")):
        try:
            found.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return found


def count(where: Path, *args: str) -> int:
    done = git(where, "rev-list", "--count", *args)
    return int(done.stdout.strip()) if done.returncode == 0 and done.stdout.strip().isdigit() else 1


def assess(path: Path) -> tuple[str, str | None]:
    """`(reason it must be kept or "", the branch when it has no commit of its own)`."""
    if git(path, "status", "--porcelain").stdout.strip():
        return "it has uncommitted changes", None
    named = git(path, "symbolic-ref", "-q", "--short", "HEAD")
    branch = named.stdout.strip() if named.returncode == 0 else ""
    if branch:
        skip = f"--exclude={branch}"
        unpushed = count(path, branch, "--not", skip, "--branches", "--remotes")
        own = count(path, branch, "--not", skip, "--branches")
    else:
        unpushed = own = count(path, "HEAD", "--not", "--branches", "--remotes")
    if unpushed:
        return "it has commits that exist nowhere else", None
    return "", branch if branch and own == 0 else None


def keep(path: Path, reason: str) -> None:
    script = (HERE / "remove-worktree.py").as_posix()
    sys.stderr.write(f"afk: kept worktree {path.as_posix()}: {reason}.\n"
                     f"afk:   resume: cd {path.as_posix()}\n"
                     f"afk:   remove (discards that work): python {script} --path {path.as_posix()} --force\n")


def remove(path: Path, record_file: Path, common: Path, force: bool) -> bool:
    reason, branch = assess(path)
    if reason and not force:
        keep(path, reason)
        return False
    main = common.parent if common.name == ".git" else common
    done = git(main, "worktree", "remove", *(["--force"] if force else []), str(path))
    if done.returncode != 0:
        sys.stderr.write(f"afk: could not remove {path.as_posix()}: {done.stderr.strip()[:300]}\n")
        return False
    if branch or (force and record_branch(record_file)):
        git(main, "branch", "-D", branch or record_branch(record_file))
    record_file.unlink(missing_ok=True)
    sys.stderr.write(f"afk: removed worktree {path.as_posix()}.\n")
    return True


def record_branch(record_file: Path) -> str:
    try:
        return json.loads(record_file.read_text(encoding="utf-8")).get("branch") or ""
    except (OSError, ValueError):
        return ""


def remove_one(target: Path, force: bool) -> None:
    common = common_dir(target)
    if common is None:
        return
    top = git(target, "rev-parse", "--show-toplevel").stdout.strip() if target.is_dir() else str(target)
    for record_file, record in records(common):
        if same(record.get("path") or "", top):
            remove(Path(top), record_file, common, force)
            return


def prune(repo: Path) -> None:
    common = common_dir(repo)
    if common is None:
        return
    owner = owner_module()
    for record_file, record in records(common):
        path = Path(record.get("path") or "")
        if not path.is_dir():
            record_file.unlink(missing_ok=True)
            git(common.parent if common.name == ".git" else common, "worktree", "prune")
            continue
        who = record.get("owner") or {}
        if not who.get("pid") or not who.get("ctime"):
            continue
        if owner.state(int(who["pid"]), str(who["ctime"])) == "dead":
            remove(path, record_file, common, False)


def main(argv: list[str]) -> int:
    force = "--force" in argv
    args = [a for a in argv if a != "--force"]
    try:
        if args[:1] == ["--path"] and len(args) == 2:
            remove_one(Path(args[1]), force)
        elif args[:1] == ["--prune"] and len(args) in (1, 3):
            prune(Path(args[2]) if len(args) == 3 else Path.cwd())
        else:
            sys.stderr.write(__doc__ or "")
            return 2
    except Exception as problem:  # a cleanup hook must never fail the harness
        sys.stderr.write(f"afk: worktree cleanup skipped ({problem}).\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
