#!/usr/bin/env python3
"""Who owns a worktree: the harness process that made it, and whether it still runs.

    python worktree_owner.py state <pid> <ctime>   -> alive | dead | unknown
    python worktree_owner.py runtime-paths    -> the plugin's runtime-state paths, one per line
    python worktree_owner.py ctime <pid>      -> the process creation time, or nothing
    python worktree_owner.py record --dir D --name N --path P --branch B --harness H [--session S]
        writes D/N.json: the owner record `create-worktree --name` leaves behind
    python worktree_owner.py copied --worktree P   < NUL-separated paths relative to P
        writes <P's git dir>/afk-copied.json: the SHA-256 of each file the copy step placed
    python worktree_owner.py placed --worktree P
        adds to that file every ignored file P holds now, outside DISPOSABLE_DIRS folders

The owner is, in order: `AFK_WORKTREE_OWNER` (`<pid>:<ctime>`, resolved by the first
native process of a hook chain, since a walk from inside bash loses the chain), the
first ancestor of this process that is not a shell, an interpreter, git or a console
host, then the pid in the env name the provider file declares (`owner_pid_env`). The creation time pins the pid: a live pid
with another creation time is a recycled one and reads `unknown`. Never
`os.kill(pid, 0)`: on Windows that terminates the process.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time

# Paths gates of plugin versions before the git-dir move left inside a checkout. `create-worktree`
# excludes them and `remove-worktree.py` does not count them as work; this is their one home.
RUNTIME_PATHS = (".claude/hooks/.gate-cache/", ".claude/metrics/")

# Ignored folder names that hold only rebuildable output or caches; `.m2` is the Maven gate's
# per-worktree repository. Removal treats nothing else that git ignores as disposable.
DISPOSABLE_DIRS = frozenset({"node_modules", "target", "build", "dist", "out", ".venv", "venv",
                             "__pycache__", ".pytest_cache", ".gradle", ".mypy_cache", ".ruff_cache",
                             ".m2"})

SKIPPED = {"bash", "sh", "dash", "zsh", "fish", "env", "timeout", "python", "python3", "pythonw",
           "py", "git", "cmd", "pwsh", "powershell", "conhost", "winpty", "mintty"}


def basename(name: str) -> str:
    name = name.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for suffix in (".exe", ".cmd", ".bat"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.rstrip("0123456789.") if name.startswith("python") and name not in SKIPPED else name


if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _k32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    _k32.Process32FirstW.argtypes = _k32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    _k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    _k32.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.c_void_p,) * 4
    _QUERY = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
    _ACCESS_DENIED, _INVALID_PARAMETER = 5, 87

    class _Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

    def snapshot() -> dict[int, tuple[int, str]]:
        """pid -> (parent pid, exe name) for every process, via the Toolhelp API."""
        handle = _k32.CreateToolhelp32Snapshot(0x2, 0)
        table: dict[int, tuple[int, str]] = {}
        entry = _Entry()
        entry.dwSize = ctypes.sizeof(_Entry)
        ok = _k32.Process32FirstW(handle, ctypes.byref(entry))
        while ok:
            table[entry.th32ProcessID] = (entry.th32ParentProcessID, entry.szExeFile)
            ok = _k32.Process32NextW(handle, ctypes.byref(entry))
        _k32.CloseHandle(handle)
        return table

    def creation_time(pid: int) -> str | None:
        """The process creation time, or None when it cannot be read."""
        handle = _k32.OpenProcess(_QUERY, False, pid)
        if not handle:
            return None
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            if not _k32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
                return None
            return str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
        finally:
            _k32.CloseHandle(handle)

    def exists(pid: int) -> bool | None:
        """Running, not merely still referenced by someone's open handle."""
        handle = _k32.OpenProcess(_QUERY, False, pid)
        if handle:
            code = wintypes.DWORD()
            running = _k32.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value == 259
            _k32.CloseHandle(handle)
            return bool(running)
        code = ctypes.get_last_error()
        if code == _INVALID_PARAMETER:
            return False
        return True if code == _ACCESS_DENIED else None
