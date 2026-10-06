"""Change meter and quarantine for a guarded checkout (PRD D4, A5, A6).

PreToolUse snapshots `git status` plus a content hash per listed path (`<session>.pre`); PostToolUse
compares and, on a difference, writes `<session>.quarantine`. While any listed path still differs from
its pre-call entry, the guard refuses everything except inspection, moving, and the named recovery.
Gaps: ignored files, the contents of collapsed untracked folders, and folders that hold a linked worktree are not seen.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path, PurePosixPath

import protected_branch_guard as guard
import shell_mutations as sm

MAX_HASH = 8 * 1024 * 1024
READ_GIT = {"status", "diff", "log", "show"}
RESTORE_FLAGS = {"--staged", "--worktree"}


def session_key(judge) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", judge.session or judge.owner_key())


def folder(place: dict) -> Path:
    return Path(place["common"]) / "afk-session"


def worktree_roots(common: str) -> list[str]:
    """Roots of the linked worktrees, read from their gitdir files (no git process)."""
    roots = []
    for pointer in Path(common).glob("worktrees/*/gitdir"):
        try:
            roots.append(guard.norm(Path(pointer.read_text(encoding="utf-8").strip()).parent))
        except OSError:
            continue
    return roots


def holds_worktree(root: str, path: str, roots: list[str]) -> bool:
    here = guard.norm(Path(root) / path)
    return any(r == here or r.startswith(here + os.sep) for r in roots)


def entry(root: str, path: str, xy: str) -> dict:
    full = Path(root) / path
    if path.endswith("/"):
        return {"xy": xy, "mtime_ns": _mtime(full)}
    if os.path.islink(full):
        return {"xy": xy, "link": os.readlink(full)}
    try:
        size = full.stat().st_size
        if not full.is_file():
            return {"xy": xy}
        if size <= MAX_HASH:
            return {"xy": xy, "hash": hashlib.sha256(full.read_bytes()).hexdigest()}
        return {"xy": xy, "size": size, "mtime_ns": full.stat().st_mtime_ns}
    except OSError:
        return {"xy": xy}


def _mtime(path: Path) -> int | None:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def snapshot(root: str, common: str | None = None) -> dict[str, dict]:
    """Path -> entry for every path `git status` lists (untracked folders collapsed)."""
    done = guard.git(Path(root), "status", "--porcelain=v1", "-z", "--untracked-files=normal")
    if done.returncode != 0:
        raise guard.Fault(f"git status failed: {done.stderr.strip()[:200]}")
    tokens = done.stdout.split("\0")
    roots = worktree_roots(common) if common else []
    found: dict[str, dict] = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        i += 1
        if len(token) < 4:
            continue
        xy, path = token[:2], token[3:]
        if "R" in xy or "C" in xy:
            i += 1
        if path.endswith("/") and holds_worktree(root, path, roots):
            continue  # cutting a worktree inside the checkout changes this folder; not watched
        found[path] = entry(root, path, xy)
    return found


def differs(before: dict, after: dict) -> list[str]:
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    temp = path.with_suffix(f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(temp, path)


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def record_pre(place: dict, key: str) -> None:
    _write(folder(place) / f"{key}.pre", {"root": place["root"], "entries": snapshot(place["root"], str(place["common"]))})


def after(place: dict, key: str) -> str | None:
    """PostToolUse: the context text when this call changed the checkout, else None."""
    pre = folder(place) / f"{key}.pre"
    saved = _read(pre)
    pre.unlink(missing_ok=True)
    if not saved or guard.norm(saved.get("root", "")) != guard.norm(place["root"]):
        return None
    now = snapshot(place["root"], str(place["common"]))
    changed = differs(saved["entries"], now)
    if not changed:
        return None
    paths = {p: {"f0": saved["entries"].get(p), "f1": now.get(p)} for p in changed}
    held = {"root": place["root"], "created": time.time(), "paths": paths}
    _write(folder(place) / f"{key}.quarantine", held)
    return message(held, detected=True)


def active(place: dict, key: str) -> dict | None:
    """The quarantine for this session and checkout while a listed path still differs; else None."""
    path = folder(place) / f"{key}.quarantine"
    held = _read(path)
    if not held or guard.norm(held.get("root", "")) != guard.norm(place["root"]):
        return None
    now = snapshot(place["root"], str(place["common"]))
    still = {p: v for p, v in held["paths"].items() if now.get(p) != v["f0"]}
    if not still:
        path.unlink(missing_ok=True)
        return None
    return {**held, "paths": still}


def new_like(spot: dict) -> bool:
    xy = (spot.get("f1") or {}).get("xy", "")
    return xy == "??" or "A" in xy


def classify(held: dict) -> tuple[list[str], list[str], list[str]]:
    """(restorable, removable, human-only) paths: only paths clean or absent before the call are the agent's."""
    restore, remove, human = [], [], []
    for path, spot in sorted(held["paths"].items()):
        if spot["f0"] is not None or path.endswith("/"):
            human.append(path)
        elif new_like(spot):
            remove.append(path)
        else:
            restore.append(path)
    return restore, remove, human


