"""The one way the engine runs the lavish host, at the pinned version.

`run(argv)` takes `open`, `poll` or `end` on one page and answers `(exit code, stdout text)`.
A server the host starts outlives this process; a killed process takes the host command down.

Exit codes of the launcher itself (nothing upstream ran). Each one leads to the Markdown fallback:
    64   refused: an operation or argument outside the grammar, a missing or non-HTML page,
         `LAVISH_AXI_HOST` set, or an installed host that is not the pinned version
    65   the page runtime could not be injected
    69   the `.cmd` path could not set up the jobs that bind its processes' lifetime
    127  `lavish-axi` is not on PATH (run setup)

Also here: the reader of the host's output, and the Codex "page waiting" record.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from shell import inject

PIN = "0.1.80"
FORBIDDEN = {
    "share": "publishes the page to a public third-party host",
    "setup": "installs session hooks into the coding agent",
    "update": "self-updates past the pin",
    "stop": "stops the server that other sessions share",
}
FALLBACK_EXITS = {64, 65, 69, 127}
HTML = re.compile(r"\.html?$", re.IGNORECASE)
CMD_SAFE = re.compile(r"^[\w./\\:@ ,+=-]*$")
KILL_ON_CLOSE = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
SILENT_BREAKAWAY = 0x1000  # JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK
PROCESS_SET_QUOTA, PROCESS_TERMINATE, PROCESS_QUERY_LIMITED = 0x0100, 0x0001, 0x1000
WAITING_PREFIX = "page-waiting-"
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


class Refused(Exception):
    """The arguments are outside the launcher's grammar."""


class Unbound(Exception):
    """The `.cmd` path could not tie its children's lifetime to this process."""


def plan(argv: list[str]) -> str | None:
    """The page to inject before the host runs, or None; Refused outside the grammar."""
    if "LAVISH_AXI_HOST" in os.environ:
        raise Refused("LAVISH_AXI_HOST is set; it widens the server bind beyond loopback. Unset it.")
    if not argv:
        raise Refused("no operation given")
    op, rest = argv[0], argv[1:]
    if op in FORBIDDEN:
        raise Refused(f"`{op}` is forbidden: it {FORBIDDEN[op]}")
    if op == "end":
        if len(rest) != 1 or not HTML.search(rest[0]):
            raise Refused("`end` takes exactly one .html page")
        return None
    if op == "poll":
        timed = len(rest) == 3 and rest[1] == "--timeout-ms" and rest[2].isdigit()
        if not rest or not (len(rest) == 1 or timed):
            raise Refused("`poll` takes one .html page and an optional `--timeout-ms <ms>`")
        _page(rest[0])
        return None
    if op != "open":
        raise Refused(f"`{op}` is not an operation this launcher runs")
    if not rest or rest[1:] not in ([], ["--no-open"], ["--reopen"]):
        raise Refused("`open` takes one .html page and at most one of `--no-open` or `--reopen`")
    return _page(rest[0])


def _page(target: str) -> str:
    if not HTML.search(target):
        raise Refused(f"{target} is not an .html page")
    if not os.path.isfile(target):
        raise Refused(f"{target} does not exist")
    return target


def _package(found: Path) -> Path:
    """The npm package folder of a found `lavish-axi`: a global shim, a local `.bin` shim, or a link."""
    beside = found.parent / "node_modules" / "lavish-axi"
    if beside.is_dir():
        return beside
    if found.parent.name == ".bin":
        return found.parent.parent / "lavish-axi"
    return found.resolve().parents[1]


