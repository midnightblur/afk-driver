"""Operating-system process facts for the transport kinds: creation time, liveness, and a whole-tree kill.

`kill_tree` lists the whole tree first, then kills every member by its own id, so a child whose parent
dies first is still reached; it never relies on a signal a shell trap catches. It answers the members it
could not stop, by id, which a caller reports as survivors.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
WINDOWS = sys.platform == "win32"


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(int(epoch), timezone.utc).strftime(TIME_FORMAT)


if WINDOWS:
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _QUERY = 0x1000                     # PROCESS_QUERY_LIMITED_INFORMATION
    _STILL_ACTIVE = 259
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _k32.GetProcessTimes.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                     ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
                                     ctypes.POINTER(wintypes.FILETIME))
    _k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))

    class _Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_void_p),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

    _k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _k32.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(_Entry))
    _k32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(_Entry))

    def _open(pid: int):
        handle = _k32.OpenProcess(_QUERY, False, pid)
        return handle or None

    def creation_time(pid: int) -> str | None:
        handle = _open(pid)
        if not handle:
            return None
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            if not _k32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                return None
            ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            return _iso(ticks / 10_000_000 - 11_644_473_600)
        finally:
            _k32.CloseHandle(handle)

    def alive(pid: int) -> bool:
        handle = _open(pid)
        if not handle:
            return ctypes.get_last_error() == 5     # access denied: it exists, owned by another user
        try:
            code = wintypes.DWORD()
            return bool(_k32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == _STILL_ACTIVE
        finally:
            _k32.CloseHandle(handle)

    def _parents() -> dict[int, int]:
        snap = _k32.CreateToolhelp32Snapshot(0x2, 0)
        out: dict[int, int] = {}
        if not snap or snap == wintypes.HANDLE(-1).value:
            return out
        try:
            entry = _Entry()
            entry.dwSize = ctypes.sizeof(_Entry)
            ok = _k32.Process32FirstW(snap, ctypes.byref(entry))
            while ok:
                out[entry.th32ProcessID] = entry.th32ParentProcessID
                ok = _k32.Process32NextW(snap, ctypes.byref(entry))
        finally:
            _k32.CloseHandle(snap)
        return out

    def _kill_one(pid: int, force: bool) -> None:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=15, check=False)

else:
    def creation_time(pid: int) -> str | None:
        stat = f"/proc/{pid}/stat"
        if os.path.exists(stat):
            try:
                fields = open(stat, encoding="utf-8").read().rsplit(")", 1)[1].split()
                ticks = int(fields[19])
                boot = next(int(line.split()[1]) for line in open("/proc/stat", encoding="utf-8")
                            if line.startswith("btime"))
                return _iso(boot + ticks / os.sysconf("SC_CLK_TCK"))
            except (OSError, ValueError, IndexError, StopIteration):
                return None
        done = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True,
                              timeout=10, check=False)
        text = done.stdout.strip()
        if done.returncode != 0 or not text:
            return None
        try:
            return _iso(time.mktime(time.strptime(text, "%a %b %d %H:%M:%S %Y")))
        except ValueError:
            return None

    def alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        try:
            done = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True,
                                  timeout=10, check=False)
            return not done.stdout.strip().startswith("Z")
        except (OSError, subprocess.SubprocessError):
            return True

    def _parents() -> dict[int, int]:
        done = subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True,
                              timeout=10, check=False)
        out: dict[int, int] = {}
        for line in done.stdout.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                out[int(parts[0])] = int(parts[1])
        return out

    def _kill_one(pid: int, force: bool) -> None:
        try:
            os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass


def tree(pid: int) -> list[int]:
    """The process and every live descendant, root first."""
    parents = _parents()
    children: dict[int, list[int]] = {}
    for child, parent in parents.items():
        if child != parent:
            children.setdefault(parent, []).append(child)
    out, queue = [], [pid]
    while queue:
        current = queue.pop(0)
        if current in out:
            continue
        out.append(current)
        queue.extend(children.get(current, []))
    return out


def kill_tree(pid: int, *, force: bool = False, wait_s: float = 10.0) -> list[int]:
    """Kill the process and its descendants; answer the members still alive after `wait_s`."""
    members = tree(pid)
    for member in reversed(members):
        _kill_one(member, force)
    end = time.monotonic() + wait_s
    survivors = [m for m in members if alive(m)]
    while survivors and time.monotonic() < end:
        time.sleep(0.2)
        if not force and not WINDOWS and time.monotonic() > end - wait_s / 2:
            for member in survivors:
                _kill_one(member, True)
        survivors = [m for m in survivors if alive(m)]
    return survivors
