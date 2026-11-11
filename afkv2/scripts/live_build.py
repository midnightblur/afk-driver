"""Prove the live build of a repository: start it, wait for an HTTP answer, stop it.

Command: `live_build.py prove|check [--start DIR] [--live JSON]`. `prove` writes the proven `live` block
into `.afkv2/config.json`; `check` writes nothing. Exit 0 ok, 1 refused, 2 unreadable input.
"""

from __future__ import annotations

import argparse
import ctypes
import http.client
import json
import os
import signal
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import IO

if sys.platform == "win32":
    from ctypes import wintypes

sys.path.insert(0, str(Path(__file__).resolve().parent))

from afkv2_config import Refusal, exit_code, live_block, read_config  # noqa: E402

POLL_SECONDS = 0.25
PROBE_SECONDS = 2
STOP_SECONDS = 15
GIT_SECONDS = 60
OUTPUT_TAIL = 800


@dataclass
class _Spawned:
    """A shell command and every process it starts. On Windows a job object holds them all, so a process
    the command detaches is stopped too; elsewhere the command leads its own session."""
    process: subprocess.Popen
    job: object = None


@dataclass
class LiveHandle:
    repo_root: Path
    live: dict
    spawned: _Spawned
    output: IO[bytes]


def prove(repo_root, live: dict | None = None) -> dict:
    """Prove the build, then write the block with `proven_at` and `proven_head`. Nothing is written on a refusal."""
    try:
        config_file, block = _block(repo_root, live)
        _prove(config_file.parent.parent, block)
        block = {**block, "proven_at": date.today().isoformat(), "proven_head": _head(config_file.parent.parent)}
        _write(config_file, block)
        return {"ok": True, "live": block}
    except Refusal as refusal:
        return _refused(refusal)


def check(repo_root, live: dict | None = None) -> dict:
    """The proof of `prove`, with no write."""
    try:
        config_file, block = _block(repo_root, live)
        _prove(config_file.parent.parent, block)
        return {"ok": True, "live": block}
    except Refusal as refusal:
        return _refused(refusal)


def start_live(repo_root, live: dict | None = None) -> LiveHandle:
    """Start the build and wait for its first answer. Raises `Refusal`; a refused start leaves no process."""
    config_file, block = _block(repo_root, live)
    root = config_file.parent.parent
    if _answers(block["address"]):
        raise Refusal("live-start-failed", f"{block['address']} already answers before the start: another server holds it")
    output = tempfile.TemporaryFile()
    try:
        spawned = _spawn(block["start"], root, output)
    except OSError as error:
        output.close()
        raise Refusal("live-start-failed", f"the start did not run: {error}") from None
    handle = LiveHandle(root, block, spawned, output)
    try:
        _wait_ready(handle)
    except BaseException:
        _kill(spawned)
        output.close()
        raise
    return handle


def stop_live(handle: LiveHandle) -> None:
    """Stop what `start_live` began: the `stop` command, else the process tree. Any process left is then killed.
    A stop command is proven on its own: the address must stop answering before the process tree is killed."""
    try:
        failure = _run_stop(handle) if handle.live["stop"] else None
        if not handle.live["stop"]:
            _kill(handle.spawned)
        if failure is None and not _gone(handle):
            failure = f"{handle.live['address']} still answers after the stop"
        if failure:
            raise Refusal("live-stop-failed", failure)
    finally:
        _kill(handle.spawned)
        handle.output.close()


def _run_stop(handle: LiveHandle) -> str | None:
    """Run the stop command in its own process group. A run past STOP_SECONDS is killed with its tree."""
    with tempfile.TemporaryFile() as output:
        try:
            stop = _spawn(handle.live["stop"], handle.repo_root, output)
        except OSError as error:
            return f"the stop command did not run: {error}"
        try:
            code = stop.process.wait(timeout=STOP_SECONDS)
        except subprocess.TimeoutExpired:
            return f"the stop command ran past {STOP_SECONDS} s"
        finally:
            _kill(stop)
        if code != 0:
            return f"the stop command exited {code}: {_read_tail(output)}"
    _wait_exit(handle.spawned.process, STOP_SECONDS)
    return None


def _prove(repo_root: Path, block: dict) -> None:
    stop_live(start_live(repo_root, block))


def _block(repo_root, live: dict | None) -> tuple[Path, dict]:
    config = read_config(repo_root, with_live=live is None)
    if not config["ok"]:
        raise Refusal(config["error"]["code"], config["error"]["reason"])
    if live is not None:
        return Path(config["config_file"]), live_block(live)
    if "live" not in config:
        raise Refusal("live-undefined", f"{config['config_file']} has no live block")
    return Path(config["config_file"]), config["live"]


def _wait_ready(handle: LiveHandle) -> None:
    deadline = time.monotonic() + handle.live["ready_seconds"]
    while True:
        if _answers(handle.live["address"]):
            return
        code = handle.spawned.process.poll()
        if code is not None:
            raise Refusal("live-start-failed", f"the start exited {code} before an answer: {_read_tail(handle.output)}")
        if time.monotonic() >= deadline:
            raise Refusal("live-no-answer", f"no HTTP answer at {handle.live['address']} in {handle.live['ready_seconds']} s")
        time.sleep(POLL_SECONDS)


