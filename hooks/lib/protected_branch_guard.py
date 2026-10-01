"""The protected-branch guard's verdict for one tool call.

Called by hooks/protected-branch-guard.py with the tool envelope on stdin. Allow:
exit 0 (a one-line context note on stdout when the forge could not answer). Refuse:
exit 0, the reason on stderr and a deny decision on stdout (`providers/CONFORMANCE.md` row P-2: exit 2 fails open).

Placement (PRD catalog P): the main checkout is refused on any branch; a linked
worktree is refused on a protected branch; a detached or unborn HEAD and any
folder outside git pass. An edit is judged at the session folder and at every
target it names, in whatever repository the target lies. A verdict that cannot
be computed inside a git work tree is a refusal that names the fault.

Placement is read from the file layout (`.git` directory or `gitdir:` file, then
HEAD); one `git rev-parse` answers the unusual layouts (submodule, `core.worktree`,
reftable, GIT_DIR in the environment).
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import time
import sys
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("AFK_PLUGIN_ROOT") or Path(__file__).resolve().parents[2])
PROVIDERS = Path(__file__).resolve().parent / "providers"
PATCH_TARGET = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+?)\s*$", re.M)
TARGET_KEYS = ("file_path", "notebook_path", "path")
MUTATING = {"write", "edit", "create", "update", "delete", "remove", "replace", "rename", "move",
            "exec", "execute", "run", "terminal", "apply", "patch", "commit", "push", "insert", "set",
            "save", "add", "append", "upload", "format", "reformat", "drop", "put", "post", "send"}
HEX_HEAD = re.compile(r"^[0-9a-f]{40,64}$")
MAX_DEPTH = 3
OUTSIDE_HINT = ("this session is not inside a repository, so no worktree can be cut for it: start the "
                "session inside the repository, or switch into an existing worktree with the harness's "
                "worktree tool (its path form).")


DEADLINE_SECONDS = 20  # below the manifest's 30 s hook timeout: a killed hook would fail open
deadline = [0.0]


class Fault(Exception):
    """The verdict could not be computed."""


def remaining() -> float:
    """Seconds left of this run's deadline; the run's Fault when none is."""
    left = deadline[0] - time.monotonic() if deadline[0] else float(DEADLINE_SECONDS)
    if left <= 0:
        raise Fault("the guard ran out of time")
    return left


def norm(path: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def provider_facts() -> dict:
    """The current harness's declarations from providers/<name>.json, or {}."""
    found, chosen = {}, None
    forced = os.environ.get("AFK_PROVIDER")
    for path in sorted(PROVIDERS.glob("*.json")):
        try:
            facts = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        facts.setdefault("name", path.stem)
        if forced:
            hit = path.stem == forced
        else:
            hit = any(os.environ.get(name) for name in facts.get("detect", {}).get("any_env", []))
        if hit and (chosen is None or facts.get("priority", 100) < chosen):
            found, chosen = facts, facts.get("priority", 100)
    return found


def mcp_class(tool: str) -> str:
    """`other` (judged as a change) when a whole word of the tool part is a mutating verb."""
    part = tool.rsplit("__", 1)[-1]
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", part)
    return "other" if MUTATING & set(re.split(r"[^A-Za-z0-9]+", words.lower())) else "allow"


def known_tools() -> dict:
    """Every provider file's tool names by class, for a run no provider file claims."""
    merged: dict = {}
    for path in sorted(PROVIDERS.glob("*.json")):
        try:
            classes = json.loads(path.read_text(encoding="utf-8")).get("tool_class") or {}
        except (OSError, ValueError):
            continue
        for kind, names in classes.items():
            merged.setdefault(kind, []).extend(names)
    return merged


def tool_class(tool: str, facts: dict) -> str:
    if tool.startswith("mcp__"):
        return mcp_class(tool)
    for kind, names in (facts.get("tool_class") or known_tools()).items():
        if tool in names:
            return kind
    return "other"


def git(directory: Path, *args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", "-C", str(directory), *args], capture_output=True,
                              encoding="utf-8", errors="replace", timeout=min(20, remaining()))
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


def _text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def by_layout(directory: Path) -> dict | None:
    """Placement from the files, or None when the layout is unusual (ask git)."""
    if os.environ.get("GIT_DIR") or os.environ.get("GIT_WORK_TREE"):
        return None
    entry = directory / ".git"
    if entry.is_dir():
        config = _text(entry / "config") or ""
        if (entry / "reftable").is_dir() or re.search(r"^\s*(worktree\s*=|bare\s*=\s*true)", config, re.M | re.I):
            return None
        return {"kind": "main", "gitdir": entry, "common": entry, "root": str(directory)}
    pointer = _text(entry)
    match = re.match(r"gitdir:\s*(.+?)\s*$", pointer or "")
    if not match:
        return None
    gitdir = Path(match.group(1))
    gitdir = gitdir if gitdir.is_absolute() else directory / gitdir
    if gitdir.parent.name != "worktrees":
        return None
    link = _text(gitdir / "commondir")
    if link is None or (gitdir / "reftable").is_dir():
        return None
    common = Path(link.strip())
    common = common if common.is_absolute() else gitdir / common
    return {"kind": "linked", "gitdir": gitdir, "common": Path(os.path.normpath(common)),
            "root": str(directory)}


