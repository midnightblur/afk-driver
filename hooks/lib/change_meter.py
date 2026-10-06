"""Change meter and quarantine for a guarded checkout (PRD D4, A5, A6).

PreToolUse snapshots `git status` plus a content hash per listed path of every guarded checkout a shell
call can enter, saving the bytes of each listed file as a blob; PostToolUse compares and, on a difference,
writes `<session>.<root>.quarantine`. While any listed path still differs from its pre-call entry, the guard
refuses everything except inspection, moving, and the named recovery. A call known to only read skips the
snapshot. Gaps: ignored files, the contents of collapsed untracked folders, folders that hold a linked
worktree, and background work (`run_in_background`, `Monitor`), which writes after the compare ran.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import tempfile
import time
from pathlib import Path, PurePosixPath

import protected_branch_guard as guard
import shell_mutations as sm

MAX_HASH = 8 * 1024 * 1024
PRE_STALE = 3600.0
BLOB_STALE = 24 * 3600.0
HOLD_STALE = 24 * 3600.0
READ_GIT = {"status", "diff", "log", "show"}
RESTORE_FLAGS = {"--staged", "--worktree"}
READERS = {"cat", "ls", "dir", "pwd", "head", "tail", "wc", "grep", "egrep", "fgrep", "rg", "find", "stat", "which",
           "type", "echo", "printf", "jq", "sort", "uniq", "diff", "test", "true", "false", "cd", "chdir",
           "set-location", "sl", "pushd", "popd", "date", "whoami", "hostname", "uname", "basename", "dirname",
           "realpath", "readlink", "tr", "cut", "column", "sleep", "herdr", "select-string", "test-path",
           "resolve-path", "write-output", "write-host"}
FIND_WRITES = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"}
GIT_READERS = {"status", "log", "diff", "show", "rev-parse", "ls-files", "fetch", "describe", "blame", "grep",
               "shortlog", "cat-file", "ls-tree", "merge-base", "for-each-ref", "rev-list", "name-rev", "check-ignore"}
FORGE_READ = {"view", "list", "status", "checks", "diff", "show"}
FORGE_API_WRITES = {"-X", "--method", "-f", "-F", "--field", "--raw-field", "--input"}


def session_key(judge) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", judge.session or judge.owner_key())


def folder(place: dict) -> Path:
    return Path(place["common"]) / "afk-session"


def digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()


def hold_path(place: dict, key: str) -> Path:
    return folder(place) / f"{key}.{digest(guard.norm(place['root']))[:10]}.quarantine"


def pre_dir() -> Path:
    return Path(tempfile.gettempdir()) / "afk-guard-pre"


def call_id(envelope: dict, command: str) -> tuple[str, str]:
    """(file-safe call id, sha1 of the command): the harness's tool_use_id when it carries one."""
    sha = digest(command)
    given = envelope.get("tool_use_id")
    return (re.sub(r"[^A-Za-z0-9._-]", "_", str(given)) if given else f"c{sha[:16]}"), sha


def pre_files(key: str, cwd: Path) -> list[Path]:
    return sorted(pre_dir().glob(f"{key}.*.{digest(guard.norm(cwd))[:8]}.pre"))


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


def entry(root: str, path: str, xy: str, blobs: Path | None = None) -> dict:
    """The state of one listed path; with `blobs`, its bytes are kept there under their hash."""
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
            data = full.read_bytes()
            name = hashlib.sha256(data).hexdigest()
            if blobs is not None:
                _keep(blobs / name, data)
            return {"xy": xy, "hash": name}
        return {"xy": xy, "size": size, "mtime_ns": full.stat().st_mtime_ns}
    except OSError:
        return {"xy": xy}


def _keep(path: Path, data: bytes) -> None:
    if path.exists():
        os.utime(path, None)  # seen again: the age sweep counts from the last use
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".{os.getpid()}.tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def _mtime(path: Path) -> int | None:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def snapshot(root: str, common: str | None = None, save: bool = False) -> dict[str, dict]:
    """Path -> entry for every path `git status` lists (untracked folders collapsed)."""
    done = guard.git(Path(root), "status", "--porcelain=v1", "-z", "--untracked-files=normal")
    if done.returncode != 0:
        raise guard.Fault(f"git status failed: {done.stderr.strip()[:200]}")
    tokens = done.stdout.split("\0")
    roots = worktree_roots(common) if common else []
    blobs = Path(common) / "afk-session" / "blobs" if save and common else None
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
        found[path] = entry(root, path, xy, blobs)
    return found


def differs(before: dict, after: dict) -> list[str]:
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(temp, path)


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _sweep(directory: Path, pattern: str, older: float) -> None:
    cutoff = time.time() - older
    for path in directory.glob(pattern):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            continue


