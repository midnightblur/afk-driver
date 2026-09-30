"""The protected-branch guard's verdict for one tool call.

Called by hooks/protected-branch-guard.sh with the tool envelope on stdin and the
harness declarations in the environment (AFK_GUARD_TOOL_CLASS, AFK_GUARD_HARNESS_CLASS,
AFK_GUARD_HINT). Allow: exit 0 (a one-line context note on stdout when the forge
could not answer). Refuse: exit 2, the reason on stderr and as a deny decision on stdout.

Placement (PRD catalog P): the main checkout is refused on any branch; a linked
worktree is refused on a protected branch; a detached or unborn HEAD and any
folder outside git pass. An edit is judged at the session folder and at each target
inside the same repository. A verdict that cannot be computed inside a git work tree
is a refusal that names the fault.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("AFK_PLUGIN_ROOT") or Path(__file__).resolve().parents[2])
PATCH_TARGET = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+?)\s*$", re.M)
TARGET_KEYS = ("file_path", "notebook_path", "path")


class Fault(Exception):
    """The verdict could not be computed."""


def norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def git(directory: Path, *args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", "-C", str(directory), *args], capture_output=True,
                              text=True, timeout=20)
    except FileNotFoundError as problem:
        raise Fault("git is not installed") from problem
    except subprocess.TimeoutExpired as problem:
        raise Fault("git did not answer in time") from problem


def existing_dir(path: Path) -> Path | None:
    path = path if path.is_dir() else path.parent
    while not path.is_dir():
        if path.parent == path:
            return None
        path = path.parent
    return path


def inside_work_tree_by_files(path: Path) -> bool:
    """A `.git` entry above `path`: enough to know a git verdict was owed."""
    directory = existing_dir(path)
    while directory is not None:
        if (directory / ".git").exists():
            return True
        if directory.parent == directory:
            return False
        directory = directory.parent
    return False


def placement(path: Path) -> dict | None:
    """`{"kind": "main"|"linked", "common": ..., "root": ...}`, or None outside git."""
    directory = existing_dir(path)
    if directory is None:
        return None
    done = git(directory, "rev-parse", "--path-format=absolute", "--git-dir",
               "--git-common-dir", "--is-bare-repository", "--show-toplevel",
               "--show-superproject-working-tree")
    if done.returncode != 0:
        if "not a git repository" in done.stderr:
            return None
        # A bare repository has no work tree to protect.
        if "this operation must be run in a work tree" in done.stderr:
            return None
        raise Fault(f"git rev-parse failed: {done.stderr.strip()[:200]}")
    lines = done.stdout.splitlines()
    if len(lines) < 4:
        raise Fault("git rev-parse answered too little")
    git_dir, common, bare, top = lines[:4]
    if bare == "true":
        return None
    if len(lines) > 4 and lines[4].strip():
        return placement(Path(lines[4]))
    kind = "main" if norm(git_dir) == norm(common) else "linked"
    return {"kind": kind, "common": norm(common), "common_raw": common, "root": top}


def branch_of(root: str) -> str | None:
    """The checked-out branch, or None for a detached or unborn HEAD."""
    named = git(Path(root), "symbolic-ref", "-q", "--short", "HEAD")
    if named.returncode != 0:
        return None
    if git(Path(root), "rev-parse", "-q", "--verify", "HEAD").returncode != 0:
        return None
    return named.stdout.strip()


def lookup_module():
    spec = importlib.util.spec_from_file_location(
        "afk_protected_lookup", PLUGIN_ROOT / "scripts" / "protected-lookup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Judge:
    def __init__(self, session: str):
        self.session = session
        self.asked: dict[tuple[str, str], dict] = {}
        self.fallback_reason = ""
        self.common_raw = ""

    def verdict(self, place: dict | None) -> str | None:
        """The refusal cause for a placement, or None to allow."""
        if place is None:
            return None
        self.common_raw = place["common_raw"]
        if place["kind"] == "main":
            return "this is the main checkout"
        branch = branch_of(place["root"])
        if branch is None:
            return None
        key = (place["common"], branch)
        if key not in self.asked:
            try:
                self.asked[key] = lookup_module().lookup(branch, Path(place["root"]))
            except Exception as problem:  # the lookup must never decide by crashing
                raise Fault(f"the protected-branch lookup failed: {problem}") from problem
        answer = self.asked[key]
        if answer.get("source") == "fallback":
            self.fallback_reason = answer.get("reason") or "the forge did not answer"
        return f"branch `{branch}` is protected" if answer["protected"] else None

    def notice_once(self) -> str:
        """The fallback notice, the first time this session needs it."""
        if not self.fallback_reason or not self.common_raw:
            return ""
        marker_dir = Path(self.common_raw) / "afk-session"
        name = re.sub(r"[^A-Za-z0-9._-]", "_", self.session or "nosession")
        try:
            marker_dir.mkdir(exist_ok=True)
            os.close(os.open(marker_dir / f"{name}.fallback", os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except OSError:
            return ""
        return ("protected-branch guard: the forge could not answer "
                f"({self.fallback_reason}); until it can, only the remote's default branch, "
                "`main` and `master` count as protected.")


def targets_of(tool_input: dict, cwd: Path) -> list[Path]:
    found = [str(tool_input[key]) for key in TARGET_KEYS if isinstance(tool_input.get(key), str)]
    for value in tool_input.values():
        if isinstance(value, str) and "*** " in value:
            found.extend(PATCH_TARGET.findall(value))
    return [Path(item) if os.path.isabs(item) else cwd / item for item in found if item]


def deny(reason: str) -> int:
    sys.stderr.write(reason + "\n")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))
    return 2


def refusal(action: str, cause: str, extra: str = "") -> str:
    hint = os.environ.get("AFK_GUARD_HINT", "")
    return (f"protected-branch guard: refused to {action}. Cause: {cause}. "
            f"Move: {hint} A human who needs this session here launches the harness "
            f"with AFK_ALLOW_PROTECTED=1.{(' ' + extra) if extra else ''}")


def decide(envelope: dict) -> int:
    tool_input = envelope.get("tool_input") if isinstance(envelope.get("tool_input"), dict) else {}
    cwd = Path(envelope.get("cwd") or os.getcwd())
    kind = os.environ.get("AFK_GUARD_TOOL_CLASS", "other")
    judge = Judge(str(envelope.get("session_id") or ""))

    here = placement(cwd)
    cause = judge.verdict(here)
    where = "the session folder"
    if cause is None and kind == "edit" and here is not None:
        for target in targets_of(tool_input, cwd):
            place = placement(target)
            if place is not None and place["common"] == here["common"]:
                cause = judge.verdict(place)
                if cause:
                    where = str(target)
                    break
    tool = envelope.get("tool_name") or "a tool"
    if kind == "shell":
        action = f"run `{str(tool_input.get('command') or tool_input.get('cmd') or '').strip()[:80]}`"
    elif kind == "edit":
        action = f"change {where}" if where != "the session folder" else f"edit with {tool}"
    else:
        action = f"use {tool}"
    if cause:
        return deny(refusal(action, cause, judge.notice_once()))
    notice = judge.notice_once()
    if notice:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "additionalContext": notice}}))
    return 0


def main() -> int:
    cwd = Path.cwd()
    try:
        envelope = json.loads(sys.stdin.read() or "{}")
        if not isinstance(envelope, dict):
            raise Fault("the tool envelope is not an object")
        cwd = Path(envelope.get("cwd") or cwd)
        return decide(envelope)
    except Exception as problem:
        # Fail closed inside a git work tree, open outside one.
        try:
            owed = inside_work_tree_by_files(cwd)
        except Exception:
            owed = True
        if not owed:
            return 0
        return deny(refusal("act", f"the guard could not compute a verdict ({problem})"))


if __name__ == "__main__":
    sys.exit(main())
