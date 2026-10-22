"""Operating-system process facts for the transport kinds: creation time, liveness, and a whole-tree kill.

`kill_tree` lists the whole tree first, then kills every member by its own id, so a child whose parent
dies first is still reached; it never relies on a signal a shell trap catches. It answers the members it
could not stop, by id, which a caller reports as survivors. `kin` finds what no tree lists: a process whose
parent ended, in a console (Windows) or session (POSIX) that a tree member uses.
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

    def _msys_parents() -> dict[int, int | None] | None:
        """Windows id of each MSYS process to the Windows id of its live MSYS parent, None for MSYS
        process 1 or a parent that is gone; empty without Git's ps, None when its ps failed."""
        ps = _msys_ps()
        if ps is None:
            return {}
        try:
            done = subprocess.run([ps, "-e"], capture_output=True, text=True, timeout=10, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
        if done.returncode != 0:
            return None
        rows = [line.split() for line in done.stdout.splitlines()[1:]]
        rows = [r for r in rows if len(r) >= 4 and r[0].isdigit() and r[1].isdigit() and r[3].isdigit()]
        winpid = {int(r[0]): int(r[3]) for r in rows}
        return {int(r[3]): winpid.get(int(r[1])) for r in rows}

    _DETACHED_PROCESS = 0x00000008      # the helper starts with no console, so it can attach to one
    _CONSOLE = r"""
import ctypes, sys
from ctypes import wintypes
k = ctypes.WinDLL("kernel32", use_last_error=True)
seen, unread = set(), []
for pid in map(int, sys.argv[1:]):
    if pid in seen:
        continue
    k.FreeConsole()
    if not k.AttachConsole(pid):
        if ctypes.get_last_error() == 5:
            unread.append(pid)
        continue
    size = n = 4096
    while n >= size:
        size = n + 64
        ids = (wintypes.DWORD * size)()
        n = k.GetConsoleProcessList(ids, size)
    seen.update(ids[i] for i in range(n))
seen.discard(k.GetCurrentProcessId())
print(" ".join(map(str, seen)))
print(" ".join(map(str, unread)))
"""

    def _console_peers(pids: list[int]) -> tuple[list[int], str | None]:
        """Every process attached to a console one of `pids` uses, and what kept the list incomplete."""
        try:
            done = subprocess.run([sys.executable, "-I", "-c", _CONSOLE, *map(str, pids)],
                                  capture_output=True, text=True, timeout=10, check=False,
                                  creationflags=_DETACHED_PROCESS)
        except (OSError, subprocess.SubprocessError) as error:
            return [], f"the console lists could not be read ({error})"
        if done.returncode != 0:
            return [], f"the console lists could not be read (exit {done.returncode})"
        found, unread = (done.stdout.splitlines() + ["", ""])[:2]
        ids = ", ".join(unread.split())
        gap = f"the consoles of processes {ids} could not be read" if ids else None
        return [int(x) for x in found.split() if x.isdigit()], gap

    def _parent_ended(pid: int, parents: dict[int, int], peers: set[int],
                      msys: dict[int, int | None] | None) -> bool | None:
        """Its Windows parent is gone or holds a reused id, and for an MSYS process its MSYS parent is too;
        None when a creation time or Git's ps could not be read."""
        parent = parents.get(pid)
        if parent in parents and parent != pid:
            mine, theirs = _created(pid), _created(parent)
            if mine is None or theirs is None:
                return None
            if theirs <= mine:
                return False
        return None if msys is None else msys.get(pid) is None

    _started = _created

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

    def _msys_parents() -> dict[int, int | None] | None:
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

    def _console_peers(pids: list[int]) -> tuple[list[int], str | None]:
        """Every process of a session one of `pids` belongs to; POSIX has no console to read."""
        sids = set()
        for pid in pids:
            try:
                sids.add(os.getsid(pid))
            except OSError:
                pass                    # gone
        return [m for sid in sids for m in session_members(sid)], None

    def _parent_ended(pid: int, parents: dict[int, int], peers: set[int],
                      msys: dict[int, int | None] | None) -> bool | None:
        """Its parent is outside the sessions read: init or a subreaper took it when its parent ended."""
        return parents.get(pid) not in peers

    def _started(pid: int):
        """Start time in clock ticks from /proc where it exists, else whole seconds from ps."""
        if os.path.exists("/proc/self/stat"):
            try:
                return int(open(f"/proc/{pid}/stat", encoding="utf-8").read().rsplit(")", 1)[1].split()[19])
            except (OSError, ValueError, IndexError):
                return None
        return creation_time(pid)

def kin(pid: int, members: list[int]) -> tuple[list[int], str | None]:
    """Processes outside `members` whose parent ended, in a console or session a member uses, started no
    earlier than `pid`, and neither this caller nor an ancestor of it or of `pid`, each with its own
    descendants; with what kept the search incomplete, or None."""
    mine = _started(pid)
    if mine is None:
        return [], f"the start time of process {pid} could not be read"
    peers, gap = _console_peers(members)
    parents, msys = _parents(), _msys_parents()     # read after the peers: a peer missing here has ended
    gaps = [gap] if gap else []
    if not parents:
        return [], "; ".join(gaps + ["the process list could not be read"])

    def line(start: int) -> set[int]:
        seen: set[int] = set()
        todo = [start]
        while todo:
            current = todo.pop()
            if current and current not in seen:
                seen.add(current)
                todo += [parents.get(current, 0), (msys or {}).get(current) or 0]
        return seen

    pool, skip = set(peers), set(members) | line(os.getpid()) | line(pid)
    found, unknown = [], []
    for member in sorted(pool - skip):
        ended = _parent_ended(member, parents, pool, msys) if member in parents else False
        if ended is False:
            continue
        born = _started(member) if ended else None
        if born is None:
            if alive(member):
                unknown.append(str(member))
        elif born >= mine:
            found.append(member)
    if unknown:
        gaps.append(f"the start or parent of processes {', '.join(unknown)} could not be read")
    found = list(dict.fromkeys(m for orphan in found for m in tree(orphan, (parents, msys), skip)))
    return found, "; ".join(gaps) or None

def tree(pid: int, snapshot: tuple[dict[int, int], dict[int, int | None] | None] | None = None,
         prune: set[int] | frozenset[int] = frozenset()) -> list[int]:
    """The process and every live descendant, root first; on Windows also each MSYS child, whose
    Windows parent is a fork stub that is gone by the time the child runs. Windows reuses a dead
    parent's id, so a child older than the process holding its parent's id is not its child; an MSYS
    edge is exempt, since an MSYS exec gives the parent a newer Windows process. `snapshot` is a
    process list and MSYS parent map the caller already read, so both views agree; the walk never
    enters a process in `prune` nor goes below it."""
    parents, msys_parents = snapshot if snapshot else (_parents(), _msys_parents())
    children: dict[int, list[int]] = {}
    for child, parent in parents.items():
        if child != parent:
            children.setdefault(parent, []).append(child)
    msys: set[tuple[int, int]] = set()
    for child, parent in (msys_parents or {}).items():
        if parent is not None and parent != child and child in parents:
            children.setdefault(parent, []).append(child)
            msys.add((parent, child))
    born: dict[int, int | None] = {}

    def created(member: int) -> int | None:
        if member not in born:
            born[member] = _created(member)
        return born[member]

    out, queue = [], [pid]
    while queue:
        current = queue.pop(0)
        if current in out or current in prune:
            continue
        out.append(current)
        mine = created(current)
        queue.extend(k for k in children.get(current, []) if (current, k) in msys
                     or mine is None or created(k) is None or created(k) >= mine)
    return out


def kill_tree(pid: int, *, force: bool = False, wait_s: float = 10.0, extra: list[int] = ()) -> list[int]:
    """Kill the process, its descendants and `extra`; answer those still alive after `wait_s`."""
    members = tree(pid)
    members += [m for m in extra if m not in members]
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
    extra, gap = kin(pid, tree(pid)) if with_kin else ([], None)
    survivors = kill_tree(pid, force=force, wait_s=wait_s, extra=extra)
    if session is not None:
        survivors += kill_session(session, keep=session, force=force)
    if survivors:
        return {"stopped": False, "reason": f"{len(survivors)} processes survived the kill", "survivors": survivors}
    if gap:
        return {"stopped": False, "survivors": [],
                "reason": f"the tree was killed, but {gap}, so a process whose parent ended may still run"}
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