def record_pre(places: list[dict], key: str, call: str, sha: str, cwd: Path) -> None:
    """One pre record for this call, with a snapshot per guarded checkout it can enter."""
    saved = [{"root": p["root"], "common": str(p["common"]),
              "entries": snapshot(p["root"], str(p["common"]), save=True)} for p in places]
    where = pre_dir()
    _sweep(where, "*.pre", PRE_STALE)
    for p in places:
        _sweep(folder(p) / "blobs", "*", BLOB_STALE)
        _sweep(folder(p), "*.quarantine", HOLD_STALE)  # a session that ended held leaves its hold
    _write(where / f"{key}.{call}.{digest(guard.norm(cwd))[:8]}.pre", {"sha": sha, "places": saved})


def _take(key: str, call: str, sha: str, cwd: Path) -> dict | None:
    """This call's pre record (consumed): by id, else the oldest of this session's with the same command."""
    tag = digest(guard.norm(cwd))[:8]
    exact = pre_dir() / f"{key}.{call}.{tag}.pre"
    found = exact if exact.exists() else None
    if found is None:
        same = [p for p in pre_files(key, cwd) if (_read(p) or {}).get("sha") == sha]
        found = min(same, key=lambda p: p.stat().st_mtime, default=None)
    if found is None:
        return None
    saved = _read(found)
    found.unlink(missing_ok=True)
    return saved


def after(key: str, call: str, sha: str, cwd: Path) -> str | None:
    """PostToolUse: the context text when this call changed a guarded checkout, else None."""
    saved = _take(key, call, sha, cwd)
    if not saved:
        return None
    texts = []
    for item in saved.get("places", []):
        now = snapshot(item["root"], item["common"])
        changed = differs(item["entries"], now)
        if not changed:
            continue
        place = {"root": item["root"], "common": item["common"]}
        paths = {p: {"f0": item["entries"].get(p), "f1": now.get(p)} for p in changed}
        held = {"root": item["root"], "common": item["common"], "created": time.time(), "paths": paths}
        _write(hold_path(place, key), held)
        texts.append(message(held, detected=True))
    return "\n".join(texts) or None


def active(place: dict, key: str) -> dict | None:
    """The quarantine for this session and checkout while a listed path still differs; else None."""
    path = hold_path(place, key)
    held = _read(path)
    if not held or guard.norm(held.get("root", "")) != guard.norm(place["root"]):
        return None
    now = snapshot(place["root"], str(place["common"]))
    still = {p: v for p, v in held["paths"].items() if now.get(p) != v["f0"]}
    if not still:
        path.unlink(missing_ok=True)
        return None
    return {**held, "paths": still}


def staged_add(spot: dict) -> bool:
    return "A" in (spot.get("f1") or {}).get("xy", "") and (spot.get("f1") or {}).get("xy") != "??"


def classify(held: dict) -> tuple[list[str], list[str], list[str]]:
    """(restorable, removable, human-only) paths: only paths clean or absent before the call are the agent's."""
    restore, remove, human = [], [], []
    for path, spot in sorted(held["paths"].items()):
        if spot["f0"] is not None or path.endswith("/"):
            human.append(path)
        elif (spot.get("f1") or {}).get("xy", "") == "??" or staged_add(spot):
            remove.append(path)
        else:
            restore.append(path)
    return restore, remove, human


def quote(path: str) -> str:
    return shlex.quote(path)


def message(held: dict, detected: bool = False) -> str:
    root = held["root"].replace("\\", "/")
    names = ", ".join(sorted(held["paths"]))
    head = (("This session's last command changed" if detected else "This session changed")
            + f" {root} (a checkout the guard protects) through a form it cannot refuse in advance: {names}. "
            "Until each is back as it was, only inspection (git status/diff/log/show), moving, and the commands below run here.")
    return head + "\n" + recovery(held)


def recovery(held: dict) -> str:
    restore, remove, human = classify(held)
    root = held["root"].replace(chr(92), "/")
    lines = ["Recover in this order: (1) move into a worktree (the native worktree tool, or the plugin's "
             "scripts/create-worktree); (2) copy the changed files from the main checkout into it; (3) restore the "
             "main checkout with these commands, which are allowed from any folder:"]
    if restore:
        lines.append(f"  git -C {quote(root)} restore --staged --worktree -- " + " ".join(quote(p) for p in restore))
    for path in remove:
        lines.append(f"  git -C {quote(root)} rm -f -- {quote(path)}" if staged_add(held["paths"][path])
                     else f"  rm -- {quote(root + chr(47) + path)}")
    if human:
        lines.append("These paths were already changed before the command, so an agent never touches them; a human "
                     "runs these lines in their own terminal; an agent never runs them. They copy the content the paths "
                     "had before the command back (their index state is not restored):")
        base = Path(held.get("common") or "") / "afk-session" / "blobs"
        for path in human:
            name = ((held["paths"][path].get("f0") or {}).get("hash"))
            if name and (base / name).exists():
                lines.append(f"  cp -- {quote((base / name).as_posix())} {quote(root + '/' + path)}")
            else:
                lines.append(f"  {path}: no copy of its earlier content was kept")
    return "\n".join(lines)


