"""Write one raw response into the page document, with per-item signals and no judgement (SDD §6).

The raw grammar: first line `[round R-n]`, then `<id> <token>` or `<id> <token> | <note>`, an em dash
for no choice. `<id>` is an element id, or a note id with the token `edit` or `delete`. A later line
continues the note unless it reads as a line of a known id with a token that id takes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from afkv2_config import Refusal

from registry import walk
from schema import invariants
from shell import inject

NO_CHOICE = "—"
NOTE_SEPARATOR = " | "
HEADER = re.compile(r"\[round R-(\d+)\]")
LETTER = re.compile(r"[a-z]")
SETTLED = ("settled_by_mark", "settled_by_note")
SETTLING = ("accept", "sign")
REOPEN = "reopen"
EDIT, DELETE = "edit", "delete"
MARKS = {"decided": {"accept", REOPEN}, "confirm": {"accept", "write-in", REOPEN}, "debate": {"write-in", REOPEN},
         "signoff": {"sign", "changes", REOPEN}, "info": set()}


@dataclass
class Line:
    target: str
    token: str
    text: str | None
    number: int


def _settles(token: str) -> bool:
    return token in SETTLING or bool(LETTER.fullmatch(token))


def apply_mark_table(state: str, lines: list[Line], settled_signal: str | None) -> str:
    """The next point state for the lines of one item (SDD §6, ADR-0002 design). Each line holds a signal."""
    marks = [line.token for line in lines if line.token != NO_CHOICE]
    lone = len(lines) == 1 and len(marks) == 1 and not lines[0].text and _settles(marks[0])
    if state in SETTLED:
        if not lone or (state == "settled_by_mark" and marks[0] != settled_signal):
            return "open"
        return state
    if state == "needs_reading":
        return state
    return "settled_by_mark" if lone else "needs_reading"


def _options(item: dict) -> set[str]:
    prefix = re.compile(re.escape(item["id"]) + "-opt-([a-z])")
    found = set()
    for _, component in walk(item["body"]):
        match = prefix.fullmatch(component.get("id") or "")
        if match:
            found.add(match.group(1))
    return found


class _Page:
    """What the parser and the writer look up in one document."""

    def __init__(self, doc: dict, ids: dict, nodes: dict):
        self.doc, self.ids, self.nodes = doc, ids, nodes
        self.current = next(r for r in doc["rounds"] if r["state"] == "current")
        self.items = {item["id"]: item for r in doc["rounds"] for item in r["items"]}
        self.notes = {note["id"]: (item, note) for item in self.items.values() for note in item.get("notes") or []}

    def owner(self, target: str) -> dict | None:
        """The item that holds an element; None for an element of the `maps` list."""
        path = self.ids[target]
        if path[0] != "rounds":
            return None
        return self.doc["rounds"][path[1]]["items"][path[3]]

    def is_steer(self, target: str) -> bool:
        return target in self.nodes or self.owner(target) is None

    def accepts(self, target: str, token: str) -> bool:
        if target in self.notes:
            return token in (EDIT, DELETE)
        if target not in self.ids:
            return False
        if token == NO_CHOICE:
            return True
        item = self.items.get(target)
        if item is None:
            return False
        if item["kind"] == "debate" and LETTER.fullmatch(token):
            return token in _options(item)
        return token in MARKS[item["kind"]]


def _line_head(text: str) -> tuple[str, str, str | None]:
    head, separator, note = text.partition(NOTE_SEPARATOR)
    target, _, token = head.rpartition(" ")
    return target, token, note if separator else None


def parse_response(raw: str, page: _Page) -> list[Line]:
    """The lines of a response. A refusal names the line the grammar cannot read."""
    rows = [row.removesuffix("\r") for row in raw.split("\n")]
    header = HEADER.fullmatch(rows[0])
    if not header:
        raise Refusal("bad-response", f"item response, field raw: line 1 must be [round R-n], found {rows[0]!r}")
    n = page.current["n"]
    if int(header.group(1)) != n:
        raise Refusal("stale-round", f"item response, field raw: the response answers round {header.group(1)}; "
                                     f"the current round is round {n}")
    lines: list[Line] = []
    for number, row in enumerate(rows[1:], start=2):
        target, token, note = _line_head(row)
        if page.accepts(target, token):
            lines.append(Line(target, token, note or None, number))
        elif lines and lines[-1].text is not None:
            lines[-1].text += "\n" + row
        elif row.strip():
            raise Refusal("bad-response", f"item response, field raw: line {number} is no line of a known element: {row!r}")
    for line in lines:
        if line.text is not None:
            line.text = line.text.rstrip("\n")
    return lines


def _write_note(item: dict, target: str, text: str, n: int) -> str:
    """One note per item per round (SDD §4): a second one on the same item folds into it."""
    note_id = f"N-{n}-{item['id']}"
    notes = item.get("notes") or []
    for note in notes:
        if note["id"] != note_id:
            continue
        if note["deleted"]:
            note.update(text=text, target=target, deleted=False)
        elif note["text"] != text:
            note["text"] += "\n\n" + text
            if note["target"] != target:
                note["target"] = item["id"]
        return note_id
    item["notes"] = [*notes, {"id": note_id, "round": n, "target": target, "text": text, "deleted": False}]
    return note_id


def _edit(note: dict, line: Line) -> str:
    if not line.text:
        raise Refusal("bad-response", f"item response, field raw: line {line.number} edits a note to no text")
    note.update(text=line.text, deleted=False)
    return line.text


def _steer_home(page: _Page, target: str, n: int) -> dict:
    """The item that stores a steer. The note's target carries the meaning, so a free item is best."""
    newest_first = [item for r in reversed(page.doc["rounds"]) for item in r["items"]]
    linked = [item for item in newest_first if item.get("node") == target]
    holder = [page.owner(target)] if page.owner(target) else []
    candidates = [*linked, *holder, *page.current["items"], *newest_first]
    if not candidates:
        raise Refusal("bad-response", f"item response, field raw: no item can hold the note on {target}")
    for item in candidates:
        if any(note["target"] == target and note["round"] == n for note in item.get("notes") or []):
            return item
    for item in candidates:
        if not any(note["id"] == f"N-{n}-{item['id']}" for note in item.get("notes") or []):
            return item
    return candidates[0]


