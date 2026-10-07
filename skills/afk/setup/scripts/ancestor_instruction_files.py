#!/usr/bin/env python3
"""Report instruction files that sit ABOVE a repository and leak into it.

    ancestor_instruction_files.py [repo_dir] [--check]

A harness that walks the working directory upward past the git root reads any
instruction file it finds in an ancestor directory, so one left in the git
root's parent (or higher, up to the filesystem root) is silently prepended to
every repository below it. This probe finds those strays. It never scans a
directory tree: it tests one fixed set of names at each ancestor by direct path
test, so it cannot trip an endpoint sensor the way a recursive scan from a drive
root would.

Names checked at each ancestor: AGENTS.md, AGENTS.override.md, CLAUDE.md,
CLAUDE.local.md, .claude/CLAUDE.md, .claude/AGENTS.md.

The harness user-global homes are excluded: a file inside ~/.claude or ~/.codex
is the global steering file, not a stray. A file directly in the home
directory (~/AGENTS.md, ~/CLAUDE.md) IS a stray and is reported.

Repository root: the argument when given, else `git rev-parse --show-toplevel`
from the current directory, else the current directory.

--check: exit 0 when no stray is found, 1 when one is, and print nothing. Exit 2
on a bad argument. Without --check: print one line per stray with its byte size,
why it leaks, and the two ways to stop it, then exit 0 (clean) or 1 (strays).
"""
import os
import subprocess
import sys
from pathlib import Path

NAMES = (
    "AGENTS.md",
    "AGENTS.override.md",
    "CLAUDE.md",
    "CLAUDE.local.md",
    ".claude/CLAUDE.md",
    ".claude/AGENTS.md",
)


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def repo_root(argv):
    args = [a for a in argv[1:] if a != "--check"]
    if len(args) > 1:
        die("usage: ancestor_instruction_files.py [repo_dir] [--check]")
    start = Path(args[0]) if args else Path.cwd()
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=20,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        pass
    return start.resolve()


def global_homes():
    """The harness user-global directories whose files are globals, not strays."""
    home = Path.home()
    return (home / ".claude").resolve(), home / ".codex"


def is_global(candidate, homes):
    candidate = candidate.resolve()
    for home in homes:
        home = home.resolve()
        if candidate == home or home in candidate.parents:
            return True
    return False


def strays(root, ancestors=None):
    """(path, bytes) for every stray instruction file above `root`, shallow first.

    `ancestors` is the directory list to test; it defaults to every directory
    above `root` up to the filesystem root. Production passes none.
    """
    homes = global_homes()
    if ancestors is None:
        ancestors = list(root.parents)
    found = []
    for ancestor in ancestors:
        for name in NAMES:
            candidate = ancestor / name
            if not candidate.is_file():
                continue
            if is_global(candidate, homes):
                continue
            try:
                size = candidate.stat().st_size
            except OSError:
                size = -1
            found.append((candidate, size))
    return found


def main():
    check = "--check" in sys.argv
    root = repo_root(sys.argv)
    found = strays(root)

    if check:
        sys.exit(1 if found else 0)

    if not found:
        print("No stray instruction files above %s." % root)
        sys.exit(0)

    print("Stray instruction files ABOVE %s:" % root)
    print("(read by a harness that walks the working directory upward past the")
    print(" git root — see providers/HARNESS-MATRIX.md — so each is prepended to")
    print(" every repository below it, silently.)\n")
    for path, size in found:
        size_txt = "%d bytes" % size if size >= 0 else "unreadable"
        print("  %s  (%s)" % (path, size_txt))
    print("\nFor each: delete it, or add its path to `claudeMdExcludes` in your")
    print("settings so the harness stops loading it. Never delete it without")
    print("the developer's answer — it may be theirs on purpose.")
    sys.exit(1)


if __name__ == "__main__":
    main()