def by_git(directory: Path, depth: int) -> dict | None:
    done = git(directory, "rev-parse", "--path-format=absolute", "--git-dir",
               "--git-common-dir", "--is-bare-repository", "--show-toplevel",
               "--show-superproject-working-tree")
    if done.returncode != 0:
        if "must be run in a work tree" in done.stderr:
            return None
        raise Fault(f"git rev-parse failed: {done.stderr.strip()[:200]}")
    lines = done.stdout.splitlines()
    if len(lines) < 4:
        raise Fault("git rev-parse answered too little")
    git_dir, common, bare, top = lines[:4]
    if not (os.path.isabs(git_dir) and os.path.isabs(common)):
        raise Fault("git is older than 2.31 (rev-parse has no --path-format)")
    if bare == "true":
        return None
    if len(lines) > 4 and lines[4].strip():
        if depth >= MAX_DEPTH:
            raise Fault("the superproject chain is too deep")
        return placement(Path(lines[4]), depth + 1)
    return {"kind": "main" if norm(git_dir) == norm(common) else "linked", "gitdir": Path(git_dir),
            "common": Path(common), "root": top}


def placement(path: Path, depth: int = 0) -> dict | None:
    """`{"kind": "main"|"linked", "common", "gitdir", "root"}`, or None outside git."""
    directory = existing_dir(path)
    if directory is None:
        return None
    walk = directory
    while True:
        if (walk / ".git").exists():
            place = by_layout(walk)
            break
        if walk.parent == walk:
            return None
        walk = walk.parent
    if place is None:
        place = by_git(walk, depth)
        if place is None:
            return None
    place["key"] = norm(place["common"])
    return place


def _git_branch(root: str) -> str | None:
    named = git(Path(root), "symbolic-ref", "-q", "HEAD")
    if named.returncode == 1:
        return None
    if named.returncode != 0:
        raise Fault(f"git symbolic-ref failed: {named.stderr.strip()[:200]}")
    ref = named.stdout.strip()
    if not ref.startswith("refs/heads/"):
        return None
    born = git(Path(root), "rev-parse", "-q", "--verify", "HEAD")
    if born.returncode == 1:
        return None
    if born.returncode != 0:
        raise Fault(f"git rev-parse failed: {born.stderr.strip()[:200]}")
    return ref[len("refs/heads/"):]


def branch_of(place: dict) -> str | None:
    """The checked-out branch, or None for a detached or unborn HEAD."""
    head = _text(place["gitdir"] / "HEAD")
    common = place["common"]
    if head is None or (common / "reftable").is_dir():
        return _git_branch(place["root"])
    head = head.strip()
    if HEX_HEAD.match(head):
        return None
    match = re.match(r"ref:\s*refs/heads/(.+)$", head)
    if not match:
        return _git_branch(place["root"])
    name = match.group(1)
    if (common / "refs" / "heads" / name).is_file():
        return name
    packed = _text(common / "packed-refs")
    if packed is not None and re.search(rf" refs/heads/{re.escape(name)}$", packed, re.M):
        return name
    return None


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
        self.common = ""

    def verdict(self, place: dict | None, branch: str | None = None) -> str | None:
        """The refusal cause for a placement, or None to allow. `branch` names one the HEAD does not."""
        if place is None:
            return None
        self.common = str(place["common"])
        if place["kind"] == "main":
            return "this is the main checkout"
        branch = branch or branch_of(place)
        if branch is None:
            return None
        key = (place["key"], branch)
        if key not in self.asked:
            try:
                os.environ["AFK_PROTECTED_TIMEOUT"] = str(min(remaining(), float(
                    os.environ.get("AFK_PROTECTED_TIMEOUT") or 5)))
                self.asked[key] = lookup_module().lookup(branch, Path(place["root"]), place["common"])
            except Exception as problem:  # the lookup must never decide by crashing
                raise Fault(f"the protected-branch lookup failed: {problem}") from problem
        answer = self.asked[key]
        if answer.get("source") == "fallback":
            self.fallback_reason = answer.get("reason") or "the forge did not answer"
        return f"branch `{branch}` is protected" if answer["protected"] else None

    def owner_key(self) -> str:
        """A session without an id is told apart by the harness process above this hook."""
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import h2_move
            found = h2_move.owner_env().get("AFK_WORKTREE_OWNER", "")
        except Exception:
            found = ""
        return f"owner-{found}" if found else "nosession"

    def notice_once(self) -> str:
        """The fallback notice, the first time this session needs it."""
        if not self.fallback_reason or not self.common:
            return ""
        marker_dir = Path(self.common) / "afk-session"
        name = re.sub(r"[^A-Za-z0-9._-]", "_", self.session or self.owner_key())
        try:
            marker_dir.mkdir(exist_ok=True)
            os.close(os.open(marker_dir / f"{name}.fallback", os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except OSError:
            return ""
        return ("protected-branch guard: the forge could not answer "
                f"({self.fallback_reason}); using the fallback rule: only the remote's default branch, "
                "`main` and `master` count as protected.")


def targets_of(tool_input: dict, cwd: Path) -> list[Path]:
    found = [str(tool_input[key]) for key in TARGET_KEYS if isinstance(tool_input.get(key), str)]
    for value in tool_input.values():
        if isinstance(value, str) and "*** " in value:
            found.extend(PATCH_TARGET.findall(value))
    return [Path(item) if os.path.isabs(item) else cwd / item for item in found if item]


def deny(reason: str) -> int:
    """The JSON deny at exit 0 blocks under both harnesses; exit 2 is a failed hook to the H-2 one."""
    sys.stderr.write(reason + "\n")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))
    return 0