def _table_lines(lines: list[Line], page: _Page) -> dict[str, list[Line]]:
    """The lines the mark table reads, by item: a mark, a note, or an edit of a note on the item.

    The page sends one line per card, so a second line of one id is a conflict even with no mark: it may
    be a line of a note that reads as a card line (D-49).
    """
    seen = [line.target for line in lines]
    by_item: dict[str, list[Line]] = {}
    for line in lines:
        if line.token == EDIT:
            item, note = page.notes[line.target]
            if not page.is_steer(note["target"]):
                by_item.setdefault(item["id"], []).append(line)
        elif line.token != DELETE and not page.is_steer(line.target):
            if line.token != NO_CHOICE or line.text or seen.count(line.target) > 1:
                by_item.setdefault(page.owner(line.target)["id"], []).append(line)
    return by_item


def _set_state(item: dict, after: str, n: int, lines: list[Line]) -> None:
    before = item.get("state", "open")
    item["state"] = after
    if after not in SETTLED:
        item.pop("settled", None)
    elif before != after:
        item["settled"] = {"by": "mark", "round": n, "signal": lines[0].token}


def apply_response(doc: dict, raw: str, received: str, ids: dict, nodes: dict) -> dict:
    """Change `doc` in memory and answer what happened. The document stays valid or a Refusal is raised."""
    page = _Page(doc, ids, nodes)
    n = page.current["n"]
    lines = parse_response(raw, page)
    signals: dict[int, dict] = {}
    result = {"settled_by_mark": [], "needs_reading": [], "reopened": [], "conflicts": [], "steers": []}

    for item_id, group in _table_lines(lines, page).items():
        item = page.items[item_id]
        before = item.get("state", "open")
        after = apply_mark_table(before, group, (item.get("settled") or {}).get("signal"))
        for line in group:
            signal = {"target": line.target, "item": item_id, "mark": None if line.token in (NO_CHOICE, EDIT) else line.token,
                      "note": None, "text": line.text, "conflict": len(group) > 1}
            if line.token == EDIT:
                _edit(page.notes[line.target][1], line)
                signal.update(note=line.target, action=EDIT)
            elif line.text:
                signal["note"] = _write_note(item, line.target, line.text, n)
            signals[line.number] = signal
        _set_state(item, after, n, group)
        for line in group:
            signals[line.number].update(state=after, reopened=before in SETTLED and after == "open")
        if before != after:
            if after in result:
                result[after].append(item_id)
            if before in SETTLED and after == "open":
                result["reopened"].append(item_id)
        if len(group) > 1:
            result["conflicts"].append(item_id)

    for line in lines:
        if line.number in signals:
            continue
        if line.token == EDIT:
            item, note = page.notes[line.target]
            signals[line.number] = {"target": line.target, "item": item["id"], "mark": None, "note": line.target,
                                    "text": _edit(note, line), "steer": True, "action": EDIT}
        elif line.token == DELETE:
            item, note = page.notes[line.target]
            note["deleted"] = True
            rests_on_it = (item.get("settled") or {}).get("signal") == line.target and item.get("state") == "settled_by_note"
            if rests_on_it:
                _set_state(item, "open", n, [])
                result["reopened"].append(item["id"])
            signals[line.number] = {"target": line.target, "item": item["id"], "mark": None, "note": line.target,
                                    "text": None, "action": DELETE, "state": item.get("state", "open"), "reopened": rests_on_it}
        elif line.text:
            item = _steer_home(page, line.target, n)
            signals[line.number] = {"target": line.target, "item": item["id"], "mark": None, "text": line.text,
                                    "note": _write_note(item, line.target, line.text, n), "steer": True}
            result["steers"].append(line.target)

    if not signals:
        raise Refusal("no-signal", "item response, field raw: the response holds no signal: no mark and no note")
    ordered = [signals[number] for number in sorted(signals)]
    for signal in ordered:
        signal["stamp"] = invariants.ingest_stamp(doc["session"]["id"], n, received, raw, signal)
    page.current["responses"] = [*(page.current.get("responses") or []), {"received": received, "raw": raw, "signals": ordered}]
    return {"round": n, "signals": ordered, **result}


def _read_raw(path: str) -> str:
    try:
        return Path(path).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise Refusal("unreadable", f"raw response {path}: {error}") from error


def cmd_ingest(args, *, check, check_changed, elements, save_copy) -> dict:
    """The verb. `check`, `check_changed`, `elements` and `save_copy` are the engine's own checks and copy."""
    raw = _read_raw(args.raw_file)
    doc, _ = check(args.document)
    _, ids, nodes = elements(doc)
    settled_before = invariants.settled_rounds(doc)
    received = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = apply_response(doc, raw, received, ids, nodes)
    check_changed(doc)
    document = Path(args.document)
    inject.write_if_changed(document, json.dumps(doc, indent=2, ensure_ascii=False).encode("utf-8"))
    if invariants.settled_rounds(doc) != settled_before:
        save_copy(document, doc)
    return {"ok": True, "verb": "ingest", **answer}
