"""The owner of one headless run: it holds the operating-system job, starts the agent in it, and waits.

    job.py --status FILE --log FILE --cwd DIR -- <argv...>

Windows: a job object with the kill-on-job-close limit and no breakaway limit; this owner joins it before it
starts the agent, so every child the agent starts is a member, and closing the owner ends them all. Elsewhere:
this owner leads its own session, which the agent and its children share. The status file gets the agent's
`pid` and `started_at` once it runs, `error` when it cannot start, and `exit_code` when it ends.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import process  # noqa: E402


def _write(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _join_job() -> str | None:
    """Put this process in a new kill-on-close job; answer the reason when that fails."""
    if not process.WINDOWS:
        return None
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", ctypes.c_uint64 * 6),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    job = k32.CreateJobObjectW(None, None)
    if not job:
        return f"CreateJobObject failed, error {ctypes.get_last_error()}"
    info = Extended()
    info.BasicLimitInformation.LimitFlags = 0x2000          # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        return f"SetInformationJobObject failed, error {ctypes.get_last_error()}"
    if not k32.AssignProcessToJobObject(job, k32.GetCurrentProcess()):
        return f"AssignProcessToJobObject failed, error {ctypes.get_last_error()}"
    return None             # the handle stays open until this process ends


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    status = Path(args.status)
    problem = _join_job()
    if problem:
        _write(status, {"error": f"could not place the run under an operating-system job: {problem}"})
        return 1
    try:
        with open(args.log, "ab") as log:
            child = subprocess.Popen(command, cwd=args.cwd, stdin=subprocess.DEVNULL, stdout=log,
                                     stderr=subprocess.STDOUT)
    except OSError as error:
        _write(status, {"error": f"could not start {command[0]}: {error}"})
        return 1
    state = {"pid": child.pid, "started_at": process.creation_time(child.pid)}
    _write(status, state)
    code = child.wait()
    _write(status, {**state, "exit_code": code})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
