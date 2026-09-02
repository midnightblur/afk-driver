"""Launch a shell hook handler through a POSIX shell the harness cannot mistake.

A harness spawns a hook command through whatever shell it prefers, so the
command string must be valid in both a POSIX shell and PowerShell, and a bare
`bash` is not a reliable name on Windows: it resolves to the WSL stub in the
system directory on many machines, which cannot run these handlers. This
launcher is the one command every hook entry uses. It resolves the handler
path, locates a real Git Bash, forwards stdin, stdout, stderr and the exit
code, and stays silent when an optional handler is absent.

Usage:
    python run-hook.py [--soft] plugin|repo <handler.sh> [args...]

    plugin  handler under this plugin's own hooks/ directory
    repo    handler under the repository harness hooks directory; absent
            repository or handler exits 0
    --soft  always exit 0 (advisory handlers that must never block a turn)

Overrides: AFK_BASH, then GIT_BASH, then a Git-relative lookup, then the known
install locations, then PATH excluding the Windows system directory.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPO_HOOKS = "tools/payable/ai-agents/harness/hooks"


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


def main(argv: list[str]) -> int:
    soft = False
    while argv and argv[0] == "--soft":
        soft = True
        argv = argv[1:]
    if len(argv) < 2 or argv[0] not in {"plugin", "repo"}:
        sys.stderr.write(
            "run-hook.py: usage: run-hook.py [--soft] plugin|repo <handler.sh> [args...]\n"
        )
        return 0 if soft else 2

    kind, handler, rest = argv[0], argv[1], argv[2:]
    bash = find_bash()
    if bash is None:
        sys.stderr.write(
            f"run-hook.py: no POSIX shell found for {handler}. Install Git Bash, "
            "or point AFK_BASH at a bash executable.\n"
        )
        return 0 if soft else 1
    # The shell's own toolchain sits on this PATH, so git resolves here even
    # when the harness handed down a PATH carrying neither.
    env = shell_env(bash)

    if kind == "plugin":
        script = PLUGIN_ROOT / "hooks" / handler
    else:
        root = repo_root(env)
        if root is None:
            return 0
        script = root / REPO_HOOKS / handler
    if not script.is_file():
        # An optional handler this checkout does not ship is not a failure.
        return 0

    completed = subprocess.run([str(bash), str(script), *rest], env=env)
    return 0 if soft else completed.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
