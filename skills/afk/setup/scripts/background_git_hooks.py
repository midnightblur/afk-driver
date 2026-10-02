#!/usr/bin/env python3
"""Report git hooks that start a detached background process.

    background_git_hooks.py [repo_dir] [--check]

Git runs one hooks directory for every worktree of a checkout. A hook there that
detaches a process — a trailing `&`, `nohup`, `setsid`, `disown`, `start /b`,
`Start-Process` — returns at once, so git never waits for or bounds the work it
started. Each commit can then add another full run behind the last, and the
load starves every tool on the machine. This probe finds those hooks.

Directory read: `git rev-parse --git-path hooks`, which follows `core.hooksPath`.
Skipped: `*.sample` files and the stubs `hooks/install-git-hooks.sh` installs.

Repository root: the argument when given, else the current directory.

--check: exit 0 when no such hook is found, 1 when one is, and print nothing.
Exit 2 on a bad argument. Without --check: print each hook with the line that
detaches, then exit 0 (clean) or 1 (found).
"""
import re
import subprocess
import sys
from pathlib import Path

AFK_STUB = "(installed by afk-toolkit install-git-hooks.sh)"
DETACH = (
    re.compile(r"(?<![&>|<])&(?![&>])"),
    re.compile(r"\b(nohup|setsid|disown)\b"),
    re.compile(r"\bstart\s+(\"[^\"]*\"\s+)?/b\b", re.I),
    re.compile(r"\bStart-Process\b", re.I),
)


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def hooks_dir(argv):
    args = [a for a in argv[1:] if a != "--check"]
    if len(args) > 1:
        die("usage: background_git_hooks.py [repo_dir] [--check]")
    start = Path(args[0]) if args else Path.cwd()
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--path-format=absolute", "--git-path", "hooks"],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    return Path(out.stdout.strip())


def detaching_lines(text):
    """(line number, line) for every non-comment line that detaches a process."""
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        code = line.strip()
        if not code or code.startswith("#"):
            continue
        if any(p.search(code) for p in DETACH):
            hits.append((n, code))
    return hits


def offenders(directory):
    """(hook path, [(line number, line)]) for every hook that detaches a process."""
    found = []
    if directory is None or not directory.is_dir():
        return found
    for hook in sorted(directory.iterdir()):
        if not hook.is_file() or hook.suffix == ".sample":
            continue
        try:
            text = hook.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if AFK_STUB in text:
            continue
        hits = detaching_lines(text)
        if hits:
            found.append((hook, hits))
    return found


def main():
    check = "--check" in sys.argv
    directory = hooks_dir(sys.argv)
    found = offenders(directory)

    if check:
        sys.exit(1 if found else 0)

    if not found:
        print("No git hook in %s starts a background process." % directory)
        sys.exit(0)

    print("Git hooks in %s that start a background process:" % directory)
    print("(git runs them for every worktree and does not wait for the work they")
    print(" start, so each commit can stack another run behind the last.)\n")
    for hook, hits in found:
        print("  %s" % hook)
        for n, line in hits:
            print("    line %d: %s" % (n, line))
    print("\nFor each: remove the hook, or remove the line that detaches. Never")
    print("delete it without the developer's answer — it may be theirs on purpose.")
    sys.exit(1)


if __name__ == "__main__":
    main()
