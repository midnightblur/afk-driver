#!/usr/bin/env python3
"""Who owns a worktree: the harness process that made it, and whether it still runs.

    python worktree_owner.py find             -> {"pid": N, "ctime": "...", "name": "..."}
    python worktree_owner.py state <pid> <ctime>   -> alive | dead | unknown
    python worktree_owner.py record --dir D --name N --path P --branch B --harness H [--session S]
        writes D/N.json: the owner record `create-worktree --name` leaves behind

The owner is the first ancestor of this process that is not a shell, an
interpreter, git or a console host. The creation time pins the pid: a live pid
with another creation time is a recycled one and reads `unknown`. Never
`os.kill(pid, 0)`: on Windows that terminates the process.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

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
        out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,comm="], capture_output=True, text=True)
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
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True)
        return out.stdout.strip() or None

    def exists(pid: int) -> bool | None:
        return creation_time(pid) is not None


def find_owner(start: int | None = None) -> dict | None:
    """The nearest ancestor that is not a shell, interpreter, git or console host."""
    table = snapshot()
    pid = table.get(start or os.getpid(), (0, ""))[0]
    seen = set()
    while pid and pid not in seen and pid in table:
        seen.add(pid)
        parent, name = table[pid]
        if basename(name) not in SKIPPED:
            ctime = creation_time(pid)
            return {"pid": pid, "ctime": ctime, "name": name} if ctime else None
        pid = parent
    return None


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
    found = find_owner() or {}
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


def main(argv: list[str]) -> int:
    if argv[:1] == ["record"]:
        return record(argv[1:])
    if argv[:1] == ["find"]:
        print(json.dumps(find_owner()))
        return 0
    if len(argv) == 3 and argv[0] == "state" and argv[1].isdigit():
        print(state(int(argv[1]), argv[2]))
        return 0
    sys.stderr.write(__doc__ or "")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
