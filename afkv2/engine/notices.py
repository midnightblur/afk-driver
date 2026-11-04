"""Engine notices: the git state of a page and the secret hits of the files a show writes (requirement ADR-0003).

`page_notices(page, scan, start)` makes at most 1 git call: `git status` over the page and the scanned files, in
the repository that holds `start` (default: the current folder), with a 10 s limit. The page reads one state:

    committed   git tracks it, changed or not
    untracked   in the repository, not committed yet (also: added to the index only)
    ignored     git ignores it
    outside     not in the repository; no git call is needed for it
    unknown     git is missing, failed or timed out; nothing is scanned

The scan reads the page and each scan file that is in the repository and not ignored, for about 10 shapes copied
from the v1 report-issue redactor (`skills/utils/report-issue/scripts/redact.py`, TOKEN_SHAPES and its
private-key, bearer and credential-authority rules). A hit holds the file, the line and the shape, never the
value. Nothing here blocks, calls a model or uses the network.
"""

from __future__ import annotations

import bisect
import os
import re
import subprocess
from pathlib import Path

GIT = "git"
GIT_TIMEOUT_S = 10
SCANNED = frozenset({"committed", "untracked"})
MAX_HITS = 20


# The literal start of a token comes first, so the search skips ahead to it; the check behind it wants no
# letter, digit, `_` or `-` before the token, so a kebab word such as `risk-...` holds no `sk-` key. A JSON escape
# `\n`, `\r` or `\t` before it is a boundary too: the scan reads a page document as raw JSON.
def _token(literal: str, rest: str) -> re.Pattern:
    word = re.escape(literal)
    return re.compile(rf"{word}(?:(?<![A-Za-z0-9_-]{word})|(?<=\\[nrt]{word})){rest}")


SHAPES = {
    "private-key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "github-token": _token("gh", r"[pousr]_[A-Za-z0-9]{20,}"),
    "github-fine-grained-token": _token("github_pat_", r"[A-Za-z0-9_]{20,}"),
    "gitlab-token": _token("glpat-", r"[A-Za-z0-9_-]{20,}"),
    "slack-token": _token("xox", r"[abprs]-[A-Za-z0-9-]{10,}"),
    "aws-access-key": _token("A", r"(?:KIA|SIA|IDA|ROA|GPA|NPA|NVA|IPA|PKA)[0-9A-Z]{16}"),
    "api-key": _token("sk-", r"[A-Za-z0-9_-]{20,}"),
    "web-token": _token("eyJ", r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}"),
    # A token after the word holds a digit, so prose such as "Bearer authentication" is none.
    "bearer-token": re.compile(r"[Bb][Ee][Aa][Rr][Ee][Rr][ \t]+(?=[A-Za-z._~+/=-]*[0-9])[A-Za-z0-9._~+/=-]{12,}"),
    "web-address-password": re.compile(r"://[A-Za-z0-9._%+-]{1,64}:[^\s/@\"'`<>]{1,128}@"),
}


def repository_root(start: Path) -> Path | None:
    """The nearest folder at or above `start` that holds `.git`, or None."""
    start = Path(start).resolve()
    return next((folder for folder in (start, *start.parents) if (folder / ".git").exists()), None)


def _relative(path: Path, root: Path | None) -> str | None:
    """The path from the repository root with `/`, or None when the file is outside the repository."""
    if root is None:
        return None
    try:
        rel = os.path.relpath(Path(path).resolve(), root)
    except ValueError:  # another drive
        return None
    if rel == ".." or rel.startswith(".." + os.sep) or os.path.isabs(rel):
        return None
    rel = rel.replace(os.sep, "/")
    return None if rel == ".git" or rel.startswith(".git/") else rel


def _status(root: Path, paths: list[str]) -> dict[str, str]:
    """The `XY` code of each path git lists, by its case-folded path; a path git lists not is tracked and clean."""
    done = subprocess.run([GIT, "--no-optional-locks", "--literal-pathspecs", "-C", str(root), "status",
                           "--porcelain=v1", "-z", "--ignored", "--untracked-files=all", "--", *paths],
                          capture_output=True, stdin=subprocess.DEVNULL, timeout=GIT_TIMEOUT_S)
    if done.returncode != 0:
        why = done.stderr.decode("utf-8", "replace").strip().splitlines()
        raise OSError(f"git status exit {done.returncode}: {why[0] if why else 'no message'}")
    codes, entries = {}, iter(done.stdout.decode("utf-8", "replace").split("\0"))
    for entry in entries:
        if len(entry) > 3:
            codes[os.path.normcase(entry[3:])] = entry[:2]
            if entry[0] in "RC":
                next(entries, None)  # the old path of a rename or copy
    return codes


def _state(code: str | None) -> str:
    if code == "!!":
        return "ignored"
    if code == "??" or (code and (code[0] in "ARC" or code[1] == "A")):
        return "untracked"
    return "committed"


def page_notices(page: Path, scan=(), start: Path | None = None) -> dict:
    """`{"git_state", "git_reason", "secrets", "secrets_more"}` of a page. `git_reason` says why a state is unknown,
    else None; `secrets` holds the first MAX_HITS hits and `secrets_more` counts the rest."""
    root = repository_root(Path.cwd() if start is None else start)
    files = [Path(page), *(Path(path) for path in scan if Path(path).is_file())]
    rels = [_relative(path, root) for path in files]
    inside = list(dict.fromkeys(rel for rel in rels if rel is not None))
    codes = {}
    if inside:
        try:
            codes = _status(root, inside)
        except subprocess.TimeoutExpired:
            return _unknown(f"git status ran past {GIT_TIMEOUT_S} s")
        except OSError as error:
            return _unknown(str(error) or type(error).__name__)
    states = ["outside" if rel is None else _state(codes.get(os.path.normcase(rel))) for rel in rels]
    chosen = list(dict.fromkeys((path, rel) for path, rel, state in zip(files, rels, states) if state in SCANNED))
    hits = scan_files(chosen)
    return {"git_state": states[0], "git_reason": None, "secrets": hits[:MAX_HITS],
            "secrets_more": max(0, len(hits) - MAX_HITS)}


def _unknown(why: str) -> dict:
    return {"git_state": "unknown", "git_reason": why, "secrets": [], "secrets_more": 0}


def scan_files(files) -> list[dict]:
    """The hits `{file, line, shape}` of each `(path, name)`, in file order, then line order; `name` names the file."""
    hits = []
    for path, name in files:
        try:
            text = Path(path).read_bytes().decode("utf-8", "replace")
        except OSError:
            continue
        hits += [{"file": name, "line": line, "shape": shape} for line, shape in scan_text(text)]
    return hits


def scan_text(text: str) -> list[tuple[int, str]]:
    """Each (line, shape) with a hit, once, by line then by shape order."""
    found = {(m.start(), shape) for shape, pattern in SHAPES.items() for m in pattern.finditer(text)}
    if not found:
        return []
    breaks = [m.start() for m in re.finditer("\n", text)]
    order = list(SHAPES)
    lines = {(bisect.bisect_left(breaks, at) + 1, shape) for at, shape in found}
    return sorted(lines, key=lambda hit: (hit[0], order.index(hit[1])))
