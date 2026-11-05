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
value. A file over MAX_SCAN_BYTES is scanned to that limit, and `scan_cut` names it. Nothing here blocks, calls a
model or uses the network.
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
# The scan reads at most this many bytes of a file: the SDD §10 budget is 60 ms for 2 MB.
MAX_SCAN_BYTES = 2 * 1024 * 1024


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
    """`{"git_state", "git_reason", "secrets", "secrets_more", "scan_cut"}` of a page. `git_reason` says why a
    state is unknown, else None; `secrets` holds the first hit of each file, then the next hits up to MAX_HITS, and
    `secrets_more` counts the rest. `scan_cut` names each scanned file over MAX_SCAN_BYTES."""
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
    shown = _capped(hits)
    cut = [name for path, name in chosen if _size(path) > MAX_SCAN_BYTES]
    return {"git_state": states[0], "git_reason": None, "secrets": shown, "secrets_more": len(hits) - len(shown),
            "scan_cut": cut}


def _size(path: Path) -> int:
    try:
        return Path(path).stat().st_size
    except OSError:
        return 0


def _capped(hits: list[dict]) -> list[dict]:
    """The first hit of each file, then the next hits in order until MAX_HITS: every file with a hit is named, also
    past the cap (PRD AC-049). File order, then line order, as in `hits`."""
    keep, files = set(), set()
    for index, hit in enumerate(hits):
        if hit["file"] not in files:
            files.add(hit["file"])
            keep.add(index)
    for index in range(len(hits)):
        if len(keep) >= MAX_HITS:
            break
        keep.add(index)
    return [hit for index, hit in enumerate(hits) if index in keep]


def _unknown(why: str) -> dict:
    return {"git_state": "unknown", "git_reason": why, "secrets": [], "secrets_more": 0, "scan_cut": []}


def scan_files(files) -> list[dict]:
    """The hits `{file, line, shape}` of each `(path, name)`, in file order, then line order; `name` names the file.
    Each file is read to MAX_SCAN_BYTES at most."""
    hits = []
    for path, name in files:
        try:
            with open(path, "rb") as handle:
                text = handle.read(MAX_SCAN_BYTES).decode("utf-8", "replace")
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
