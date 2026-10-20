"""The only code that appends to a diagnosis's Outside writes, and the read-back retry.

A writing script runs each outside write through `retry_with_read_back`, then
records it with `append_outside_write` straight after it succeeds; a re-run
skips a write that `listed` finds. Entry grammar: DIAGNOSIS-FORMAT.md
"Outside writes entries".
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnosis_file import HEADING, load_format, outside_write_kinds  # noqa: E402

SECTION = "outside writes"
ENTRY = re.compile(r"^([a-z][a-z-]*):\s*(\S.*)$")
EVIDENCE = re.compile(r"^afk-evidence \S+ [a-z][a-z0-9-]*$")
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


def retry_with_read_back(write, read_back=None, *, key=None, sleep=time.sleep) -> Outcome:
    """Run `write()`; on failure retry at most twice, after 5 s then 20 s, and
    only after `read_back()` shows the write left nothing.

    `read_back()` answers None for "no effect", a failed answer for "cannot
    tell", anything else for "the write took effect". Without a read-back a
    failed write is never retried.
    """
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
        seen = _attempt(read_back)
        if seen is None:
            continue
        if failed(seen):
            return Outcome(False, answer, attempts,
                           reason=f"read-back could not tell whether the write took effect: {_reason(seen)}")
        return Outcome(True, seen, attempts, found=True)
    return Outcome(False, answer, attempts, reason=_reason(answer))


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
    lines = Path(diagnosis).read_text(encoding="utf-8").splitlines()
    start, end = _section(lines)
    return f"- {_normal(entry)}" in (line.strip() for line in lines[start:end])


def append_outside_write(diagnosis, entry: str, format_path=None) -> bool:
    """Append `- {entry}` as the last item of Outside writes. Earlier lines are
    never changed; an entry already listed is not added again (returns False)."""
    entry = _normal(entry)
    kind_value = ENTRY.match(entry)
    kinds = outside_write_kinds(load_format(format_path))
    if not kind_value or kind_value.group(1) not in kinds:
        raise ValueError(f"`{entry}` is not `{{kind}}: {{value}}` with a kind from {sorted(kinds)}")
    if kind_value.group(1) == "evidence" and not EVIDENCE.match(kind_value.group(2)):
        raise ValueError(f"`{kind_value.group(2)}` is not an evidence marker `afk-evidence {{work id}} {{step}}`")
    path = Path(diagnosis)
    raw = path.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.splitlines()
    start, end = _section(lines)
    if f"- {entry}" in (line.strip() for line in lines[start:end]):
        return False
    at = end
    while at > start and not lines[at - 1].strip():
        at -= 1
    lines.insert(at, f"- {entry}")
    trailing = raw.endswith("\n") or at == len(lines) - 1
    _replace(path, newline.join(lines) + (newline if trailing else ""))
    return True


def _normal(entry: str) -> str:
    entry = entry.strip()
    return entry[2:].strip() if entry.startswith("- ") else entry


def _section(lines):
    """(first content line, end) of Outside writes; ValueError when absent."""
    start = None
    for i, line in enumerate(lines):
        match = HEADING.match(line)
        if match and start is not None:
            return start, i
        if match and match.group(1).lower() == SECTION:
            start = i + 1
    if start is None:
        raise ValueError("the diagnosis has no `## Outside writes` part")
    return start, len(lines)


def _replace(path: Path, text: str):
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