else:
    def snapshot() -> dict[int, tuple[int, str]]:
        out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,comm="], capture_output=True, encoding="utf-8", errors="replace")
        table: dict[int, tuple[int, str]] = {}
        for line in out.stdout.splitlines():
            parts = line.split(None, 2)
            if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
                table[int(parts[0])] = (int(parts[1]), parts[2])
        return table

    def creation_time(pid: int) -> str | None:
        try:
            with open(f"/proc/{pid}/stat", encoding="utf-8") as stat:
                return stat.read().rsplit(")", 1)[1].split()[19]
        except (OSError, IndexError):
            pass
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, encoding="utf-8", errors="replace")
        return out.stdout.strip() or None

    def exists(pid: int) -> bool | None:
        return creation_time(pid) is not None


def find_owner(start: int | None = None) -> dict | None:
    """The nearest ancestor that is not a shell, interpreter, git or console host.

    `AFK_OWNER_PROCESS` (comma-separated process names) names the owner outright:
    the nearest ancestor with one of those names wins over the skip list. The walk stops
    at a parent created after its child: that pid was reused and is no ancestor.
    """
    wanted = {name.strip().lower() for name in os.environ.get("AFK_OWNER_PROCESS", "").split(",") if name.strip()}
    table = snapshot()
    child = start or os.getpid()
    pid = table.get(child, (0, ""))[0]
    born = creation_time(child)
    seen = set()
    while pid and pid not in seen and pid in table:
        seen.add(pid)
        parent, name = table[pid]
        made = creation_time(pid)
        if born and made and born.isdigit() and made.isdigit() and int(made) > int(born):
            return None
        born = made
        if basename(name) in wanted or (not wanted and basename(name) not in SKIPPED):
            return {"pid": pid, "ctime": made, "name": name} if made else None
        pid = parent
    return None


def env_owner() -> dict | None:
    """The owner a native ancestor resolved and passed down as `AFK_WORKTREE_OWNER=<pid>:<ctime>`."""
    pid, _, ctime = os.environ.get("AFK_WORKTREE_OWNER", "").partition(":")
    return {"pid": int(pid), "ctime": ctime} if pid.isdigit() and ctime else None


def provider_owner(harness: str) -> dict | None:
    """The harness's own pid from the env name its provider file declares, pinned by creation time."""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks", "lib", "providers",
                               f"{harness}.json"), encoding="utf-8") as handle:
            name = json.load(handle).get("owner_pid_env") or ""
    except (OSError, ValueError):
        return None
    pid = os.environ.get(name, "") if name else ""
    ctime = creation_time(int(pid)) if pid.isdigit() else None
    return {"pid": int(pid), "ctime": ctime} if ctime else None


def state(pid: int, ctime: str) -> str:
    """alive | dead | unknown. A live pid with another creation time is `unknown`."""
    present = exists(pid)
    if present is False:
        return "dead"
    if present is None:
        return "unknown"
    now = creation_time(pid)
    if now is None:
        return "unknown"
    return "alive" if now == str(ctime) else "unknown"


def owners_of(record: dict) -> list[dict]:
    """Every owner a record names: its `owners` list, else its single `owner` as a one-item list."""
    listed = record.get("owners")
    if isinstance(listed, list):
        return [item for item in listed if isinstance(item, dict)]
    return [record["owner"]] if isinstance(record.get("owner"), dict) else []


def all_dead(record: dict) -> bool:
    """True only when the record names at least one owner and every one is provably `dead`."""
    found = owners_of(record)
    return bool(found) and all(item.get("pid") and item.get("ctime")
                               and state(int(item["pid"]), str(item["ctime"])) == "dead" for item in found)