def _answers(address: str) -> bool:
    """Any HTTP answer, an error status too, counts. The probe skips proxies and does not check a certificate:
    it asks only whether the build serves."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect(),
                                         urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    try:
        with opener.open(address, timeout=PROBE_SECONDS):
            return True
    except urllib.error.HTTPError:
        return True
    except (OSError, ValueError, http.client.HTTPException):
        return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A 3xx is the build's own answer: it comes back as an HTTPError and is not followed."""

    def redirect_request(self, *args, **kwargs):
        return None


def _gone(handle: LiveHandle) -> bool:
    deadline = time.monotonic() + STOP_SECONDS
    while _answers(handle.live["address"]):
        if time.monotonic() >= deadline:
            return False
        time.sleep(POLL_SECONDS)
    return True


def _spawn(command: str, cwd: Path, output: IO[bytes]) -> _Spawned:
    common = {"shell": True, "cwd": cwd, "stdin": subprocess.DEVNULL, "stdout": output, "stderr": subprocess.STDOUT}
    if sys.platform != "win32":
        return _Spawned(subprocess.Popen(command, start_new_session=True, **common))
    job = _windows_job()
    kernel32, ntdll = _windows_dlls()
    try:
        process = subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | _CREATE_SUSPENDED, **common)
    except OSError:
        kernel32.CloseHandle(job)
        raise
    if not kernel32.AssignProcessToJobObject(job, int(process._handle)):
        error = ctypes.WinError(ctypes.get_last_error())
        kernel32.CloseHandle(job)
        process.kill()
        _wait_exit(process, STOP_SECONDS)
        raise error
    ntdll.NtResumeProcess(int(process._handle))
    return _Spawned(process, job)


def _kill(spawned: _Spawned) -> None:
    """Stop every process of the command. Repeat calls are harmless."""
    if spawned.job is not None:
        kernel32, _ = _windows_dlls()
        kernel32.TerminateJobObject(spawned.job, 1)
        kernel32.CloseHandle(spawned.job)
        spawned.job = None
    elif sys.platform == "win32":
        if spawned.process.poll() is None:
            spawned.process.kill()
    else:
        try:
            os.killpg(spawned.process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    _wait_exit(spawned.process, STOP_SECONDS)


_CREATE_SUSPENDED = 0x00000004
_KILL_ON_JOB_CLOSE = 0x00002000
_EXTENDED_LIMIT_INFORMATION = 9


def _windows_dlls():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    kernel32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtResumeProcess.argtypes = (wintypes.HANDLE,)
    return kernel32, ntdll


def _windows_job():
    """A job that ends its processes when its last handle closes, so a crash of this script also stops the build."""

    class _Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class _Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", _Basic), ("IoInfo", ctypes.c_uint64 * 6),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel32, _ = _windows_dlls()
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    info = _Extended()
    info.BasicLimitInformation.LimitFlags = _KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(job, _EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info)):
        error = ctypes.WinError(ctypes.get_last_error())
        kernel32.CloseHandle(job)
        raise error
    return job


def _wait_exit(process: subprocess.Popen, seconds: float) -> None:
    try:
        process.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        pass


def _head(repo_root: Path) -> str:
    try:
        done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=GIT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Refusal("git-failed", f"git rev-parse HEAD: {error}") from None
    if done.returncode != 0:
        raise Refusal("git-failed", f"git rev-parse HEAD: {done.stderr.strip()}")
    return done.stdout.strip()


def _write(config_file: Path, block: dict) -> None:
    temporary = config_file.with_suffix(".tmp")
    try:
        raw = json.loads(config_file.read_text(encoding="utf-8"))
        raw["live"] = block
        temporary.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        os.replace(temporary, config_file)
    except (OSError, ValueError) as error:
        temporary.unlink(missing_ok=True)
        raise Refusal("config-write-failed", f"{config_file}: {error}") from None


def _read_tail(output: IO[bytes]) -> str:
    """The last OUTPUT_TAIL characters of the output file, read from near its end only."""
    size = output.seek(0, os.SEEK_END)
    output.seek(max(0, size - OUTPUT_TAIL * 4))
    return output.read().decode("utf-8", "replace").strip()[-OUTPUT_TAIL:]


def _refused(refusal: Refusal) -> dict:
    return {"ok": False, "error": {"code": refusal.code, "reason": refusal.reason}}


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise Refusal("usage", message)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(prog="live_build.py", add_help=False)
    parser.add_argument("verb", choices=["prove", "check"])
    parser.add_argument("--start", default=None)
    parser.add_argument("--live", default=None)
    try:
        args = parser.parse_args(argv)
        try:
            live = None if args.live is None else json.loads(args.live)
        except json.JSONDecodeError as error:
            raise Refusal("usage", f"--live: {error}") from None
        answer = (prove if args.verb == "prove" else check)(Path(args.start or os.getcwd()), live)
    except Refusal as refusal:
        answer = _refused(refusal)
    print(json.dumps(answer))
    return exit_code(answer)


if __name__ == "__main__":
    sys.exit(main())
