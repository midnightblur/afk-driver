"""Shared read-only git access for section parsers (the diff-extraction half
of the SDD §9b "git binary" seam). Every call is best-effort: any failure
returns None so a section degrades to Absent instead of crashing the render.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

UNIT_SEP = "\x1f"
_TIMEOUT = 15


def run_git(spec_dir: Path, args: list):
    try:
        result = subprocess.run(
            ["git", "-C", str(spec_dir), *args],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def inside_work_tree(spec_dir: Path) -> bool:
    out = run_git(spec_dir, ["rev-parse", "--is-inside-work-tree"])
    return out is not None and out.strip() == "true"


def log_subjects(spec_dir: Path, max_commits: int):
    """Recent commits, subjects only (cheap): [{full, short, subject}]."""
    out = run_git(spec_dir, ["log", f"-n{max_commits}", f"--pretty=format:%H{UNIT_SEP}%h{UNIT_SEP}%s"])
    if out is None:
        return None
    commits = []
    for line in out.splitlines():
        parts = line.split(UNIT_SEP)
        if len(parts) == 3:
            commits.append({"full": parts[0], "short": parts[1], "subject": parts[2]})
    return commits


def log_with_numstat(spec_dir: Path, max_commits: int) -> list:
    """Recent commits, one git call: [{hash, subject, files: [{path, add, del}]}]."""
    out = run_git(
        spec_dir,
        ["log", f"-n{max_commits}", "--numstat", f"--pretty=format:%x1f%h{UNIT_SEP}%s"],
    )
    if out is None:
        return None
    commits = []
    current = None
    for line in out.splitlines():
        if line.startswith("\x1f"):
            short_hash, _, subject = line[1:].partition(UNIT_SEP)
            current = {"hash": short_hash, "subject": subject, "files": []}
            commits.append(current)
        elif line.strip() and current is not None:
            parts = line.split("\t")
            if len(parts) == 3:
                added, deleted, path = parts
                current["files"].append({"path": path, "add": added, "del": deleted})
    return commits
