"""Launch a shell hook handler through a POSIX shell the harness cannot mistake.

A harness spawns a hook command through whatever shell it prefers, so the
command string must be valid in both a POSIX shell and PowerShell, and a bare
`bash` is not a reliable name on Windows: it resolves to the WSL stub in the
system directory on many machines, which cannot run these handlers. This
launcher is the one command every hook entry uses. It resolves the handler
path, locates a real Git Bash, forwards stdin, stdout, stderr and the exit
code, and stays silent when an optional handler is absent.

Usage:
    afk-python run-hook.py [--soft] [--deadline <seconds>] plugin <handler.sh> [args...]
    afk-python run-hook.py [--soft] [--deadline <seconds>] repo-list <event>

    plugin     handler under this plugin's own hooks/ directory
    repo-list  every repository-owned handler the consuming repository declares
               for <event> in `.afk/hooks.json`; absent file or repository
               exits 0
    --soft     always exit 0 (advisory handlers that must never block a turn)
    --deadline one aggregate budget for the whole invocation, below the harness
               timeout. Past it the handler's whole process tree is killed: a
               plugin handler exits 0 with a one-line notice (verdict unknown,
               never a block); a repository handler fails closed as before.
               Handlers read the kill time as `AFK_HOOK_DEADLINE` (Unix epoch
               seconds), so each can fit its own waits inside the budget.

`.afk/hooks.json` is a JSON array of objects, each with `event`
(SessionStart|PreToolUse|PostToolUse|PostCompact|Stop|WorktreeCreated), `matcher` (a regular
expression matched against
the envelope tool name, or `*`), `timeout` (seconds), and `script` (a path
relative to the repository root). A script path that resolves outside the
repository root is refused. Handlers run in declaration order, each receives the
original stdin envelope, and `AFK_PLUGIN_ROOT` names this plugin's root.

`WorktreeCreated` runs once per new worktree, after its files are copied and its
build is set up, from the worktree folder. The envelope is `{"worktree", "branch"}`;
`AFK_WORKTREE_PATH` and `AFK_WORKTREE_BRANCH` carry the same two values. A script
that exits non-zero, is missing, or resolves outside the repository is warned about
on stderr, by name, and never removes the worktree.

A handler a repository declares but this checkout cannot run — the script is
missing, the matcher is not a regular expression, the manifest does not parse —
is a configuration error, never a silent skip. A handler that returns no verdict
inside its timeout is reported as a timeout, never as a configuration error. On
Stop and PreToolUse either blocks the turn with the decision object a failed gate
emits, so a gate cannot disappear by being misdeclared or by being slow. A Stop
or PreToolUse handler that exits non-zero, or prints a refusal object, is a
refusal: its own stdout and exit code are never passed through. The launcher
gathers every refusal and emits one verdict in the provider's block shape
(PreToolUse: the deny JSON at exit 0). With no POSIX shell the same events
block too. On the remaining events it writes the reason to stderr.

A handler that fails without refusing (any exit but 0 or 2, no refusal object) or runs
out of time gets one stderr line from the launcher, `[afk] <handler> (<event>) failed: ...`,
after its own stderr; so does a fault in the launcher itself. Where the provider declaration
says the harness drops stderr on a failed exit, a non-soft failure exits 0 with that line in
`systemMessage` instead (contract: CAPABILITIES.md "Hook failures").

Two bails exit 0 before any shell lookup: `repo-list` when the repository declares no
handler for the event, and `plugin` for a handler its provider's declaration
(`hooks/lib/providers/<name>.json`) makes a no-op (POLICY_NOOP). Before a handler
starts, `AFK_PYTHON` must name this interpreter, the `afk-python` entry: handlers
run `"$AFK_PYTHON"`. Without it no handler runs, the same as without a shell.

Overrides: AFK_BASH, then GIT_BASH, then a Git-relative lookup, then the known
install locations, then PATH excluding the Windows system directory.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPO_HOOKS_MANIFEST = ".afk/hooks.json"
EVENTS = {"SessionStart", "PreToolUse", "PostToolUse", "PostCompact", "Stop", "WorktreeCreated"}
# The events whose whole point is to stop a turn. A handler that cannot run is
# a missing verdict on these, so the launcher answers for it. PostToolUse and
# PostCompact carry context injections, never a block, so they only warn.
BLOCKING_EVENTS = {"Stop", "PreToolUse"}


# ---- the process-tree primitive: every handler this launcher starts runs through
# run_tree, so a deadline or a killed launcher takes the handler's whole tree with it.
#
# Windows: the launcher joins a kill-on-close Job Object (the harness killing the
# launcher closes it), and each handler gets a nested job of its own, so a deadline
# ends that tree and the launcher survives to answer. Neither job allows breakaway:
# MSYS bash starts its children with the breakaway flag, so a job that allowed it
# would let every bash descendant leave. A handler that must leave a deliberately
# detached helper behind (DETACHES_HELPERS) runs with no job and, past a deadline,
# is ended by walking its parent chain.
# POSIX: each handler is a session leader; signals, deadlines and a normal exit kill its group.
_DEADLINE_AT: float | None = None
_DEADLINE_S = 0.0
_ACTIVE: list[subprocess.Popen] = []
_JOBS: dict = {}
_KILL_ON_CLOSE = 0x2000
DETACHES_HELPERS = {"worktree-remove.sh"}
_CREATE_SUSPENDED = 0x00000004


def budget_left() -> float | None:
    return None if _DEADLINE_AT is None else max(_DEADLINE_AT - time.monotonic(), 0.0)


def _job_api():
    if "api" in _JOBS:
        return _JOBS["api"]
    api = None
    try:
        import ctypes
        from ctypes import wintypes

        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class Extended(ctypes.Structure):
            _fields_ = [("Basic", Basic), ("Io", ctypes.c_uint64 * 6), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        ntdll = ctypes.WinDLL("ntdll")
        ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
        api = (ctypes, kernel, ntdll, Extended)
    except Exception:
        api = None
    _JOBS["api"] = api
    return api


def _make_job():
    api = _job_api()
    if api is None:
        return None
    ctypes, kernel, _ntdll, Extended = api
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        return None
    info = Extended()
    info.Basic.LimitFlags = _KILL_ON_CLOSE
    if not kernel.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        kernel.CloseHandle(job)
        return None
    return job


def enter_launcher_job() -> None:
    """Windows: put this launcher in a kill-on-close job; say so when that fails."""
    if os.name != "nt" or "launcher" in _JOBS:
        return
    job = _make_job()
    api = _job_api()
    if job is not None and api is not None:
        _ctypes, kernel, _ntdll, _ext = api
        if kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess()):
            _JOBS["launcher"] = job
            return
    _JOBS["launcher"] = None
    sys.stderr.write("[afk] run-hook.py: tree cleanup degraded (no job object for the launcher).\n")


def _spawn(args: list[str], jobbed: bool, **kwargs) -> tuple[subprocess.Popen, object]:
    """Start `args` as the root of a killable tree; the second value is its Windows job, if any."""
    if os.name != "nt":
        return subprocess.Popen(args, start_new_session=True, **kwargs), None
    job = _make_job() if jobbed else None
    if job is None:
        return subprocess.Popen(args, **kwargs), None
    proc = subprocess.Popen(args, creationflags=_CREATE_SUSPENDED, **kwargs)
    _ctypes, kernel, ntdll, _ext = _job_api()
    owned = bool(kernel.AssignProcessToJobObject(job, int(proc._handle)))
    ntdll.NtResumeProcess(int(proc._handle))
    if owned:
        return proc, job
    kernel.CloseHandle(job)
    return proc, None


def _kill_group(proc: subprocess.Popen, job: object) -> None:
    if os.name == "nt":
        if job is not None:
            _ctypes, kernel, _ntdll, _ext = _job_api()
            kernel.TerminateJobObject(job, 1)
        else:
            sys.stderr.write("[afk] run-hook.py: tree cleanup degraded (no job object for the handler).\n")
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=20)
        try:
            proc.kill()
        except OSError:
            pass
        return
    for sig, grace in ((signal.SIGTERM, 1.0), (signal.SIGKILL, 0.0)):
        try:
            os.killpg(proc.pid, sig)
        except OSError:
            return
        stop = time.monotonic() + grace
        while time.monotonic() < stop:
            try:
                os.killpg(proc.pid, 0)
            except OSError:
                return
            time.sleep(0.05)


def _drain(proc: subprocess.Popen) -> tuple[bytes | None, bytes | None]:
    """Collect what a killed tree left in the pipes without ever waiting on a survivor."""
    try:
        return proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            try:
                if pipe:
                    pipe.close()
            except OSError:
                pass
        return None, None


def run_tree(args: list[str], env: dict[str, str], *, input: bytes | None = None,
             capture: bool = False, timeout: float | None = None,
             jobbed: bool = True, outputs: tuple | None = None) -> subprocess.CompletedProcess:
    """`subprocess.run` for a handler: the whole tree dies on timeout, error or signal.

    `outputs` is a (stdout, stderr) pair of files: unlike a pipe, a file never waits on a background child.
    """
    pipes = subprocess.PIPE if capture else None
    out_to, err_to = outputs if outputs is not None else (pipes, pipes)
    proc, job = _spawn(args, jobbed, env=env, stdin=subprocess.PIPE if input is not None else None,
                       stdout=out_to, stderr=err_to)
    _ACTIVE.append(proc)
    try:
        try:
            out, err = proc.communicate(input=input, timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_group(proc, job)
            out, err = _drain(proc)
            raise subprocess.TimeoutExpired(args, timeout, output=out, stderr=err)
        except BaseException:
            _kill_group(proc, job)
            raise
        return subprocess.CompletedProcess(args, proc.returncode, out, err)
    finally:
        _ACTIVE.remove(proc)
        if os.name != "nt" and jobbed:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        if job is not None:
            _ctypes, kernel, _ntdll, _ext = _job_api()
            kernel.CloseHandle(job)


def install_signal_handlers() -> None:
    """POSIX: a signal to the launcher ends every handler group first."""
    if os.name == "nt":
        return

    def stop(signum, _frame):
        for proc in list(_ACTIVE):
            _kill_group(proc, None)
        os._exit(128 + signum)

    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, stop)


def repo_root(env: dict[str, str]) -> Path | None:
    return git_toplevel(env)[0]


def git_toplevel(env: dict[str, str]) -> tuple[Path | None, bool]:
    """The working tree's Git root, and whether Git answered: a root, or "not a git repository".

    Like every plugin gate; CLAUDE_PROJECT_DIR names the launch checkout, which can differ.
    """

    # Windows resolves the executable name against this process's PATH, not the
    # PATH being handed to the child, so name git absolutely when it is only on
    # the shell's own PATH.
    git = shutil.which("git", path=env.get("PATH")) or "git"
    try:
        out = subprocess.run(
            [git, "-C", os.getcwd(), "rev-parse", "--show-toplevel"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=20, env={**env, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return None, False
    top = out.stdout.strip()
    if out.returncode == 0 and top:
        return Path(top), True
    return None, "not a git repository" in out.stderr


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except (ValueError, OSError):
        return False
    return True


def is_wsl_stub(candidate: Path) -> bool:
    """The Windows system directory ships a WSL launcher named bash.exe."""
    return is_under(candidate, Path(os.environ.get("SystemRoot", r"C:\Windows")))


def git_relative_bash() -> Path | None:
    """Git for Windows ships bash.exe in <git>/bin, beside its exec-path tree."""
    try:
        out = subprocess.run(
            ["git", "--exec-path"], capture_output=True, encoding="utf-8", errors="replace", timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    node = Path(out.stdout.strip())
    for parent in [node] + list(node.parents):
        for name in ("bash.exe", "bash"):
            candidate = parent / "bin" / name
            if candidate.is_file():
                return candidate
    return None


def find_bash() -> Path | None:
    for variable in ("AFK_BASH", "GIT_BASH"):
        named = os.environ.get(variable)
        if named and Path(named).is_file():
            return Path(named)
    if os.name != "nt":
        found = shutil.which("bash")
        return Path(found) if found else None

    from_git = git_relative_bash()
    if from_git:
        return from_git

    bases = [
        os.environ.get("ProgramW6432", r"C:\Program Files"),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
    ]
    for base in bases:
        if not base:
            continue
        candidate = Path(base) / "Git" / "bin" / "bash.exe"
        if candidate.is_file():
            return candidate

    found = shutil.which("bash")
    if found and not is_wsl_stub(Path(found)):
        return Path(found)
    return None


def hook_bash() -> Path | None:
    """find_bash(), past Git for Windows' <git>/bin/bash.exe redirector: one process start fewer
    per handler. Start it only with shell_env(), which sets what the redirector would have."""
    bash = find_bash()
    if bash is not None and os.name == "nt" and bash.parent.name.lower() == "bin":
        direct = bash.parent.parent / "usr" / "bin" / bash.name
        if direct.is_file():
            return direct
    return bash


def shell_env(bash: Path, base: dict[str, str] | None = None) -> dict[str, str]:
    """Handlers call grep, sed, git and friends.

    A parent PATH that never had a POSIX shell on it has none of them either, so
    put the shell's own toolchain in front of whatever the harness passed down
    (`base`, default this process's environment).
    """
    env = dict(os.environ if base is None else base)
    if os.name != "nt":
        return env
    home = bash.resolve().parent
    if home.name.lower() == "bin" and home.parent.name.lower() == "usr":
        return redirector_env(home.parent.parent, env)
    root = home.parent
    extra = [str(root / "bin"), str(root / "usr" / "bin"), str(root / "mingw64" / "bin")]
    present = {part.lower() for part in env.get("PATH", "").split(os.pathsep)}
    missing = [part for part in extra if Path(part).is_dir() and part.lower() not in present]
    if missing:
        env["PATH"] = os.pathsep.join(missing + [env.get("PATH", "")]).rstrip(os.pathsep)
    return env


def redirector_env(root: Path, env: dict[str, str]) -> dict[str, str]:
    """Set what <git>/bin/bash.exe sets before it starts <git>/usr/bin/bash.exe:
    setup_environment() in git-for-windows/MINGW-packages mingw-w64-git/git-wrapper.c."""
    msys = next((name for name in ("mingw64", "ucrt64", "clangarm64", "mingw32")
                 if (root / name).is_dir()), "mingw64")
    env["MSYSTEM"] = msys.upper()
    env["EXEPATH"] = str(root / "bin")
    env.setdefault("PLINK_PROTOCOL", "ssh")
    if not env.get("HOME"):
        drive_path = env.get("HOMEDRIVE", "") + env.get("HOMEPATH", "")
        system32 = Path(env.get("SystemRoot", r"C:\Windows"), "system32")
        if env.get("HOMEPATH") and Path(drive_path).is_dir() and not is_under(Path(drive_path), system32):
            env["HOME"] = drive_path
        elif env.get("USERPROFILE"):
            env["HOME"] = env["USERPROFILE"]
    front = [str(root / msys / "bin"), str(root / "usr" / "bin")]
    if env.get("HOME"):  # as spelled: Path() would turn /c/x into \c\x, which bash reads as /c/c/x
        front.append(env["HOME"].rstrip("/\\") + "/bin")
    env["PATH"] = os.pathsep.join(front + [env.get("PATH", "")]).rstrip(os.pathsep)
    return env


def load_lib(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Plugin handlers a provider declaration makes a no-op. `never` injects nothing, so no
# session marker exists for the SessionStart/PostCompact reset to remove either.
POLICY_NOOP = {
    "nested-steering.sh": lambda facts: facts.get("nested_inject_mode", "never") == "never",
    "agents-md-config-check.sh": lambda facts: facts.get("instruction_files_setting") is not True,
}


_FACTS: list[dict | None] = []


def provider_facts() -> dict | None:
    """This harness's provider declaration, loaded once; None when it cannot be read."""
    if not _FACTS:
        try:
            _FACTS.append(load_lib("afk_provider_facts", PLUGIN_ROOT / "hooks" / "lib" / "provider_facts.py").facts())
        except Exception:
            _FACTS.append(None)
    return _FACTS[0]


def policy_noop(handler: str) -> bool:
    test = POLICY_NOOP.get(handler)
    facts = provider_facts() if test is not None else None
    return facts is not None and test(facts)


# ---- a failed handler names itself: CAPABILITIES.md "Hook failures" owns the contract,
# hooks/lib/hook_failure.py the line. Loaded only on a failure.
_ENVELOPE: list[bytes | None] = []
_WHO = {"handler": "run-hook.py", "event": None, "soft": False}


def envelope() -> bytes | None:
    """The harness's stdin envelope, read once; None when stdin is a terminal or absent."""
    if not _ENVELOPE:
        stream = sys.stdin
        _ENVELOPE.append(None if stream is None or stream.isatty() else stream.buffer.read())
    return _ENVELOPE[0]


def envelope_field(name: str) -> str:
    try:
        said = json.loads((envelope() or b"").decode("utf-8", "replace"))
    except (ValueError, OSError):
        return ""
    return str(said.get(name) or "") if isinstance(said, dict) else ""


def failure_text(handler: str, event: str | None, outcome: str, said: bytes | str | None) -> str:
    try:
        return load_lib("afk_hook_failure", PLUGIN_ROOT / "hooks" / "lib" / "hook_failure.py").line(
            handler, event, outcome, said)
    except Exception:  # a broken install still names the handler
        return f"[afk] {handler} ({event or 'unknown event'}) failed: {outcome}"


def failed(handler: str, event: str | None, outcome: str, said: bytes | str | None) -> str:
    text = failure_text(handler, event, outcome, said)
    sys.stderr.write(text + "\n")
    sys.stderr.flush()
    return text


def answer(lines: list[str], outputs: list[bytes]) -> bool:
    """Where the provider drops stderr on a failed exit, carry `lines` in one stdout document at exit 0.

    True when it did: the caller then exits 0. `outputs` are the documents that document joins.
    """
    try:
        lib = load_lib("afk_hook_failure", PLUGIN_ROOT / "hooks" / "lib" / "hook_failure.py")
        wanted = bool(lines) and lib.system_message(provider_facts() or {})
    except Exception:
        return False
    if wanted:
        sys.stdout.write(merge_allowed([*outputs, lib.notice(lines).encode("utf-8")]) + "\n")
        sys.stdout.flush()
    return wanted


def write_raw(stream, data: bytes | None) -> None:
    if data:
        stream.flush()
        stream.buffer.write(data)
        stream.buffer.flush()


def run_captured(args: list[str], env: dict[str, str], *, input: bytes | None, timeout: float | None,
                 jobbed: bool = True) -> tuple[int | None, bytes, bytes]:
    """A handler's exit code (None past `timeout`), stdout and stderr, both held in files."""
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            code = run_tree(args, env, input=input, timeout=timeout, jobbed=jobbed, outputs=(out, err)).returncode
        except subprocess.TimeoutExpired:
            code = None
        out.seek(0)
        err.seek(0)
        return code, out.read(), err.read()


def plugin_verdict(handler: str, code: int | None, out: bytes, err: bytes, soft: bool) -> int:
    """Pass a plugin handler's streams and code through; a failure or a timeout also names itself."""
    write_raw(sys.stderr, err)
    event = envelope_field("hook_event_name") or None
    if code is None:  # partial stdout is dropped: a verdict cut off midway is no verdict
        text = failed(handler, event, f"timed out after {_DEADLINE_S:g}s, stopped, verdict unknown", err)
        if not soft:
            answer([text], [])
        return 0
    if code in (0, 2) or denial(event or "", out) is not None:
        write_raw(sys.stdout, out)
        return 0 if soft else code
    text = failed(handler, event, f"exit {code}", err)
    if not soft and answer([text], []):
        return 0  # the handler's own stdout is dropped, as the harness drops it on a failed exit
    write_raw(sys.stdout, out)
    return 0 if soft else code


def runtime_fault() -> str | None:
    """Why `AFK_PYTHON` does not name this interpreter, or None when it does."""
    named, here = os.environ.get("AFK_PYTHON"), sys.executable
    if not named:
        return f"AFK_PYTHON is not set, so {here} is not the afk-python entry; run /afk:setup"
    if not os.path.isabs(named):
        # Handlers run "$AFK_PYTHON" through their own PATH, which can name another file.
        return f"AFK_PYTHON names {named}, not an absolute path; run /afk:setup"
    if os.path.normcase(os.path.abspath(named)) == os.path.normcase(os.path.abspath(here)):
        return None
    try:
        if os.name == "nt" and os.path.samefile(named, here):
            return None
    except OSError:
        pass
    return f"AFK_PYTHON names {named}, not this interpreter {here}; run /afk:setup"


def manifest_path(root: Path) -> Path:
    """`.afk/hooks.json` unless the repository's config names another path.

    The configuration reader is the plugin's own module, so this stays one
    import rather than a subprocess on the hook path.
    """
    try:
        module = load_lib("afk_config", PLUGIN_ROOT / "scripts" / "afk-config.py")
        named = module.get(module.load(root), "repo-hooks")
    except Exception:
        named = None
    if not isinstance(named, str) or not named:
        named = REPO_HOOKS_MANIFEST
    candidate = (root / named).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return root / REPO_HOOKS_MANIFEST
    return candidate


def repo_entries(root: Path, event: str) -> tuple[list[dict], list[str]]:
    """Handlers declared for one event, in declaration order, and any faults.

    A manifest that does not parse yields no handlers AND one fault: the
    repository asked for gates and none of them can run, which is the opposite
    of "nothing was declared".
    """
    manifest = manifest_path(root)
    if not manifest.is_file():
        return [], []
    try:
        declared = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        return [], [f"{REPO_HOOKS_MANIFEST}: {problem}"]
    if not isinstance(declared, list):
        return [], [f"{REPO_HOOKS_MANIFEST}: expected a JSON array"]
    entries: list[dict] = []
    faults: list[str] = []
    for position, entry in enumerate(declared):
        if not isinstance(entry, dict):
            faults.append(f"{REPO_HOOKS_MANIFEST}: entry {position} is not an object")
            continue
        if entry.get("event") == event:
            entries.append(entry)
    return entries, faults


def matcher_fault(matcher: object) -> str | None:
    """Why this matcher can never be applied, or None when it can."""
    if matcher is None or (isinstance(matcher, str) and matcher in ("", "*")):
        return None
    if not isinstance(matcher, str):
        return f"matcher is not a string: {matcher!r}"
    try:
        re.compile(matcher)
    except re.error as problem:
        return f"matcher is not a regular expression: {matcher!r} ({problem})"
    return None


def matches(matcher: object, tool: str) -> bool:
    if not isinstance(matcher, str) or matcher in ("", "*"):
        return True
    try:
        return re.fullmatch(matcher, tool) is not None
    except re.error:
        return False


def resolved_script(root: Path, entry: dict) -> tuple[Path | None, str | None]:
    """The declared script, or why this checkout cannot run it."""
    named = entry.get("script")
    if not isinstance(named, str) or not named:
        return None, "no script path is declared"
    candidate = (root / named).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None, f"script escapes the repository root: {named}"
    if not candidate.is_file():
        return None, f"script is missing: {named}"
    return candidate, None


def denial(event: str, stdout: bytes) -> str | None:
    """The reason in a refusal object a handler printed, or None when it printed none."""
    try:
        said = json.loads(stdout.decode("utf-8", "replace"))
    except ValueError:
        return None
    if not isinstance(said, dict):
        return None
    inner = said.get("hookSpecificOutput")
    if event == "PreToolUse" and isinstance(inner, dict) and inner.get("permissionDecision") == "deny":
        return str(inner.get("permissionDecisionReason") or "denied")
    if said.get("decision") in ("block", "deny"):
        return str(said.get("reason") or "blocked")
    return None


DECISION_RANK = {"allow": 0, "ask": 1}


def merge_allowed(outputs: list[bytes]) -> str:
    """One JSON document from every handler's allowed output.

    A harness reads one document; two concatenated ones lose both. `additionalContext` and
    `systemMessage` are joined by newlines. `permissionDecision` takes the strictest answer
    (ask over allow) with that handler's reason, so one handler's prompt for a human is never
    turned into an approval by another. Output that is not a JSON object goes to stderr.
    """
    merged: dict = {}
    context: list[str] = []
    messages: list[str] = []
    decision: tuple[int, str, str | None] | None = None
    for out in outputs:
        text = out.decode("utf-8", "replace").strip()
        try:
            said = json.loads(text)
        except ValueError:
            said = None
        if not isinstance(said, dict):
            if text:
                sys.stderr.write(text + "\n")
            continue
        inner = said.get("hookSpecificOutput")
        if isinstance(inner, dict):
            if isinstance(inner.get("additionalContext"), str):
                context.append(inner["additionalContext"])
            asked = inner.get("permissionDecision")
            if asked in DECISION_RANK and (decision is None or DECISION_RANK[asked] > decision[0]):
                decision = (DECISION_RANK[asked], asked, inner.get("permissionDecisionReason"))
        if isinstance(said.get("systemMessage"), str):
            messages.append(said["systemMessage"])
        for key, value in said.items():
            if key == "hookSpecificOutput" and isinstance(value, dict):
                merged.setdefault(key, {}).update(
                    {k: v for k, v in value.items()
                     if k not in ("additionalContext", "permissionDecision", "permissionDecisionReason")})
            elif key not in ("additional_context", "systemMessage"):
                merged[key] = value
    if context:
        joined = "\n".join(context)
        merged.setdefault("hookSpecificOutput", {})["additionalContext"] = joined
        merged["additional_context"] = joined
    if decision is not None:
        body = merged.setdefault("hookSpecificOutput", {})
        body["permissionDecision"] = decision[1]
        if decision[2] is not None:
            body["permissionDecisionReason"] = decision[2]
    if messages:
        merged["systemMessage"] = "\n".join(messages)
    return json.dumps(merged) if merged else ""


def block_without_shell(event: str, why: str) -> int:
    """No handler can run (`why`): a repository gate that matches this call still blocks it."""
    env = dict(os.environ)
    root = repo_root(env)
    entries, faults = repo_entries(root, event) if root is not None else ([], [])
    tool = envelope_field("tool_name")
    for entry in entries:
        if matcher_fault(entry.get("matcher")) or matches(entry.get("matcher"), tool):
            faults.append(f"{why}: cannot run {entry.get('script')}")
    return block(event, faults, None, env) if faults else 0


def block(event: str, faults: list[str], bash: Path | None, env: dict[str, str],
          refused: list[str] | None = None, timeouts: list[str] | None = None) -> int:
    """Answer for the handlers that could not run or refused, the way a gate answers.

    The decision travels the same path a failed gate travels — the provider
    library owns the shape of a verdict and the exit code its harness reads one
    from — so a broken gate blocks exactly like a failing one.
    """
    parts = []
    if faults:
        listed = "\n".join(f"  - {fault}" for fault in faults)
        parts.append(
            f"afk: this repository declares {event} handlers this checkout cannot run, "
            "so the gates they carry did not judge this turn:\n"
            f"{listed}\n"
            f"Fix {REPO_HOOKS_MANIFEST}, or remove the entries that no longer apply."
        )
    if timeouts:
        listed = "\n".join(f"  - {item}" for item in timeouts)
        parts.append(
            f"afk: this repository's {event} handlers timed out, "
            "so the gates they carry did not judge this turn:\n"
            f"{listed}\n"
            f"The timeout counts process start-up: raise it in {REPO_HOOKS_MANIFEST}, or start fewer processes."
        )
    if refused:
        listed = "\n".join(f"  - {item}" for item in refused)
        parts.append(f"afk: this repository's {event} handlers refused:\n{listed}")
    reason = "\n".join(parts)
    library = PLUGIN_ROOT / "hooks" / "lib" / "provider.sh"
    # The PreToolUse deny parses to afk_emit_deny's object on every provider (semantic JSON
    # parity; bytes may differ), so only a Stop verdict, whose exit code varies, needs the shell.
    if event == "Stop" and bash is not None and library.is_file():
        snippet = '. "$1" || exit 70\nafk_emit_stop_block "$2"; exit "$(afk_stop_block_code)"\n'
        try:
            completed = run_tree(
                [str(bash), "-c", snippet, "run-hook", str(library), reason],
                env, timeout=10 if _DEADLINE_AT is not None else 60,
            )
            if completed.returncode != 70:
                return completed.returncode
        except (OSError, subprocess.SubprocessError):
            pass
    # No shell, or a provider library this checkout cannot read: say the same
    # thing in the shapes both harnesses read, and use the documented default.
    sys.stderr.write(reason + "\n")
    if event == "Stop":
        sys.stdout.write(json.dumps({"decision": "block", "reason": reason}) + "\n")
        return 0  # both adapters name 0 as the Stop block code: the decision object is the verdict
    sys.stdout.write(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}) + "\n")
    return 0


