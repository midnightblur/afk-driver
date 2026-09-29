"""Review IDs and fix history belong on the PR, never in shipped code comments
or docstrings — a citation like ``A3-004`` or ``CA2-3`` describes who reviewed
a line, not what the line does, and goes stale the moment the round ends.

``scripts/tests`` is exempt: a test fixture legitimately pins the scenario one
specific finding covers, and that citation is useful there."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = Path(__file__).resolve().parent

PATTERN = re.compile(r"\b(?:C?A[0-9]-[0-9]{3}|CA[0-9]-[0-9])\b")


def _iter_scanned_files():
    """Every tracked and untracked repository file, from git's own
    enumeration and its `.gitignore` rules — never a partial suffix
    allowlist, which silently passes any shipped file whose extension nobody
    thought to list (YAML, JS, CSS, HTML, extensionless text, ...)."""
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    for name in listed.split(b"\0"):
        if not name:
            continue
        path = ROOT / name.decode("utf-8", errors="surrogateescape")
        if not path.is_file():
            continue
        if TESTS_DIR in path.parents:
            continue
        yield path


def _is_binary(data: bytes) -> bool:
    return b"\x00" in data


def test_no_review_id_citations_outside_scripts_tests():
    hits = []
    for path in _iter_scanned_files():
        data = path.read_bytes()
        if _is_binary(data):
            continue
        text = data.decode("utf-8", errors="ignore")
        for match in PATTERN.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(f"{path.relative_to(ROOT)}:{line_no}: {match.group(0)}")
    assert not hits, "review-ID citation(s) outside scripts/tests:\n" + "\n".join(hits)
