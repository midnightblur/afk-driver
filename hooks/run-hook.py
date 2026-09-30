"""Launch a shell hook handler through a POSIX shell the harness cannot mistake.

A harness spawns a hook command through whatever shell it prefers, so the
command string must be valid in both a POSIX shell and PowerShell, and a bare
`bash` is not a reliable name on Windows: it resolves to the WSL stub in the
system directory on many machines, which cannot run these handlers. This
launcher is the one command every hook entry uses. It resolves the handler
path, locates a real Git Bash, forwards stdin, stdout, stderr and the exit
code, and stays silent when an optional handler is absent.

Usage:
    python run-hook.py [--soft] plugin <handler.sh> [args...]
    python run-hook.py [--soft] repo-list <event>

    plugin     handler under this plugin's own hooks/ directory
    repo-list  every repository-owned handler the consuming repository declares
               for <event> in `.afk/hooks.json`; absent file or repository
               exits 0
    --soft     always exit 0 (advisory handlers that must never block a turn)

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
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPO_HOOKS_MANIFEST = ".afk/hooks.json"
EVENTS = {"SessionStart", "PreToolUse", "PostToolUse", "PostCompact", "Stop", "WorktreeCreated"}
# The events whose whole point is to stop a turn. A handler that cannot run is
# a missing verdict on these, so the launcher answers for it. PostToolUse and
# PostCompact carry context injections, never a block, so they only warn.
BLOCKING_EVENTS = {"Stop", "PreToolUse"}


def repo_root(env: dict[str, str]) -> Path | None:
    named = env.get("CLAUDE_PROJECT_DIR") or env.get("PROJECT_DIR")
    if named and Path(named).is_dir():
        return Path(named)
    # Windows resolves the executable name against this process's PATH, not the
    # PATH being handed to the child, so name git absolutely when it is only on
    # the shell's own PATH.
    git = shutil.which("git", path=env.get("PATH")) or "git"
    try:
        out = subprocess.run(
            [git, "-C", os.getcwd(), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=20, env=env,
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
            ["git", "--exec-path"], capture_output=True, text=True, timeout=20,
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
            completed = subprocess.run(
                [str(bash), "-c", snippet, "run-hook", str(library), event, reason],
                env=env, timeout=60,
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
    soft = False
    while argv and argv[0] == "--soft":
        soft = True
        argv = argv[1:]
    if len(argv) < 2 or argv[0] not in {"plugin", "repo-list"}:
        sys.stderr.write(
            "run-hook.py: usage: run-hook.py [--soft] plugin <handler.sh> [args...]\n"
            "run-hook.py: usage: run-hook.py [--soft] repo-list <event>\n"
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

    if argv[0] == "plugin":
        script = PLUGIN_ROOT / "hooks" / argv[1]
        if not script.is_file():
            # An optional handler this checkout does not ship is not a failure.
            return 0
        if argv[1] in OWNER_HANDLERS:
            env.update(owner_env())
        completed = subprocess.run([str(bash), str(script), *argv[2:]], env=env)
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
        try:
            completed = subprocess.run(
                [str(bash), str(script)], env=env, input=envelope, timeout=timeout,
                capture_output=blocking,
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
