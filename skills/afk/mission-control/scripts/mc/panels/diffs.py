"""MC-4 Diff review — derived from git (feature branch range, per-subtask
commits; PRD "Mission-control panels" row MC-4).

This module is the diff-extraction half of the SDD §9b "git binary" seam
(the merge/ancestry half belongs to 0005-preflight-skill). It shells out to
the repo-standard `git` binary already on PATH; the seam-test is a
git-backed fixture (a temp repo with real commits) driving this panel's
golden output.
"""
from __future__ import annotations

import html
import subprocess
from pathlib import Path

from ..vm import Absent, PanelVM

PANEL_ID = "diffs"
PANEL_TITLE = "Diff review"

_MAX_COMMITS = 20
_UNIT_SEP = "\x1f"


def parse(spec_dir: Path):
    inside = _run_git(spec_dir, ["rev-parse", "--is-inside-work-tree"])
    if inside is None or inside.strip() != "true":
        return Absent(PANEL_ID, "spec folder is not inside a git working tree")

    log = _run_git(spec_dir, ["log", f"-n{_MAX_COMMITS}", f"--pretty=format:%h{_UNIT_SEP}%s"])
    if not log or not log.strip():
        return Absent(PANEL_ID, "git log returned no commits")

    commits = []
    for line in log.splitlines():
        if _UNIT_SEP not in line:
            continue
        short_hash, subject = line.split(_UNIT_SEP, 1)
        commits.append((short_hash, subject))
    if not commits:
        return Absent(PANEL_ID, "git log returned no parseable commits")

    body = ['<ul class="mc-diffs">']
    for short_hash, subject in commits:
        stat = _run_git(spec_dir, ["show", "--stat", "--pretty=format:", short_hash]) or ""
        files = [line.strip() for line in stat.splitlines() if line.strip() and "|" in line]
        files_html = "".join(f"<li>{html.escape(f)}</li>" for f in files)
        body.append(
            '<li><code>{h}</code> {s}<ul class="mc-diff-files">{files}</ul></li>'.format(
                h=html.escape(short_hash), s=html.escape(subject), files=files_html
            )
        )
    body.append("</ul>")
    return PanelVM(PANEL_ID, PANEL_TITLE, "\n".join(body))


def _run_git(spec_dir: Path, args: list):
    try:
        result = subprocess.run(
            ["git", "-C", str(spec_dir), *args],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout
