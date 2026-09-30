#!/usr/bin/env python3
"""Remove a worktree the plugin made, or prune the ones whose session is gone.

    remove-worktree.py --path <dir> [--force]   remove one plugin-made worktree
    remove-worktree.py --prune [--repo <dir>]   remove every stale one of a repository
    remove-worktree.py --report-kept            print the kept worktrees not yet shown, as hook context
    remove-worktree.py --after-exit <pid>:<ctime> --path <dir>   detached: wait for that process, then remove

Only a worktree with an owner record (`<common>/afk-worktrees/<name>.json`, written by
`create-worktree --name`) is ever touched. A clean worktree with no unpushed commit is
removed, and its recorded branch with it when that branch has no commit of its own.
Anything else is kept, recorded for the next session start, and the resume and remove
commands are printed. `--force` removes a kept one: the human's call. A stale worktree is
one whose recorded owner process is dead; an unknown owner is kept. The worktree the
calling session stands in, and the target of a move in flight, are never pruned. Exit is
0 unless the call is malformed or a forced removal is asked from inside the worktree (exit 1),
so a hook never fails. A session that ends standing in its own worktree starts the detached
`--after-exit` waiter (same spawn flags as `afk-move.py`, up to 24 h) for the assessment; the
next session start prune stays the backstop.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV = dict(os.environ, AFK_WORKTREE_OP="1")
SESSION_CWD = Path.cwd()
MOVE_GRACE = 600  # seconds a recorded move target counts as in use
WAIT_CAP = 24 * 3600  # seconds a detached waiter outlives the session it follows


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, env=ENV, timeout=120)


def owner_module():
    spec = importlib.util.spec_from_file_location("afk_worktree_owner", HERE / "worktree_owner.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def real(path: str | Path) -> str:
    return os.path.normcase(os.path.realpath(str(path)))


def same(a: str | Path, b: str | Path) -> bool:
    return real(a) == real(b)


def inside(inner: Path, outer: Path) -> bool:
    a, b = real(inner), real(outer)
    return a == b or a.startswith(b.rstrip("\\/") + os.sep)


def common_dir(where: Path) -> Path | None:
    while not where.is_dir() and where.parent != where:
        where = where.parent
    done = git(where, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(done.stdout.strip()) if done.returncode == 0 and done.stdout.strip() else None


def main_of(common: Path) -> Path:
    return common.parent if common.name == ".git" else common


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


def work_in(path: Path) -> bool:
    """Tracked changes, or an untracked file outside the plugin's own runtime paths."""
    runtime = tuple(owner_module().RUNTIME_PATHS)
    for line in git(path, "status", "--porcelain", "--untracked-files=all").stdout.splitlines():
        if line.startswith("?? ") and line[3:].strip('"').replace("\\", "/").startswith(runtime):
            continue
        if line.strip():
            return True
    return False


def assess(path: Path) -> str:
    """The reason this worktree must be kept, or "" when it is clean and nothing is unpushed."""
    top = git(path, "rev-parse", "--show-toplevel").stdout.strip()
    if not top or not same(top, path):
        return "git does not know it as a worktree"
    if work_in(path):
        return "it has uncommitted changes"
    named = git(path, "symbolic-ref", "-q", "--short", "HEAD")
    branch = named.stdout.strip() if named.returncode == 0 else ""
    if branch:
        unpushed = count(path, branch, "--not", f"--exclude={branch}", "--branches", "--remotes")
    else:
        unpushed = count(path, "HEAD", "--not", "--branches", "--remotes")
    return "it has commits that exist nowhere else" if unpushed else ""


def own_commits(main: Path, branch: str) -> int:
    """Commits on `branch` that no other branch holds; 1 (keep it) when unknown."""
    return count(main, branch, "--not", f"--exclude={branch}", "--branches")


def kept_file(common: Path) -> Path:
    return common / "afk-session" / "kept.json"


def read_kept(common: Path) -> dict:
    try:
        found = json.loads(kept_file(common).read_text(encoding="utf-8"))
        return found if isinstance(found, dict) else {}
    except (OSError, ValueError):
        return {}


def write_kept(common: Path, kept: dict) -> None:
    target = kept_file(common)
    if not kept:
        target.unlink(missing_ok=True)
        return
    target.parent.mkdir(exist_ok=True)
    scratch = target.with_name(f"kept.{os.getpid()}.tmp")
    scratch.write_text(json.dumps(kept), encoding="utf-8")
    os.replace(scratch, target)


