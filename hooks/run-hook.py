"""Launch a shell hook handler through a POSIX shell the harness cannot mistake.

A harness spawns a hook command through whatever shell it prefers, so the
command string must be valid in both a POSIX shell and PowerShell, and a bare
`bash` is not a reliable name on Windows: it resolves to the WSL stub in the
system directory on many machines, which cannot run these handlers. This
launcher is the one command every hook entry uses. It resolves the handler
path, locates a real Git Bash, forwards stdin, stdout, stderr and the exit
code, and stays silent when an optional handler is absent.

Usage:
    python run-hook.py [--soft] [--deadline <seconds>] plugin <handler.sh> [args...]
    python run-hook.py [--soft] [--deadline <seconds>] repo-list <event>

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
missing, the matcher is not a regular expression, the manifest does not parse,
the handler returns no verdict inside its timeout — is a configuration error,
never a silent skip. On Stop and PreToolUse the launcher blocks the turn with
the decision object a failed gate emits, so a gate cannot disappear by being
misdeclared. A Stop or PreToolUse handler that exits non-zero, or prints a refusal
object, is a refusal: its own stdout and exit code are never passed through. The
launcher gathers every refusal and emits one verdict in the provider's block
shape (PreToolUse: the deny JSON at exit 0). With no POSIX shell the same
events block too. On the remaining events it writes the reason to stderr.

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
             jobbed: bool = True) -> subprocess.CompletedProcess:
    """`subprocess.run` for a handler: the whole tree dies on timeout, error or signal."""
    pipes = subprocess.PIPE if capture else None
    proc, job = _spawn(args, jobbed, env=env, stdin=subprocess.PIPE if input is not None else None,
                       stdout=pipes, stderr=pipes)
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
    # The working tree's Git root, like every plugin gate; CLAUDE_PROJECT_DIR
    # names the launch checkout, which can differ.

    # Windows resolves the executable name against this process's PATH, not the
    # PATH being handed to the child, so name git absolutely when it is only on
    # the shell's own PATH.
    git = shutil.which("git", path=env.get("PATH")) or "git"
    try:
        out = subprocess.run(
            [git, "-C", os.getcwd(), "rev-parse", "--show-toplevel"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=20, env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    top = out.stdout.strip()
    return Path(top) if out.returncode == 0 and top else None


def is_wsl_stub(candidate: Path) -> bool:
    """The Windows system directory ships a WSL launcher named bash.exe."""
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    try:
        candidate.resolve().relative_to(Path(system_root).resolve())
    except (ValueError, OSError):
        return False
    return True


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


def shell_env(bash: Path) -> dict[str, str]:
    """Handlers call grep, sed, git and friends.

    A parent PATH that never had a POSIX shell on it has none of them either, so
    put the shell's own toolchain in front of whatever the harness passed down.
    """
    env = dict(os.environ)
    if os.name != "nt":
        return env
    root = bash.resolve().parent.parent
    extra = [str(root / "bin"), str(root / "usr" / "bin"), str(root / "mingw64" / "bin")]
    present = {part.lower() for part in env.get("PATH", "").split(os.pathsep)}
    missing = [part for part in extra if Path(part).is_dir() and part.lower() not in present]
    if missing:
        env["PATH"] = os.pathsep.join(missing + [env.get("PATH", "")]).rstrip(os.pathsep)
    return env


def manifest_path(root: Path) -> Path:
    """`.afk/hooks.json` unless the repository's config names another path.

    The configuration reader is the plugin's own module, so this stays one
    import rather than a subprocess on the hook path.
    """
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "afk_config", PLUGIN_ROOT / "scripts" / "afk-config.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
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


def block_without_shell(event: str) -> int:
    """No POSIX shell: a repository gate that matches this call still blocks it."""
    env = dict(os.environ)
    root = repo_root(env)
    entries, faults = repo_entries(root, event) if root is not None else ([], [])
    tool = ""
    try:
        raw = sys.stdin.buffer.read() if not sys.stdin.isatty() else b""
        tool = str(json.loads(raw.decode("utf-8", "replace")).get("tool_name") or "") if raw else ""
    except (ValueError, AttributeError):
        tool = ""
    for entry in entries:
        if matcher_fault(entry.get("matcher")) or matches(entry.get("matcher"), tool):
            faults.append(f"no POSIX shell to run {entry.get('script')}")
    return block(event, faults, None, env) if faults else 0


def block(event: str, faults: list[str], bash: Path | None, env: dict[str, str],
          refused: list[str] | None = None) -> int:
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
    if refused:
        listed = "\n".join(f"  - {item}" for item in refused)
        parts.append(f"afk: this repository's {event} handlers refused:\n{listed}")
    reason = "\n".join(parts)
    library = PLUGIN_ROOT / "hooks" / "lib" / "provider.sh"
    if bash is not None and library.is_file():
        snippet = (
            '. "$1" || exit 70\n'
            'case "$2" in\n'
            '  Stop) afk_emit_stop_block "$3"; exit "$(afk_stop_block_code)" ;;\n'
            '  *) printf \'%s\\n\' "$3" >&2; afk_emit_deny "$3"; exit 0 ;;\n'
            'esac\n'
        )
        try:
            completed = run_tree(
                [str(bash), "-c", snippet, "run-hook", str(library), event, reason],
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
        spec = importlib.util.spec_from_file_location("afk_worktree_owner", PLUGIN_ROOT / "scripts" / "worktree_owner.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        found = module.find_owner()
    except Exception:
        return {}
    return {"AFK_WORKTREE_OWNER": f"{found['pid']}:{found['ctime']}"} if found else {}


def main(argv: list[str]) -> int:
    global _DEADLINE_AT, _DEADLINE_S
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

    bash = find_bash()
    if bash is None:
        sys.stderr.write(
            f"run-hook.py: no POSIX shell found for {argv[1]}. Install Git Bash, "
            "or point AFK_BASH at a bash executable.\n"
        )
        if soft:
            return 0
        if argv[0] == "repo-list" and argv[1] in BLOCKING_EVENTS:
            return block_without_shell(argv[1])
        return 1
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
        try:
            completed = run_tree([str(bash), str(script), *argv[2:]], env, timeout=budget_left(),
                                 jobbed=argv[1] not in DETACHES_HELPERS)
        except subprocess.TimeoutExpired:
            sys.stderr.write(
                f"[afk] {argv[1]} exceeded its {_DEADLINE_S:g}s budget — stopped, verdict unknown.\n")
            return 0
        return 0 if soft else completed.returncode

    event = argv[1]
    if event not in EVENTS:
        sys.stderr.write(f"run-hook.py: unknown event: {event}\n")
        return 0 if soft else 2
    root = repo_root(env)
    if root is None:
        return 0
    entries, faults = repo_entries(root, event)
    if not entries and not faults:
        return 0

    envelope = sys.stdin.buffer.read() if not sys.stdin.isatty() else b""
    tool = ""
    if envelope:
        try:
            parsed = json.loads(envelope.decode("utf-8", "replace"))
            tool = str(parsed.get("tool_name") or "")
        except ValueError:
            tool = ""

    failure = 0
    refused: list[str] = []
    allowed: list[bytes] = []
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
            completed = run_tree(
                [str(bash), str(script)], env, input=envelope, timeout=timeout, capture=blocking,
            )
        except subprocess.TimeoutExpired:
            faults.append(f"{named}: no verdict within {timeout:g} seconds")
            continue
        except OSError as problem:
            faults.append(f"{named}: {problem}")
            continue
        if blocking:
            said = (completed.stderr or b"").decode("utf-8", "replace").strip()
            reason = denial(event, completed.stdout or b"")
            if reason is not None or completed.returncode:
                # One verdict leaves this launcher, in the provider's shape: never a handler's own.
                refused.append(reason or said or f"{named} exited {completed.returncode}")
                continue
            if completed.stdout:
                allowed.append(completed.stdout)
            if said:
                sys.stderr.write(said + "\n")
            continue
        if completed.returncode and event == "WorktreeCreated":
            faults.append(f"{named}: exited {completed.returncode}; the worktree is kept")
            continue
        if completed.returncode and not failure:
            failure = completed.returncode

    if faults:
        for fault in faults:
            sys.stderr.write(f"run-hook.py: {fault}\n")
    if (faults or refused) and blocking:
        return block(event, faults, bash, env, refused)
    merged = merge_allowed(allowed)  # context printed while nothing refused: one document
    if merged:
        sys.stdout.write(merged + "\n")
        sys.stdout.flush()
    return 0 if soft else failure


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