def record(argv: list[str]) -> int:
    fields = {"dir": "", "name": "", "path": "", "branch": "", "harness": "", "session": ""}
    args = iter(argv)
    for flag in args:
        key = flag.lstrip("-")
        if key not in fields:
            sys.stderr.write(f"unknown argument: {flag}\n")
            return 2
        fields[key] = next(args, "")
    if not fields["dir"] or not fields["name"]:
        sys.stderr.write("record needs --dir and --name\n")
        return 2
    found = env_owner() or find_owner() or provider_owner(fields["harness"]) or {}
    document = {"name": fields["name"], "path": fields["path"], "branch": fields["branch"],
                "harness": fields["harness"], "session": fields["session"],
                "owner": {"pid": found.get("pid"), "ctime": found.get("ctime")},
                "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    os.makedirs(fields["dir"], exist_ok=True)
    target = os.path.join(fields["dir"], f"{fields['name']}.json")
    scratch = f"{target}.{os.getpid()}.tmp"
    with open(scratch, "w", encoding="utf-8") as out:
        json.dump(document, out)
    os.replace(scratch, target)
    return 0


COPIED = "afk-copied.json"


def git_dir_of(worktree: str) -> str:
    """The git dir a linked worktree's `.git` file names, or "" when it names none."""
    try:
        with open(os.path.join(worktree, ".git"), encoding="utf-8") as handle:
            line = handle.readline().strip()
    except OSError:
        return ""
    if not line.startswith("gitdir:"):
        return ""
    found = line[len("gitdir:"):].strip()
    return found if os.path.isabs(found) else os.path.normpath(os.path.join(worktree, found))


def sha256_of(path: str) -> str | None:
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return None


def copied_manifest(worktree: str) -> dict:
    """`{relative path: SHA-256}` of the files the copy step placed in this worktree."""
    try:
        with open(os.path.join(git_dir_of(worktree), COPIED), encoding="utf-8") as handle:
            found = json.load(handle)
        return found if isinstance(found, dict) else {}
    except (OSError, ValueError):
        return {}


def disposable(rel_dir: str) -> bool:
    return rel_dir.rstrip("/").rsplit("/", 1)[-1] in DISPOSABLE_DIRS


def files_under(worktree: str, rel_dir: str, tick=lambda: None):
    """Each file below an ignored folder, relative to the worktree, skipping disposable folders.
    `tick` runs once per folder, so a caller on a budget can stop the walk."""
    for root, dirs, files in os.walk(os.path.join(worktree, rel_dir)):
        tick()
        dirs[:] = [name for name in dirs if name not in DISPOSABLE_DIRS]
        for name in files:
            yield os.path.relpath(os.path.join(root, name), worktree).replace(os.sep, "/")


def ignored_files(worktree: str) -> list[str] | None:
    """Every ignored file in the worktree outside disposable folders; None when git cannot say."""
    done = subprocess.run(["git", "-C", worktree, "status", "--porcelain", "-z", "--untracked-files=all",
                           "--ignored=matching"], capture_output=True, encoding="utf-8", errors="replace")
    if done.returncode != 0:
        return None
    found = []
    for entry in done.stdout.split("\0"):
        rel = entry[3:]
        if entry[:2] != "!!" or not rel:
            continue
        if not rel.endswith("/"):
            found.append(rel)
        elif not disposable(rel):
            found.extend(files_under(worktree, rel))
    return found


def copied(argv: list[str], placed: bool = False) -> int:
    name = "placed" if placed else "copied"
    if len(argv) != 2 or argv[0] != "--worktree":
        sys.stderr.write(f"{name} needs --worktree <path>\n")
        return 2
    worktree = argv[1]
    gitdir = git_dir_of(worktree)
    if not gitdir:
        sys.stderr.write(f"{name}: {worktree} is not a linked worktree\n")
        return 2
    manifest = copied_manifest(worktree)
    rels = ignored_files(worktree) if placed else sys.stdin.read().split("\0")
    if rels is None:
        sys.stderr.write(f"placed: git status failed in {worktree}\n")
        return 1
    for rel in rels:
        rel = rel.strip("\r\n").replace("\\", "/")
        digest = sha256_of(os.path.join(worktree, rel)) if rel else None
        if digest:
            manifest[rel] = digest
    target = os.path.join(gitdir, COPIED)
    scratch = f"{target}.{os.getpid()}.tmp"
    with open(scratch, "w", encoding="utf-8") as out:
        json.dump(manifest, out)
    os.replace(scratch, target)
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["record"]:
        return record(argv[1:])
    if argv[:1] == ["copied"]:
        return copied(argv[1:])
    if argv[:1] == ["placed"]:
        return copied(argv[1:], placed=True)
    if argv[:1] == ["runtime-paths"]:
        print("\n".join(RUNTIME_PATHS))
        return 0
    if len(argv) == 2 and argv[0] == "ctime" and argv[1].isdigit():
        print(creation_time(int(argv[1])) or "")
        return 0
    if len(argv) == 3 and argv[0] == "state" and argv[1].isdigit():
        print(state(int(argv[1]), argv[2]))
        return 0
    sys.stderr.write(__doc__ or "")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