def keep(path: Path, reason: str, common: Path) -> None:
    kept = read_kept(common)
    key = path.as_posix()
    if key not in kept:  # a worktree already reported stays reported
        kept[key] = {"reason": reason, "shown": False}
        try:
            write_kept(common, kept)
        except OSError:
            pass
    script = (HERE / "remove-worktree.py").as_posix()
    sys.stderr.write(f"afk: kept worktree {path.as_posix()}: {reason}.\n"
                     f"afk:   resume: cd {path.as_posix()}\n"
                     f"afk:   remove (discards that work): python {script} --path {path.as_posix()} --force\n")


def marker_paths(common: Path):
    """`(marker file, the worktree path it names)` for each pane move marker."""
    for marker in (common / "afk-session").glob("*.move"):
        try:
            yield marker, json.loads(marker.read_text(encoding="utf-8")).get("path") or ""
        except (OSError, ValueError):
            continue


def drop_markers(common: Path, path: Path) -> None:
    """Forget the pane's move marker of a worktree that is gone."""
    for marker, target in marker_paths(common):
        if same(target, path):
            marker.unlink(missing_ok=True)


def move_in_flight(common: Path, path: Path) -> bool:
    """Is this worktree the target of a pane's move that is pending or just completed?"""
    for marker, target in marker_paths(common):
        try:
            if same(target, path) and time.time() - marker.stat().st_mtime < MOVE_GRACE:
                return True
        except OSError:
            continue
    return False


def record_branch(record_file: Path) -> str:
    try:
        return json.loads(record_file.read_text(encoding="utf-8")).get("branch") or ""
    except (OSError, ValueError):
        return ""


def drop_branch(main: Path, record_file: Path) -> None:
    """Delete the branch the record names when it holds no commit of its own."""
    branch = record_branch(record_file)
    if branch and git(main, "rev-parse", "-q", "--verify", f"refs/heads/{branch}").returncode == 0 \
            and own_commits(main, branch) == 0:
        git(main, "branch", "-D", branch)


def registered(common: Path, path: Path) -> bool:
    """Does git still list `path` as a worktree of this repository?"""
    listed = git(main_of(common), "worktree", "list", "--porcelain").stdout.splitlines()
    return any(same(line[len("worktree "):], path) for line in listed if line.startswith("worktree "))


def clear_leftover(common: Path, path: Path, record_file: Path) -> None:
    """A folder git no longer lists (a removal that failed on the folder): clear it when empty."""
    try:
        path.rmdir()
    except OSError:
        return  # not empty: someone's files, not a leftover
    drop_branch(main_of(common), record_file)
    record_file.unlink(missing_ok=True)
    drop_markers(common, path)
    sys.stderr.write(f"afk: cleared the leftover folder {path.as_posix()}.\n")


class StandingInside(Exception):
    """A forced removal asked from inside the folder it would delete."""


def remove(path: Path, record_file: Path, common: Path, force: bool) -> bool:
    if inside(SESSION_CWD, path):
        if force:
            raise StandingInside(path)
        # Deleting the folder this process stands in half-removes it on Windows.
        sys.stderr.write(f"afk: worktree {path.as_posix()} is this session's folder; "
                         "it is removed when the session exits, or at a later session start.\n")
        wait_for_exit(path, record_file, common)
        return False
    reason = assess(path)
    if reason and not force:
        keep(path, reason, common)
        return False
    main = main_of(common)
    os.chdir(main)  # a process must not stand in the folder it deletes
    done = git(main, "worktree", "remove", "--force", str(path))  # assess already judged it
    if done.returncode != 0:
        sys.stderr.write(f"afk: could not remove {path.as_posix()}: {done.stderr.strip()[:300]}\n")
        return False
    drop_branch(main, record_file)
    record_file.unlink(missing_ok=True)
    drop_markers(common, path)
    sys.stderr.write(f"afk: removed worktree {path.as_posix()}.\n")
    return True


def wait_for_exit(path: Path, record_file: Path, common: Path) -> None:
    """Start a detached waiter that removes `path` once the harness above this hook has exited."""
    owner = owner_module()
    found = owner.env_owner() or owner.find_owner()
    if not found or not found.get("pid") or not found.get("ctime"):
        who = json.loads(record_file.read_text(encoding="utf-8")).get("owner") or {}
        found = who if who.get("pid") and who.get("ctime") else None
    if not found:
        return
    flag = common / "afk-worktrees" / f"{record_file.stem}.wait"
    try:
        if flag.exists() and time.time() - flag.stat().st_mtime < WAIT_CAP:
            return
        flag.write_text(str(os.getpid()), encoding="utf-8")
        spec = importlib.util.spec_from_file_location("afk_h2_move", HERE.parent / "hooks" / "lib" / "h2_move.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.spawn([sys.executable, str(HERE / "remove-worktree.py"), "--after-exit",
                      f"{found['pid']}:{found['ctime']}", "--path", str(path)], cwd=str(main_of(common)))
    except (OSError, ValueError):
        pass