def read_only(command: str, cwd: Path) -> bool:
    """True when every segment is a known non-writer with no redirect target (an optimization only)."""
    for segment in sm.segments(command):
        if segment.mark:
            continue
        if any(w.opaque or sm.resolve(w, cwd) is not None for w in segment.redirects):
            return False
        words = sm.strip_prefixes(segment.words)
        if not words:
            if segment.words and segment.words[0].opaque:
                return False
            continue
        if any(w.opaque and ("`" in w.text or "$(" in w.text) for w in words):
            return False
        prog = sm.program_of(words[0])
        args = [w.text for w in words[1:]]
        if prog == "git":
            if not _git_reads(args):
                return False
        elif prog in ("gh", "glab"):
            if not _forge_reads(args):
                return False
        elif prog in READERS or prog.startswith("get-"):
            if (prog == "find" and FIND_WRITES & set(args)) or (prog == "sort" and any(
                    a == "-o" or a.startswith(("--output", "-o")) for a in args)) \
                    or (prog == "uniq" and len([a for a in args if not a.startswith("-")]) > 1) \
                    or (prog == "rg" and any(a.startswith("--pre") for a in args)):
                return False
        else:
            return False
    return True


def _git_reads(args: list[str]) -> bool:
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
    if i >= len(args):
        return False
    verb, rest = args[i].lower(), args[i + 1:]
    plain = [a for a in rest if not a.startswith("-")]
    if any(a == "--output" or a.startswith("--output=") for a in rest):
        return False
    if verb == "branch":
        clusters = [a for a in rest if a.startswith("-") and not a.startswith("--")]
        return not plain and not sm.BRANCH_CONFIG & {a.split("=")[0] for a in rest} and not any(
            set(a[1:]) & sm.GIT_BRANCH_EDIT for a in clusters)
    if verb == "remote":
        return not plain
    if verb == "worktree":
        return plain[:1] == ["list"]
    return verb in GIT_READERS


def _forge_reads(args: list[str]) -> bool:
    plain = [a for a in args if not a.startswith("-")]
    if plain[:1] == ["api"]:
        return not FORGE_API_WRITES & set(args)
    return len(plain) >= 2 and plain[1] in FORGE_READ


def _rel(word: sm.Word, here: Path | None, root: str) -> str | None:
    full = sm.resolve(word, here)
    if full is None:
        return None
    try:
        return PurePosixPath(Path(os.path.relpath(full, root)).as_posix()).as_posix()
    except ValueError:
        return None


def _allowed_segment(words: list, redirects: list, here: Path | None, held: dict, outside) -> bool:
    if any(word.opaque or sm.resolve(word, here) is not None for word in redirects):
        return False
    words = sm.strip_prefixes(words)
    if not words:
        return True
    prog = sm.program_of(words[0])
    if prog in sm.CD:
        return True
    if prog == "git":
        return _allowed_git(words, here, held)
    if prog == "rm":
        restore, remove, _ = classify(held)
        args = [w.text for w in words[1:]]
        if len(args) < 2 or args[0] != "--":
            return False
        return all(_rel(w, here, held["root"]) in remove and not staged_add(held["paths"][_rel(w, here, held["root"])])
                   for w in words[2:])
    if prog in sm.COPY and outside is not None:
        positional, targets, destination = sm.parse(words[1:], sm.VALUE_OPTS["cp"])
        if targets or destination or len(positional) < 2:
            return False
        target = sm.resolve(positional[-1], here)
        return target is not None and outside(target) and all(
            _rel(w, here, held["root"]) in held["paths"] for w in positional[:-1])
    full = sm.resolve(words[0], here) if re.search(r"[\\/]", words[0].text) else None
    script = Path(guard.PLUGIN_ROOT) / "scripts" / "create-worktree"
    return full is not None and guard.norm(full) == guard.norm(script)


def _allowed_git(words: list, here: Path | None, held: dict) -> bool:
    i = 1
    while i < len(words):
        text = words[i].text
        if text == "-C" and i + 1 < len(words):
            here = sm.resolve(words[i + 1], here) if words[i + 1].text else here
            i += 2
        elif text in ("-c", "--git-dir", "--work-tree", "--namespace") and i + 1 < len(words):
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
    if "--" not in args:
        return False
    cut = args.index("--")
    flags, paths = args[:cut], words[i + 1 + cut + 1:]
    if not paths:
        return False
    if verb == "rm":
        if sorted(flags) not in (["-f"], ["--force"]):
            return False
        return all(_staged(held, _rel(w, here, held["root"])) for w in paths)
    if verb != "restore" or sorted(flags) != sorted(RESTORE_FLAGS):
        return False
    restore, _, _ = classify(held)
    return all(_rel(w, here, held["root"]) in restore for w in paths)


def _staged(held: dict, rel: str | None) -> bool:
    return rel in held["paths"] and held["paths"][rel]["f0"] is None and staged_add(held["paths"][rel])


def allows(command: str, cwd: Path, held: dict, outside=None) -> bool:
    """True when every segment of `command` is inspection, moving, or a named recovery command.

    `outside(path)` says a copy destination lies outside every guarded checkout; without it no copy is allowed.
    """
    here: Path | None = cwd
    segments = [s for s in sm.segments(command) if not s.mark]
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
        if not _allowed_segment(segment.words, segment.redirects, here, held, outside):
            return False
    return True
