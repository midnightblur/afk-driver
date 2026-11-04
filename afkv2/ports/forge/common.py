"""What the GitHub and GitLab forms share: the payload readers and the CI wait."""

from __future__ import annotations

import time
from typing import NamedTuple

from tracker.envelope import Refusal, fail, need, ok

DEFAULT_BUDGET, DEFAULT_INTERVAL = 5400, 180
MAX_READ_ERRORS = 3
SIDES = ("new", "old", "context")
TERMINAL = ("success", "failed", "canceled")
PLAIN_NOTE_REASON = "the position was rejected; this landed as a plain note"


class Target(NamedTuple):
    side: str
    old_path: str
    new_path: str
    line: int | None
    old_line: int | None


def ref(payload):
    """The change reference. A leading dash would reach the command line as a flag."""
    value = str(need(payload, "id"))
    if value.startswith("-"):
        raise Refusal("bad-payload", f"`id` {value} is no change reference")
    return value


PAGE = 100


def branch(payload):
    """The source branch. A leading dash would reach the command line as a flag."""
    value = payload.get("branch")
    if not isinstance(value, str) or not value.strip() or value.startswith("-"):
        raise Refusal("bad-payload", "the payload needs `branch`: the name of a source branch")
    return value


def change_list(items, own, entry):
    """One page of the forge, newest first. A full page can hide an open change: it refuses."""
    if len(items) >= PAGE:
        raise Refusal("too-many", f"the forge answered {PAGE} changes for this branch: only one page is read")
    if not all(isinstance(item, dict) for item in items):
        raise Refusal("bad-answer", "the change list holds an item that is not a JSON object")
    changes = [entry(item) for item in items if own(item)]
    if not all(change["id"].isdigit() for change in changes):
        raise Refusal("bad-answer", "the change list holds a change with no number")
    changes.sort(key=lambda change: int(change["id"]), reverse=True)
    return ok(changes=changes, count=len(changes))


def body_text(payload):
    """A blank body is refused: it would wipe the description of the change."""
    body = payload.get("body")
    if not isinstance(body, str) or not body.strip():
        raise Refusal("bad-payload", "the payload needs a `body` that is not blank")
    return body


def _comparable(text):
    """A forge may change line ends or trim the end of a description: neither is a lost write."""
    return str(text or "").replace("\r\n", "\n").rstrip()


def check_body_kept(sent, read, change):
    """A write is finished when the forge shows the text. The text stays out of the error."""
    try:
        seen = read()
    except Refusal as refusal:
        raise Refusal("body-not-kept", f"the write to {change} ran, but its description could not be read back: "
                                       f"{refusal.reason}", id=change) from None
    if _comparable(seen) != _comparable(sent):
        raise Refusal("body-not-kept", f"the write to {change} ran, but its description is not the text sent", id=change)


def joined(value):
    return ",".join(str(item) for item in value) if isinstance(value, (list, tuple)) else str(value or "")


def _line(payload, key):
    value = payload.get(key)
    if value is None or value == "":
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise Refusal("bad-position", f"`{key}` must be a line number, not {value!r}") from None
    if number < 1:
        raise Refusal("bad-position", f"`{key}` must be a line number, not {value!r}")
    return number


def inline_target(payload):
    """Where an inline comment goes; None for a plain comment."""
    file = payload.get("file") or ""
    old_path = payload.get("old_path") or payload.get("new_path") or file
    new_path = payload.get("new_path") or payload.get("old_path") or file
    if not old_path:
        return None
    side = payload.get("side") or "new"
    if side not in SIDES:
        raise Refusal("bad-position", f"`side` must be one of {', '.join(SIDES)}, not {side!r}")
    target = Target(side, old_path, new_path, _line(payload, "line"), _line(payload, "old_line"))
    if side in ("new", "context") and target.line is None:
        raise Refusal("bad-position", f"a comment on the {side} side needs `line`")
    if side in ("old", "context") and target.old_line is None:
        raise Refusal("bad-position", f"a comment on the {side} side needs `old_line`")
    return target


def comment_id(answer):
    ident = str(answer.get("id") or "") if isinstance(answer, dict) else ""
    if not ident:
        raise Refusal("bad-answer", "the forge answer names no comment id")
    return ident


def diff_answer(diff):
    return ok(diff=diff, lines=diff.count("\n"), bytes=len(diff))


def _whole_number(payload, key, default):
    value = payload.get(key)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        raise Refusal("bad-payload", f"`{key}` must be a whole number of seconds") from None


def _unreadable(what, elapsed):
    return fail("unreadable", f"{what} gave no status: auth, network, or no checks on the change; not a verdict", elapsed=elapsed)


def ci_wait(payload, read_status):
    """Poll until a final status or the budget ends. Every readable status exits 0: the caller routes on `status`."""
    change = ref(payload)
    budget = _whole_number(payload, "budget", DEFAULT_BUDGET)
    interval = _whole_number(payload, "interval", DEFAULT_INTERVAL)
    if interval <= 0:
        interval = 1
    errors, elapsed, seen = 0, 0, False
    while True:
        try:
            status = read_status(change)
        except Refusal as refusal:
            if refusal.code == "unavailable":
                raise
            status = ""
        if status:
            errors, seen = 0, True
            if status in TERMINAL:
                return ok(status=status, elapsed=elapsed, id=change)
        else:
            errors += 1
            if errors >= MAX_READ_ERRORS:
                return _unreadable(f"{MAX_READ_ERRORS} reads in a row of {change}", elapsed)
        if elapsed >= budget:
            if not seen:
                return _unreadable(f"every read of {change}", elapsed)
            break
        wait = min(interval, budget - elapsed)
        time.sleep(wait)
        elapsed += wait
    return ok(status="running", elapsed=elapsed, id=change, reason="budget exhausted; the checks keep running")