def refusal(action: str, cause: str, hint: str, extra: str = "") -> str:
    return (f"protected-branch guard: refused to {action}. Cause: {cause}. "
            f"Move: {hint} A human who needs this session here launches the harness "
            f"with AFK_ALLOW_PROTECTED=1.{(' ' + extra) if extra else ''}")


def hint_of(facts: dict) -> str:
    text = facts.get("move_hint") or "create a linked worktree with `{plugin_root}/scripts/create-worktree --name <name>` and continue there."
    return text.replace("{plugin_root}", str(PLUGIN_ROOT).replace("\\", "/"))


def h2_hint(place: dict, envelope: dict, facts: dict, fallback: str) -> str:
    """The pending worktree's path and the exact line to type; creation runs detached."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import h2_move
        chosen = h2_move.plan(place, envelope, facts)
    except Exception as problem:
        return f"{fallback} (the worktree could not be started: {problem})"
    if chosen.get("error"):
        root = str(PLUGIN_ROOT).replace("\\", "/")
        return (f"the session worktree could not be created: {chosen['error']}. Fix that, or run "
                f"`{root}/scripts/create-worktree --name <name>` and continue there.")
    command = (facts.get("move_ui") or {}).get("command")
    if not command:
        return fallback
    typed = ("It is typed into this pane for you once it exists; if it is not, type" if chosen["pane"]
             else "Once it exists, type")
    return (f"a linked worktree is being created for this session at {chosen['path']}. {typed} this line:\n"
            f"{command.format(path=chosen['path'])}\n")


def decide(envelope: dict, facts: dict) -> int:
    tool_input = envelope.get("tool_input") if isinstance(envelope.get("tool_input"), dict) else {}
    cwd = Path(envelope.get("cwd") or os.getcwd())
    tool = str(envelope.get("tool_name") or "")
    kind = tool_class(tool, facts)
    if kind == "allow":
        return 0
    judge = Judge(str(envelope.get("session_id") or ""))

    here = placement(cwd)
    cause = judge.verdict(here)
    session_refused = cause is not None
    where = "the session folder"
    refused = here
    if cause is None and kind == "edit":
        for target in targets_of(tool_input, cwd):
            refused = placement(target)
            cause = judge.verdict(refused)
            if cause:
                where = str(target)
                break
    if kind == "shell":
        action = f"run `{str(tool_input.get('command') or tool_input.get('cmd') or '').strip()[:80]}`"
    elif kind == "edit":
        action = f"change {where}" if where != "the session folder" else f"edit with {tool or 'a tool'}"
    else:
        action = f"use {tool or 'a tool'}"
    if cause:
        hint = hint_of(facts) if here is not None else OUTSIDE_HINT
        if facts.get("harness_class") == "H-2":
            if session_refused and here is not None:
                hint = h2_hint(here, envelope, facts, hint)  # only a refused session folder moves the session
            elif here is not None:
                hint = f"write inside this session's worktree {here['root']}, not outside it."
        return deny(refusal(action, cause, hint, judge.notice_once()))
    notice = judge.notice_once()
    if notice:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "additionalContext": notice}}))
    return 0


def main() -> int:
    if os.environ.get("AFK_ALLOW_PROTECTED") == "1":
        return 0
    cwd = Path.cwd()
    facts: dict = {}
    deadline[0] = time.monotonic() + DEADLINE_SECONDS
    try:
        envelope = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
        if not isinstance(envelope, dict):
            raise Fault("the tool envelope is not an object")
        cwd = Path(envelope.get("cwd") or cwd)
        facts = provider_facts()
        return decide(envelope, facts)
    except Exception as problem:
        # Fail closed inside a git work tree, open outside one.
        try:
            owed = inside_work_tree_by_files(cwd)
        except Exception:
            owed = True
        if not owed:
            return 0
        return deny(refusal("act", f"the guard could not compute a verdict ({problem})", hint_of(facts)))


if __name__ == "__main__":
    sys.exit(main())