def _manifest(package: Path) -> dict:
    try:
        meta = json.loads((package / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return meta if isinstance(meta, dict) else {}


def npm_script(package: Path) -> Path | None:
    """The JavaScript entry an npm `.cmd` shim runs, from the package's own `bin` field."""
    entry = _manifest(package).get("bin")
    entry = entry if isinstance(entry, str) else entry.get("lavish-axi") if isinstance(entry, dict) else None
    script = package / entry if isinstance(entry, str) else None
    return script if script is not None and script.is_file() else None


def upstream(args: list[str]) -> list[str] | None:
    """The argument vector that runs the pinned `lavish-axi` with `args`, or None when it is absent."""
    found = shutil.which("lavish-axi")
    if not found:
        return None
    package = _package(Path(found))
    version = _manifest(package).get("version")
    if version != PIN:
        raise Refused(f"lavish-axi is {version}; this engine needs exactly {PIN}. Run setup.")
    if os.name == "nt" and found.lower().endswith((".cmd", ".bat")):
        script = npm_script(package)
        local = Path(found).with_name("node.exe")
        node = str(local) if local.is_file() else shutil.which("node")
        if script is not None and node:
            return [node, str(script), *args]
        if not all(CMD_SAFE.match(arg) for arg in args):
            raise Refused("lavish-axi resolves to a batch shim with no readable npm package; "
                          "an argument holds characters cmd.exe would re-parse. Run setup.")
    return [found, *args]


def kernel32():
    import ctypes
    from ctypes import wintypes

    handle = wintypes.HANDLE
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = handle
    kernel.OpenProcess.restype = handle
    kernel.SetInformationJobObject.argtypes = [handle, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [handle, handle]
    kernel.CloseHandle.argtypes = [handle]
    kernel.CreateIoCompletionPort.restype = handle
    kernel.CreateIoCompletionPort.argtypes = [handle, handle, ctypes.c_size_t, wintypes.DWORD]
    kernel.GetQueuedCompletionStatus.argtypes = [handle, ctypes.POINTER(wintypes.DWORD),
                                                 ctypes.POINTER(ctypes.c_size_t),
                                                 ctypes.POINTER(ctypes.c_void_p), wintypes.DWORD]
    return kernel


def assign(kernel, job, pid: int) -> bool:
    process = kernel.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
    if not process:
        return False
    try:
        return bool(kernel.AssignProcessToJobObject(job, process))
    finally:
        kernel.CloseHandle(process)


def lifetime_job(kernel):
    """A job that kills its processes when this process's handle closes; what they start breaks away."""
    import ctypes
    from ctypes import wintypes

    class Limits(ctypes.Structure):
        _fields_ = [("a", ctypes.c_int64), ("b", ctypes.c_int64), ("flags", wintypes.DWORD),
                    ("c", ctypes.c_size_t), ("d", ctypes.c_size_t), ("e", wintypes.DWORD),
                    ("f", ctypes.c_size_t), ("g", wintypes.DWORD), ("h", wintypes.DWORD),
                    ("io", ctypes.c_uint64 * 6), ("i", ctypes.c_size_t), ("j", ctypes.c_size_t),
                    ("k", ctypes.c_size_t), ("l", ctypes.c_size_t)]

    job = kernel.CreateJobObjectW(None, None)
    limits = Limits(flags=KILL_ON_CLOSE | SILENT_BREAKAWAY)
    if job and kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        return job
    return None


def bind_child_lifetime(pid: int):
    """Windows: hold the host command alone in a kill-on-close job. Returns the job, or None."""
    if os.name != "nt":
        return None
    try:
        kernel = kernel32()
        job = lifetime_job(kernel)
        return job if job and assign(kernel, job, pid) else None
    except Exception:
        return None


def parent_of(pid: int) -> int | None:
    import ctypes

    class Basic(ctypes.Structure):
        _fields_ = [("exit", ctypes.c_long), ("peb", ctypes.c_void_p), ("affinity", ctypes.c_size_t),
                    ("priority", ctypes.c_long), ("pid", ctypes.c_size_t), ("parent", ctypes.c_size_t)]

    kernel, ntdll = kernel32(), ctypes.WinDLL("ntdll")
    process = kernel.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
    if not process:
        return None
    try:
        info = Basic()
        failed = ntdll.NtQueryInformationProcess(ctypes.c_void_p(process), 0, ctypes.byref(info),
                                                 ctypes.sizeof(info), None)
        return None if failed else info.parent
    finally:
        kernel.CloseHandle(process)


def start_batch(command: list[str], **streams):
    """`.cmd` path: run cmd.exe suspended in a watch job that reports each new process, bind every
    process cmd.exe starts to the lifetime job as its notice arrives, then resume cmd.exe.

    Returns (child, jobs); raises Unbound, with nothing left running, when a job cannot be set up."""
    import ctypes
    from ctypes import wintypes

    class Port(ctypes.Structure):
        _fields_ = [("key", ctypes.c_void_p), ("port", wintypes.HANDLE)]

    def checked(result, what: str):
        if not result:
            raise Unbound(f"{what} setup failed (Windows error {ctypes.get_last_error()})")
        return result

    kernel = kernel32()
    lifetime = checked(lifetime_job(kernel), "lifetime job")
    watch = checked(kernel.CreateJobObjectW(None, None), "watch job")
    port = checked(kernel.CreateIoCompletionPort(wintypes.HANDLE(-1), None, 0, 1), "completion port")
    link = Port(key=None, port=port)
    checked(kernel.SetInformationJobObject(watch, 7, ctypes.byref(link), ctypes.sizeof(link)), "watch job notice")
    child = subprocess.Popen(command, creationflags=0x4, **streams)  # CREATE_SUSPENDED
    handle = int(child._handle)
    if not (kernel.AssignProcessToJobObject(watch, handle) and kernel.AssignProcessToJobObject(lifetime, handle)):
        error = ctypes.get_last_error()
        child.kill()
        child.wait()
        raise Unbound(f"cmd.exe could not join its jobs (Windows error {error})")

    def bind_new_children() -> None:
        code, key, pid = wintypes.DWORD(), ctypes.c_size_t(), ctypes.c_void_p()
        while kernel.GetQueuedCompletionStatus(port, ctypes.byref(code), ctypes.byref(key), ctypes.byref(pid),
                                               0xFFFFFFFF):
            if code.value == 6 and pid.value and parent_of(pid.value) == child.pid:  # JOB_OBJECT_MSG_NEW_PROCESS
                assign(kernel, lifetime, pid.value)

    threading.Thread(target=bind_new_children, daemon=True).start()
    ctypes.WinDLL("ntdll").NtResumeProcess(ctypes.c_void_p(handle))
    return child, (lifetime, watch, port)


def _spawn(command: list[str], **streams):
    """The child and whatever keeps its lifetime job open; Unbound when a `.cmd` cannot be bound."""
    if command[0].lower().endswith((".cmd", ".bat")):
        return start_batch(command, **streams)
    child = subprocess.Popen(command, **streams)
    return child, bind_child_lifetime(child.pid)


def run(argv: list[str]) -> tuple[int, str]:
    """Run the host. Output goes through a file: a server the host starts may hold a pipe open."""
    try:
        target = plan(argv)
        command = upstream(argv[1:] if argv[0] == "open" else argv)
    except Refused as problem:
        return 64, f"refused: {problem}"
    if command is None:
        return 127, "lavish-axi is not on PATH; run setup"
    if target is not None:
        try:
            inject.inject_file(target)
        except inject.InjectError as problem:
            return 65, str(problem)
    with tempfile.TemporaryFile() as out:
        try:
            child, jobs = _spawn(command, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.DEVNULL)  # noqa: F841
        except Unbound as problem:
            return 69, f"refused to run the batch shim: {problem}"
        try:
            code = child.wait()
        except KeyboardInterrupt:
            child.kill()
            child.wait()
            return 130, "interrupted"
        out.seek(0)
        return code, out.read().decode("utf-8")


# The host's output is TOON. This reads the fields the engine uses, in the two shapes the
# encoder writes for a list of objects: one table row each, or one expanded `- ` block each.
QUOTED = re.compile(r'"((?:[^"\\]|\\.)*)"')
KEY_LINE = re.compile(r'^(?P<key>[A-Za-z_][\w]*)(?P<head>\[\d+\](?:\{[^}]*\})?)?:(?: (?P<value>.*))?$')
ESCAPES = {"\\": "\\", '"': '"', "n": "\n", "r": "\r", "t": "\t"}


def _unquote(text: str) -> str:
    out, i = [], 0
    while i < len(text):
        if text[i] != "\\":
            out.append(text[i])
            i += 1
        elif text[i + 1] == "u":
            out.append(chr(int(text[i + 2:i + 6], 16)))
            i += 6
        else:
            out.append(ESCAPES[text[i + 1]])
            i += 2
    return "".join(out)


def _scalar(text: str):
    text = text.strip()
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        return _unquote(text[1:-1])
    return {"true": True, "false": False, "null": None}.get(text, text)


def _split_row(row: str) -> list:
    cells, i = [], 0
    while i <= len(row):
        match = QUOTED.match(row, i) if i < len(row) else None
        if match:
            cells.append(_unquote(match.group(1)))
            i = match.end() + 1
        else:
            end = row.find(",", i)
            end = len(row) if end < 0 else end
            cells.append(_scalar(row[i:end]))
            i = end + 1
    return cells


def _block(lines: list[str], start: int, indent: int) -> tuple[dict, int]:
    """Scalar `key: value` lines at `indent`, from `start`; deeper lines are skipped."""
    fields, i = {}, start
    while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip(" ")) >= indent):
        match = KEY_LINE.match(lines[i][indent:]) if lines[i].strip() else None
        if match and match.group("value") is not None:
            fields[match.group("key")] = _scalar(match.group("value"))
        i += 1
    return fields, i


def _prompts(lines: list[str], start: int, head: str) -> tuple[list[dict], int]:
    if "{" in head:
        names = head[head.index("{") + 1:head.index("}")].split(",")
        rows, i = [], start
        while i < len(lines) and lines[i].startswith("  "):
            rows.append(dict(zip(names, _split_row(lines[i][2:]))))
            i += 1
        return rows, i
    rows, i = [], start
    while i < len(lines) and lines[i].startswith("  - "):
        first = KEY_LINE.match(lines[i][4:])
        row = {first.group("key"): _scalar(first.group("value") or "")} if first else {}
        more, i = _block(lines, i + 1, 4)
        rows.append({**row, **more})
    return rows, i


def parse_host_output(text: str) -> dict:
    """`{"session": {...}, "prompts": [...], "error": ..., "code": ...}`, with the keys found."""
    lines = text.replace("\r\n", "\n").split("\n")
    parsed: dict = {}
    i = 0
    while i < len(lines):
        match = KEY_LINE.match(lines[i])
        i += 1
        if not match:
            continue
        key = match.group("key")
        if key == "session":
            parsed["session"], i = _block(lines, i, 2)
        elif key == "prompts" and match.group("head"):
            parsed["prompts"], i = _prompts(lines, i, match.group("head"))
        elif key in ("error", "code") and match.group("value") is not None:
            parsed[key] = _scalar(match.group("value"))
    return parsed


def poll_status(argv: list[str]) -> tuple[str, dict]:
    """Run one poll and name what came back: a host status, a fallback exit, or a host error."""
    code, out = run(argv)
    if code in FALLBACK_EXITS:
        return "fallback", {"exit": code, "reason": out}
    parsed = parse_host_output(out)
    if code != 0:
        status = "no-session" if parsed.get("code") == "NOT_FOUND" else "error"
        return status, {"exit": code, "code": parsed.get("code"), "reason": parsed.get("error") or out.strip()}
    session = parsed.get("session") or {}
    return session.get("status") or "error", {
        "raw": "\n".join(str(p.get("prompt", "")) for p in parsed.get("prompts", [])),
        "prompts": parsed.get("prompts", []),
        "session_ended": session.get("session_ended") is True,
        "reason": out.strip(),
    }


def _waiting_path(folder: Path, session: str) -> Path:
    name = session if SAFE_NAME.match(session) else hashlib.sha256(session.encode("utf-8")).hexdigest()[:24]
    return folder / f"{WAITING_PREFIX}{name}.json"


def write_waiting_record(folder: Path, session: str, document: str, page: str) -> Path:
    """Codex: one "page waiting" record per session; the Stop hook reads it."""
    record = {"session": session, "document": document, "page": page,
              "written": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    path = _waiting_path(folder, session)
    inject.write_if_changed(path, json.dumps(record, indent=2).encode("utf-8"))
    return path


def read_waiting_record(folder: Path, session: str) -> dict | None:
    try:
        record = json.loads(_waiting_path(folder, session).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) and isinstance(record.get("page"), str) else None


def clear_waiting_record(folder: Path, session: str) -> None:
    try:
        _waiting_path(folder, session).unlink()
    except OSError:
        pass