def after_exit(spec: str, target: Path) -> None:
    """Wait (up to WAIT_CAP) until the process `spec` is gone, then run the normal removal."""
    pid, _, ctime = spec.partition(":")
    owner = owner_module()
    poll = float(os.environ.get("AFK_WAIT_POLL") or 2.0)
    deadline = time.monotonic() + WAIT_CAP
    while pid.isdigit() and owner.state(int(pid), ctime) == "alive" and time.monotonic() < deadline:
        time.sleep(poll)
    common = common_dir(target)
    try:
        remove_one(target, False)
    finally:
        if common is not None:
            (common / "afk-worktrees" / f"{target.name}.wait").unlink(missing_ok=True)


def remove_one(target: Path, force: bool) -> None:
    common = common_dir(target)
    if common is None:
        return
    top = git(target, "rev-parse", "--show-toplevel").stdout.strip() if target.is_dir() else str(target)
    for record_file, record in records(common):
        named = record.get("path") or ""
        if same(named, target) or same(named, top):
            if not force and move_in_flight(common, Path(named)):
                return
            remove(Path(named), record_file, common, force)
            return


def adopt(owner, record_file: Path, record: dict) -> None:
    """Re-record the current session as the owner of a worktree it starts in."""
    found = owner.env_owner() or owner.find_owner()
    if not found or not found.get("pid"):
        return
    record["owner"] = {"pid": found["pid"], "ctime": found.get("ctime")}
    try:
        record_file.write_text(json.dumps(record), encoding="utf-8")
    except OSError:
        pass


def prune(repo: Path) -> None:
    common = common_dir(repo)
    if common is None:
        return
    owner = owner_module()
    for record_file, record in records(common):
        path = Path(record.get("path") or "")
        if not path.is_dir():
            record_file.unlink(missing_ok=True)
            git(main_of(common), "worktree", "prune")
            continue
        if inside(SESSION_CWD, path):  # a resumed session stands here: it owns the worktree now
            adopt(owner, record_file, record)
            continue
        who = record.get("owner") or {}
        if not who.get("pid") or not who.get("ctime"):
            continue
        if owner.state(int(who["pid"]), str(who["ctime"])) != "dead" or move_in_flight(common, path):
            continue
        if registered(common, path):
            remove(path, record_file, common, False)
        else:
            clear_leftover(common, path, record_file)


def report_kept(repo: Path) -> None:
    """Print the kept worktrees not yet shown as SessionStart context, once."""
    common = common_dir(repo)
    if common is None:
        return
    kept = {path: item for path, item in read_kept(common).items() if Path(path).is_dir()}
    fresh = [(path, item) for path, item in kept.items() if not item.get("shown")]
    if fresh:
        script = (HERE / "remove-worktree.py").as_posix()
        lines = ["afk kept these worktrees because they hold work:"]
        for path, item in fresh:
            lines.append(f"- {path}: {item.get('reason')}. Resume: cd {path}. "
                         f"Remove and discard its work: python {script} --path {path} --force")
            item["shown"] = True
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                 "additionalContext": "\n".join(lines)}}))
    try:
        write_kept(common, kept)
    except OSError:
        pass


def main(argv: list[str]) -> int:
    force = "--force" in argv
    args = [a for a in argv if a != "--force"]
    try:
        if args[:1] == ["--path"] and len(args) == 2:
            remove_one(Path(args[1]), force)
        elif args[:1] == ["--prune"] and len(args) in (1, 3):
            prune(Path(args[2]) if len(args) == 3 else Path.cwd())
        elif args[:1] == ["--after-exit"] and len(args) == 4 and args[2] == "--path":
            after_exit(args[1], Path(args[3]))
        elif args == ["--report-kept"]:
            report_kept(Path.cwd())
        else:
            sys.stderr.write(__doc__ or "")
            return 2
    except StandingInside as inner:
        sys.stderr.write(f"afk: not removed: this shell is inside {Path(inner.args[0]).as_posix()}. "
                         "Run this from outside the worktree:\n"
                         f"afk:   python {(HERE / 'remove-worktree.py').as_posix()} --path "
                         f"{Path(inner.args[0]).as_posix()} --force\n")
        return 1
    except Exception as problem:  # a cleanup hook must never fail the harness
        sys.stderr.write(f"afk: worktree cleanup skipped ({problem}).\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
