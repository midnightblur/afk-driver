"""Operating-system process facts for the transport kinds: creation time, liveness, and a whole-tree kill.

`kill_tree` lists the whole tree first, then kills every member by its own id, so a child whose parent
dies first is still reached; it never relies on a signal a shell trap catches. It answers the members it
could not stop, by id, which a caller reports as survivors. With `kin` it also kills a descendant whose
parent ended first, which no tree lists: a newer process in the root's console (Windows) or session (POSIX).
"""
from __future__ import annotations

import os
import shutil
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

    def _created(pid: int) -> int | None:
        """The creation time in 100 ns ticks, or None when the process cannot be opened."""
        handle = _open(pid)
        if not handle:
            return None
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            if not _k32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                return None
            return (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        finally:
            _k32.CloseHandle(handle)

    def creation_time(pid: int) -> str | None:
        ticks = _created(pid)
        return None if ticks is None else _iso(ticks / 10_000_000 - 11_644_473_600)

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

    def _msys_ps() -> str | None:
        """Git for Windows' `ps`, which knows the MSYS parent of a process whose Windows parent is gone."""
        found = [os.path.join(os.path.dirname(os.path.dirname(git)), "usr", "bin", "ps.exe")
                 for git in filter(None, [shutil.which("git")])]
        found += [os.path.join(os.environ.get(k, ""), "Git", "usr", "bin", "ps.exe")
                  for k in ("ProgramFiles", "ProgramW6432", "LOCALAPPDATA") if os.environ.get(k)]
        return next((path for path in found if os.path.isfile(path)), None)

    def _msys_children() -> dict[int, list[int]]:
        """Windows id of each MSYS process to the Windows ids of its MSYS children; empty without Git's ps."""
        ps = _msys_ps()
        if ps is None:
            return {}
        try:
            done = subprocess.run([ps, "-e"], capture_output=True, text=True, timeout=10, check=False)
        except (OSError, subprocess.SubprocessError):
            return {}
        rows = [line.split() for line in done.stdout.splitlines()[1:]]
        rows = [r for r in rows if len(r) >= 4 and r[0].isdigit() and r[1].isdigit() and r[3].isdigit()]
        winpid = {int(r[0]): int(r[3]) for r in rows}
        out: dict[int, list[int]] = {}
        for r in rows:
            parent = winpid.get(int(r[1]))
            if parent is not None and parent != int(r[3]):
                out.setdefault(parent, []).append(int(r[3]))
        return out

    _CONSOLE = r"""
import ctypes, sys
from ctypes import wintypes
k = ctypes.WinDLL("kernel32")
seen = set()
for pid in map(int, sys.argv[1:]):
    if pid in seen:
        continue
    k.FreeConsole()
    if not k.AttachConsole(pid):
        continue
    ids = (wintypes.DWORD * 4096)()
    n = k.GetConsoleProcessList(ids, 4096)
    seen.update(ids[i] for i in range(min(n, 4096)))
seen.discard(k.GetCurrentProcessId())
sys.stdout.write(" ".join(map(str, seen)))
"""

    def _containers(pids: list[int]) -> list[int]:
        """Every process attached to a console of one of `pids`, read by a helper started with no console."""
        try:
            done = subprocess.run([sys.executable, "-I", "-c", _CONSOLE, *map(str, pids)],
                                  capture_output=True, text=True, timeout=10, check=False,
                                  creationflags=0x00000008)
        except (OSError, subprocess.SubprocessError):
            return []
        return [int(x) for x in done.stdout.split() if x.isdigit()] if done.returncode == 0 else []

    _born = _created

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

    def _msys_children() -> dict[int, list[int]]:
        return {}

    def _created(pid: int) -> int | None:
        return None                     # a POSIX orphan moves to init, so a parent id is never stale

    def session_members(sid: int) -> list[int]:
        """Every live process of one session, by os.getsid, which every POSIX system has."""
        out = []
        for pid in _parents():
            try:
                if os.getsid(pid) == sid:
                    out.append(pid)
            except OSError:
                pass                    # gone, or another user's process
        return out

    def _containers(pids: list[int]) -> list[int]:
        sids = set()
        for pid in pids:
            try:
                sids.add(os.getsid(pid))
            except OSError:
                pass                    # gone
        return [m for sid in sids for m in session_members(sid)]

    _born = creation_time


def kin(pid: int, members: list[int]) -> list[int]:
    """Processes outside `members` in a console or session of one of them, born no earlier than `pid`,
    and neither this caller, its ancestor, nor an ancestor of `pid`: a descendant whose parent ended."""
    mine = _born(pid)
    if mine is None:
        return []
    parents = _parents()

    def line(start: int) -> set[int]:
        seen: set[int] = set()
        while start and start not in seen:
            seen.add(start)
            start = parents.get(start, 0)
        return seen

    skip = set(members) | line(os.getpid()) | line(pid)
    out = []
    for member in set(_containers(members)):
        born = None if member in skip else _born(member)
        if born is not None and born >= mine:
            out.append(member)
    return out


def tree(pid: int) -> list[int]:
    """The process and every live descendant, root first; on Windows also each MSYS child, whose
    Windows parent is a fork stub that is gone by the time the child runs. Windows reuses a dead
    parent's id, so a child older than the process holding its parent's id is not its child; an MSYS
    edge is exempt, since an MSYS exec gives the parent a newer Windows process."""
    parents = _parents()
    children: dict[int, list[int]] = {}
    for child, parent in parents.items():
        if child != parent:
            children.setdefault(parent, []).append(child)
    msys: set[tuple[int, int]] = set()
    for parent, kids in _msys_children().items():
        children.setdefault(parent, []).extend(k for k in kids if k in parents)
        msys.update((parent, k) for k in kids)
    born: dict[int, int | None] = {}

    def created(member: int) -> int | None:
        if member not in born:
            born[member] = _created(member)
        return born[member]

    out, queue = [], [pid]
    while queue:
        current = queue.pop(0)
        if current in out:
            continue
        out.append(current)
        mine = created(current)
        queue.extend(k for k in children.get(current, []) if (current, k) in msys
                     or mine is None or created(k) is None or created(k) >= mine)
    return out


def kill_tree(pid: int, *, force: bool = False, wait_s: float = 10.0, with_kin: bool = False) -> list[int]:
    """Kill the process, its descendants and, with `with_kin`, its `kin`; answer those alive after wait_s."""
    members = tree(pid)
    if with_kin:
        members += kin(pid, members)
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


def stop(pid: int | None, *, force: bool, wait_s: float, none: str = "nothing to kill",
         session: int | None = None, with_kin: bool = False) -> dict:
    """agent-stop's answer for one process tree, with its `kin` when asked, and on POSIX what is left of its
    `session`: stopped with a method, or not with its survivors."""
    if pid is None:
        return {"stopped": True, "method": none}
    if not alive(pid):
        return {"stopped": True, "method": "not running"}
    survivors = kill_tree(pid, force=force, wait_s=wait_s, with_kin=with_kin)
    if session is not None:
        survivors += kill_session(session, keep=session, force=force)
    if survivors:
        return {"stopped": False, "reason": f"{len(survivors)} processes survived the kill", "survivors": survivors}
    return {"stopped": True, "method": "killed the process tree"}


def kill_session(sid: int, *, keep: int, force: bool = False, wait_s: float = 5.0) -> list[int]:
    """POSIX: kill every process left in session `sid` but `keep`, which catches a descendant that moved
    to init before the stop; answer those still alive. Windows has no sessions here: a job holds the run."""
    if WINDOWS:
        return []
    members = [m for m in session_members(sid) if m != keep and m != os.getpid()]
    for member in members:
        _kill_one(member, force)
    end = time.monotonic() + wait_s
    survivors = [m for m in members if alive(m)]
    while survivors and time.monotonic() < end:
        time.sleep(0.2)
        survivors = [m for m in survivors if alive(m)]
    for member in survivors:
        _kill_one(member, True)
    return [m for m in survivors if alive(m)]