# Handlers that record who launched them. A walk up the process tree from inside bash
# loses the chain at the first bash-to-bash hop, so the first native process resolves it.
OWNER_HANDLERS = {"worktree-create.sh"}


def owner_env() -> dict[str, str]:
    """`AFK_WORKTREE_OWNER=<pid>:<creation time>` of the harness above this launcher, or {}."""
    try:
        found = load_lib("afk_worktree_owner", PLUGIN_ROOT / "scripts" / "worktree_owner.py").find_owner()
    except Exception:
        return {}
    return {"AFK_WORKTREE_OWNER": f"{found['pid']}:{found['ctime']}"} if found else {}


def main(argv: list[str]) -> int:
    global _DEADLINE_AT, _DEADLINE_S
    _ENVELOPE.clear()
    _FACTS.clear()
    for stream in (sys.stdout, sys.stderr):  # the harness reads UTF-8; a code page cannot encode all text
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    soft = False
    budget = None
    while argv and argv[0] in ("--soft", "--deadline"):
        if argv[0] == "--soft":
            soft = True
            argv = argv[1:]
            continue
        try:
            budget = float(argv[1])
        except (IndexError, ValueError):
            budget = -1.0
        if budget <= 0:
            sys.stderr.write("run-hook.py: --deadline needs a positive number of seconds\n")
            return 0 if soft else 2
        argv = argv[2:]
    if budget is not None:
        _DEADLINE_S = budget
        _DEADLINE_AT = time.monotonic() + budget
    if len(argv) < 2 or argv[0] not in {"plugin", "repo-list"}:
        sys.stderr.write(
            "run-hook.py: usage: run-hook.py [--soft] [--deadline <seconds>] plugin <handler.sh> [args...]\n"
            "run-hook.py: usage: run-hook.py [--soft] [--deadline <seconds>] repo-list <event>\n"
        )
        return 0 if soft else 2
    _WHO.update(handler=argv[1] if argv[0] == "plugin" else "repo-list",
                event=argv[1] if argv[0] == "repo-list" else None, soft=soft)

    if argv[0] == "repo-list":
        if argv[1] not in EVENTS:
            sys.stderr.write(f"run-hook.py: unknown event: {argv[1]}\n")
            return 0 if soft else 2
        # Manifest first: no declared handler needs no shell, no job and no second git call.
        # Only Git's own answer proves "nothing declared"; a failed lookup retries on the shell's PATH.
        root, answered = git_toplevel(dict(os.environ)) if shutil.which("git") else (None, False)
        if answered and (root is None or repo_entries(root, argv[1]) == ([], [])):
            return 0
    elif policy_noop(argv[1]):
        return 0

    why = runtime_fault()
    bash = hook_bash() if why is None else None
    if bash is None:
        why = why or "no POSIX shell found. Install Git Bash, or point AFK_BASH at a bash executable"
        sys.stderr.write(f"run-hook.py: {argv[1]}: {why}.\n")
        if soft:
            return 0
        if argv[0] == "repo-list" and argv[1] in BLOCKING_EVENTS:
            return block_without_shell(argv[1], why)
        text = failed(_WHO["handler"], _WHO["event"] or envelope_field("hook_event_name") or None, "exit 1", why)
        return 0 if answer([text], []) else 1
    # The shell's own toolchain sits on this PATH, so git resolves here even
    # when the harness handed down a PATH carrying neither.
    env = shell_env(bash)
    env["AFK_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    if _DEADLINE_AT is not None:
        env["AFK_HOOK_DEADLINE"] = f"{time.time() + (budget_left() or 0.0):.3f}"
    if argv[1] not in DETACHES_HELPERS:
        enter_launcher_job()
    install_signal_handlers()

    if argv[0] == "plugin":
        script = PLUGIN_ROOT / "hooks" / argv[1]
        if not script.is_file():
            # An optional handler this checkout does not ship is not a failure.
            return 0
        if argv[1] in OWNER_HANDLERS:
            env.update(owner_env())
        code, out, err = run_captured([str(bash), str(script), *argv[2:]], env, input=envelope(),
                                      timeout=budget_left(), jobbed=argv[1] not in DETACHES_HELPERS)
        return plugin_verdict(argv[1], code, out, err, soft)

    event = argv[1]
    root = repo_root(env)
    if root is None:
        return 0
    entries, faults = repo_entries(root, event)
    if not entries and not faults:
        return 0

    given = envelope() or b""
    tool = envelope_field("tool_name")

    failure = 0
    refused: list[str] = []
    timeouts: list[str] = []
    allowed: list[bytes] = []
    passed: list[bytes] = []  # non-blocking stdout, verbatim and in order
    notices: list[str] = []
    blocking = event in BLOCKING_EVENTS and not soft
    for entry in entries:
        named = entry.get("script")
        fault = matcher_fault(entry.get("matcher"))
        if fault:
            faults.append(f"{named}: {fault}")
            continue
        if not matches(entry.get("matcher"), tool):
            continue
        script, fault = resolved_script(root, entry)
        if script is None:
            faults.append(f"{REPO_HOOKS_MANIFEST}: {fault}")
            continue
        timeout = entry.get("timeout")
        timeout = float(timeout) if isinstance(timeout, (int, float)) else None
        left = budget_left()
        if left is not None:
            timeout = left if timeout is None else min(timeout, left)
        try:
            if not blocking:
                code, out, err = run_captured([str(bash), str(script)], env, input=given, timeout=timeout)
            else:
                completed = run_tree(
                    [str(bash), str(script)], env, input=given, timeout=timeout, capture=True,
                )
        except subprocess.TimeoutExpired:
            timeouts.append(f"{named}: no verdict within {timeout:g} seconds")
            continue
        except OSError as problem:
            faults.append(f"{named}: {problem}")
            continue
        if blocking:
            said = (completed.stderr or b"").decode("utf-8", "replace").strip()
            reason = denial(event, completed.stdout or b"")
            if reason is None and completed.returncode not in (0, 2):
                # A crash, not a refusal: the item names the handler, as a failed handler does.
                refused.append(failure_text(named, event, f"exit {completed.returncode}", said))
                continue
            if reason is not None or completed.returncode:
                # One verdict leaves this launcher, in the provider's shape: never a handler's own.
                refused.append(reason or said or f"{named} exited {completed.returncode}")
                continue
            if completed.stdout:
                allowed.append(completed.stdout)
            if said:
                sys.stderr.write(said + "\n")
            continue
        write_raw(sys.stderr, err)
        if code is None:
            notices.append(failed(named, event, f"timed out after {timeout:g}s, verdict unknown", err))
            continue
        if code not in (0, 2):
            notices.append(failed(named, event, f"exit {code}", err))
        else:
            allowed.append(out)
        passed.append(out)
        if code and event == "WorktreeCreated":
            faults.append(f"{named}: exited {code}; the worktree is kept")
            continue
        if code and not failure:
            failure = code

    for fault in faults + timeouts:
        sys.stderr.write(f"run-hook.py: {fault}\n")
    if (faults or refused or timeouts) and blocking:
        return block(event, faults, bash, env, refused, timeouts)
    if not blocking:
        if not soft and answer(notices, allowed):
            return 0
        for out in passed:
            write_raw(sys.stdout, out)
        return 0 if soft else failure
    merged = merge_allowed(allowed)  # context printed while nothing refused: one document
    if merged:
        sys.stdout.write(merged + "\n")
        sys.stdout.flush()
    return 0 if soft else failure


def guarded_main(argv: list[str]) -> int:
    """`main`, except that a fault in the launcher itself names itself as a failed handler does."""
    try:
        return main(argv)
    except Exception as problem:
        try:
            event = _WHO["event"] or envelope_field("hook_event_name") or None
        except Exception:
            event = None
        text = failed(_WHO["handler"], event, "exit 1", f"{type(problem).__name__}: {problem}")
        if _WHO["soft"]:
            return 0
        return 0 if answer([text], []) else 1


if __name__ == "__main__":
    sys.exit(guarded_main(sys.argv[1:]))