def quote(path: str) -> str:
    return f'"{path}"' if re.search(r"[\s\"']", path) else path


def message(held: dict, detected: bool = False) -> str:
    root = held["root"].replace("\\", "/")
    names = ", ".join(sorted(held["paths"]))
    head = (("This session's last command changed" if detected else "This session changed")
            + f" {root} (a checkout the guard protects) through a form it cannot refuse in advance: {names}. "
            "Until each is back as it was, only inspection (git status/diff/log/show), moving, and the commands below run here.")
    return head + "\n" + recovery(held)


def recovery(held: dict) -> str:
    restore, remove, human = classify(held)
    root = held["root"].replace("\\", "/")
    lines = []
    lines.append("Recover in this order: (1) move into a worktree (the native worktree tool, or the plugin's "
                 "scripts/create-worktree); (2) copy the changed files from the main checkout into it; (3) restore the "
                 "main checkout with these commands, which are allowed here:")
    if restore:
        lines.append("  git restore --staged --worktree -- " + " ".join(quote(p) for p in restore))
    for path in remove:
        lines.append(f"  rm -- {quote(path)}")
    if human:
        lines.append("These paths were already changed before the command, so an agent never touches them; a human "
                     "restores them if they should go back: "
                     + "; ".join(f'git -C "{root}" restore --staged --worktree -- {quote(p)}' for p in human))
    return "\n".join(lines)


def _rel(word: sm.Word, here: Path | None, root: str) -> str | None:
    full = sm.resolve(word, here)
    if full is None:
        return None
    try:
        return PurePosixPath(Path(os.path.relpath(full, root)).as_posix()).as_posix()
    except ValueError:
        return None


def _allowed_segment(words: list, redirects: list, here: Path | None, held: dict, opts: dict) -> bool:
    if any(word.opaque or sm.resolve(word, here) is not None for word in redirects):
        return False
    words = sm.strip_prefixes(words)
    if not words:
        return True
    prog = sm.program_of(words[0])
    if prog in sm.CD:
        return True
    if prog == "git":
        return _allowed_git(words, here, held, opts)
    if prog == "rm":
        restore, remove, _ = classify(held)
        args = [w.text for w in words[1:]]
        if len(args) < 2 or args[0] != "--":
            return False
        return all(_rel(w, here, held["root"]) in remove for w in words[2:])
    full = sm.resolve(words[0], here) if re.search(r"[\\/]", words[0].text) else None
    script = Path(guard.PLUGIN_ROOT) / "scripts" / "create-worktree"
    return full is not None and guard.norm(full) == guard.norm(script)


def _allowed_git(words: list, here: Path | None, held: dict, opts: dict) -> bool:
    i = 1
    while i < len(words):
        text = words[i].text
        if text in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") and i + 1 < len(words):
            i += 2
        elif text.startswith("-"):
            i += 1
        else:
            break
    if i >= len(words):
        return False
    verb = words[i].text.lower()
    args = [w.text for w in words[i + 1:]]
    if verb in READ_GIT:
        return not any(a == "--output" or a.startswith("--output=") for a in args)
    if verb != "restore" or "--" not in args:
        return False
    cut = args.index("--")
    flags, paths = args[:cut], words[i + 1 + cut + 1:]
    if sorted(flags) != sorted(RESTORE_FLAGS) or not paths:
        return False
    restore, _, _ = classify(held)
    return all(_rel(w, here, held["root"]) in restore for w in paths)


def allows(command: str, cwd: Path, held: dict) -> bool:
    """True when every segment of `command` is inspection, moving, or a named recovery command."""
    here: Path | None = cwd
    segments = sm.segments(command)
    if not segments:
        return False
    for segment in segments:
        words = sm.strip_prefixes(segment.words)
        if words and sm.program_of(words[0]) in sm.CD:
            _, targets, _ = sm.parse(words[1:])
            positional = sm.parse(words[1:])[0]
            chosen = targets or positional[:1]
            here = sm.resolve(chosen[0], here) if chosen and chosen[0].text != "-" else None
            continue
        if not _allowed_segment(segment.words, segment.redirects, here, held, {}):
            return False
    return True
