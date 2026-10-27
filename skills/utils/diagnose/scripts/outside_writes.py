"""The only code that appends to a diagnosis's Outside writes, and the read-back retry.

A writing script runs each outside write through `retry_with_read_back`, then
records it with `append_outside_write` straight after it succeeds; a re-run
skips a write that `listed` finds and passes `read_first=True` for the rest.
Entry grammar: DIAGNOSIS-FORMAT.md "Outside writes entries".
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnosis_file import (  # noqa: E402
    BOM, entry_problem, headings, load_format, outside_write_kinds, split_lines)

SECTION = "outside writes"
BACKOFF = (5, 20)


@dataclass
class Outcome:
    ok: bool
    answer: object = None
    attempts: int = 0
    found: bool = False
    reason: str = ""


def failed(answer, key=None) -> bool:
    """An adapter answer that did not write: `error`, `unavailable` or
    `unsupported` (all may arrive with exit 0), a non-object, or an empty `key`."""
    if not isinstance(answer, dict):
        return True
    if answer.get("error") or answer.get("unavailable") or answer.get("unsupported"):
        return True
    return bool(key) and not str(answer.get(key) or "").strip()


def retry_with_read_back(write, read_back=None, *, key=None, read_first=False,
                         sleep=time.sleep) -> Outcome:
    """Run `write()`; on failure retry at most twice, after 5 s then 20 s, and
    only after `read_back()` shows the write left nothing.

    `read_back()` answers None when the write left nothing (the caller maps an
    empty search to None), an adapter answer object when it found the write,
    and a `failed` answer when it cannot tell. Without a read-back a failed
    write is never retried. `read_first` reads back before the first write, for
    a re-run whose write may have taken effect without being listed.
    """
    if read_first and read_back is not None:
        found = _read(read_back, 0)
        if found is not None:
            return found
    attempts = 0
    answer = None
    for delay in (0, *BACKOFF):
        if delay:
            sleep(delay)
        attempts += 1
        answer = _attempt(write)
        if not failed(answer, key):
            return Outcome(True, answer, attempts)
        if read_back is None:
            return Outcome(False, answer, attempts, reason=_reason(answer))
        found = _read(read_back, attempts)
        if found is not None:
            return found
    return Outcome(False, answer, attempts, reason=_reason(answer))


def _read(read_back, attempts):
    """None when the read-back saw no effect, else the Outcome it settles."""
    seen = _attempt(read_back)
    if seen is None:
        return None
    if failed(seen):
        return Outcome(False, seen, attempts,
                       reason=f"read-back could not tell whether the write took effect: {_reason(seen)}")
    return Outcome(True, seen, attempts, found=True)


def _attempt(call):
    try:
        return call()
    except Exception as e:  # a raised write tells nothing about the far side
        return {"error": True, "reason": f"{type(e).__name__}: {e}"}


def _reason(answer) -> str:
    if isinstance(answer, dict):
        return str(answer.get("reason") or answer.get("body") or answer)
    return repr(answer)


def listed(diagnosis, entry: str) -> bool:
    """True when `entry` is already in the diagnosis's Outside writes."""
    lines = _read_lines(Path(diagnosis))[1]
    start, end = _section(lines)
    return f"- {_normal(entry)}" in (line.strip() for line in lines[start:end])


def append_outside_write(diagnosis, entry: str, format_path=None) -> bool:
    """Append `- {entry}` as the last item of Outside writes. Earlier lines are
    never changed; an entry already listed is not added again (returns False)."""
    entry = _normal(entry)
    problem = entry_problem(entry, outside_write_kinds(load_format(format_path)))
    if problem:
        raise ValueError(problem)
    path = Path(diagnosis)
    bom, lines = _read_lines(path)
    start, end = _section(lines)
    if f"- {entry}" in (line.strip() for line in lines[start:end]):
        return False
    at = end
    while at > start and not lines[at - 1].strip():
        at -= 1
    before = lines[at - 1]  # a non-blank line: an entry or the heading
    eol = "\r\n" if before.endswith("\r\n") else "\n" if before.endswith("\n") else ""
    if not eol:
        eol = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"
        lines[at - 1] = before + eol
    lines.insert(at, f"- {entry}{eol}")
    replace_text(path, (BOM if bom else "") + "".join(lines))
    return True


def _read_lines(path: Path):
    """(had a BOM, lines split at `\\n` only, each with its own line end)."""
    text = path.read_bytes().decode("utf-8")
    return text.startswith(BOM), split_lines(text.removeprefix(BOM), keepends=True)


def _normal(entry: str) -> str:
    entry = entry.strip()
    return entry[2:].strip() if entry.startswith("- ") else entry


def _section(lines):
    """(first content line, end) of the first Outside writes; ValueError when absent."""
    marks = list(headings(lines))
    for n, (i, name) in enumerate(marks):
        if name == SECTION:
            return i + 1, marks[n + 1][0] if n + 1 < len(marks) else len(lines)
    raise ValueError("the diagnosis has no `## Outside writes` part")


def replace_text(path: Path, text: str, tries: int = 20, pause: float = 0.05):
    """Write text to path through a temporary file in the same folder."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        shutil.copymode(path, tmp)
        for left in range(tries - 1, -1, -1):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                # Windows refuses the swap while a scanner holds the file open.
                if not left:
                    raise
                time.sleep(pause)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
