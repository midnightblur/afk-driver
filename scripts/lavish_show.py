"""The one agent-facing lavish-axi command: inject the page runtime, then run the pinned upstream.

    afk-python scripts/lavish_show.py <file> [--no-open|--reopen]
    afk-python scripts/lavish_show.py poll <file> [--agent-reply <message>]
    afk-python scripts/lavish_show.py end <file>
    afk-python scripts/lavish_show.py stop
    afk-python scripts/lavish_show.py playbook [id]

Open, reopen and poll first inject the runtime (`lavish/inject.py`; the file is rewritten
only when its bytes change), then run `lavish-axi` with the same arguments, the inherited
standard streams and its exit status. On POSIX the upstream replaces this process; on
Windows it runs as a child bound to this process's lifetime, without `cmd.exe`.

Exit codes of the wrapper itself (nothing upstream ran):
    64   refused: `share`, `setup`, `update`, any other operation or argument shape, a
         missing or non-HTML target, or `LAVISH_AXI_HOST` in the environment
    65   the page runtime could not be injected
    127  `lavish-axi` is not on PATH (run `/afk:setup`)

Doctrine: `LAVISH.md`. Standard library only.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lavish import inject  # noqa: E402

FORBIDDEN = {
    "share": "publishes the page to a public third-party host",
    "setup": "installs session hooks into the coding agent",
    "update": "self-updates past the pin in LAVISH.md",
}
HTML = re.compile(r"\.html?$", re.IGNORECASE)
CMD_SAFE = re.compile(r"^[\w./\\:@ ,+=-]*$")


class Refused(Exception):
    """The arguments are outside the wrapper's grammar."""


def plan(argv: list[str]) -> str | None:
    """The page to inject before the upstream runs, or None; Refused outside the grammar."""
    if "LAVISH_AXI_HOST" in os.environ:
        raise Refused("LAVISH_AXI_HOST is set; it widens the server bind beyond loopback. Unset it.")
    if not argv:
        raise Refused("no operation given")
    op, rest = argv[0], argv[1:]
    if op in FORBIDDEN:
        raise Refused(f"`{op}` is forbidden: it {FORBIDDEN[op]}")
    if op == "stop":
        if rest:
            raise Refused("`stop` takes no argument")
        return None
    if op == "playbook":
        if len(rest) > 1 or (rest and rest[0].startswith("-")):
            raise Refused("`playbook` takes at most one playbook id")
        return None
    if op == "end":
        if len(rest) != 1 or not HTML.search(rest[0]):
            raise Refused("`end` takes exactly one .html page")
        return None
    if op == "poll":
        if not rest or not (len(rest) == 1 or (len(rest) == 3 and rest[1] == "--agent-reply")):
            raise Refused("`poll` takes one .html page and an optional `--agent-reply <message>`")
        return page(rest[0])
    if op.startswith("-"):
        raise Refused(f"`{op}` is not an operation this wrapper runs")
    if rest not in ([], ["--no-open"], ["--reopen"]):
        raise Refused("a render takes one .html page and at most one of `--no-open` or `--reopen`")
    return page(op)


def page(target: str) -> str:
    if not HTML.search(target):
        raise Refused(f"{target} is not an .html page")
    if not os.path.isfile(target):
        raise Refused(f"{target} does not exist")
    return target


def npm_script(shim: Path) -> Path | None:
    """The JavaScript entry an npm `.cmd` shim runs, from the package's own `bin` field."""
    package = shim.parent / "node_modules" / "lavish-axi"
    try:
        meta = json.loads((package / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    entry = meta.get("bin")
    entry = entry if isinstance(entry, str) else (entry or {}).get("lavish-axi") if isinstance(entry, dict) else None
    script = package / entry if isinstance(entry, str) else None
    return script if script is not None and script.is_file() else None


def upstream(args: list[str]) -> list[str] | None:
    """The argument vector that runs the installed `lavish-axi` with `args`, or None when it is absent."""
    found = shutil.which("lavish-axi")
    if not found:
        return None
    if os.name == "nt" and found.lower().endswith((".cmd", ".bat")):
        script = npm_script(Path(found))
        local = Path(found).with_name("node.exe")
        node = str(local) if local.is_file() else shutil.which("node")
        if script is not None and node:
            return [node, str(script), *args]
        # Batch files re-parse their arguments through cmd.exe; pass only plain ones that way.
        if not all(CMD_SAFE.match(arg) for arg in args):
            raise Refused("lavish-axi resolves to a batch shim with no readable npm package; "
                          "an argument holds characters cmd.exe would re-parse. Reinstall per /afk:setup.")
    return [found, *args]


def bind_child_lifetime() -> None:
    """Windows: put this process in a kill-on-close job, so a stopped wrapper takes its child down."""
    try:
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        job = kernel.CreateJobObjectW(None, None)
        if not job:
            return

        class Limits(ctypes.Structure):
            _fields_ = [("a", ctypes.c_int64), ("b", ctypes.c_int64), ("flags", wintypes.DWORD),
                        ("c", ctypes.c_size_t), ("d", ctypes.c_size_t), ("e", wintypes.DWORD),
                        ("f", ctypes.c_size_t), ("g", wintypes.DWORD), ("h", wintypes.DWORD),
                        ("io", ctypes.c_uint64 * 6), ("i", ctypes.c_size_t), ("j", ctypes.c_size_t),
                        ("k", ctypes.c_size_t), ("l", ctypes.c_size_t)]

        limits = Limits(flags=0x2000)  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess())
    except Exception:
        pass  # best effort: the upstream still runs, only its lifetime is unbound


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        target = plan(args)
        command = upstream(args)
    except Refused as problem:
        sys.stderr.write(f"lavish_show: refused: {problem}\n")
        return 64
    if command is None:
        sys.stderr.write("lavish_show: lavish-axi is not on PATH; run /afk:setup (register N4)\n")
        return 127
    if target is not None:
        try:
            inject.inject_file(target, cwd=os.getcwd())
        except inject.InjectError as problem:
            sys.stderr.write(f"lavish_show: {problem}\n")
            return 65
    sys.stdout.flush()
    sys.stderr.flush()
    if argv is None and os.name != "nt":
        os.execv(command[0], command)
    if argv is None:
        bind_child_lifetime()
    try:
        return subprocess.call(command)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
