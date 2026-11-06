"""Write one raw response into the page document, with per-item signals and no judgement (SDD §6).

The raw grammars have one home, `prompt_lines.py`; this module is their one parser, by the format of the page
file. Format 0: first line `[round R-n]`, then `<id> <token>` or `<id> <token> | <note>`, an em dash for no
choice. `<id>` is an element id, or a note id with the token `edit` or `delete`. A later line continues the
note unless it reads as a line of a known id with a token that id takes. Format 1: a mark line, a note entry
or an edit with its words indented 2 spaces, and a delete line. A format 1 mark takes the first note entry
of its element, as a format 0 mark shares the line of its first note: the mark table reads both the same.
Format 2: the format 1 lines and a tick line, `<question id> tick <option id> ...`. A tick is a signal in
`questions_to_read` and changes no state (ADR-0004 design); one that names no question, no option, an option
twice, more options than its question takes, or a question ticked twice in one send is refused `bad-tick`.

Each note line or entry is one note: the page sends one per lavish annotation. Every note goes into
the session list (ADR-0001 design). A note on a card element names that card: `N-<round>-<item>-<k>`. A
steer, a note on a map, a map node, a round banner or another element that no card holds, names no card:
`N-<round>-<target>-<k>`. k counts 1, 2, 3 per card or target in the round (`schema/note_rules.py`).
The answer's `notes` lists the ids of the new notes.

On a format 2 page a note on a section, story, example or question, or on a part of one, is a plain note
of that entry: `N-<round>-<entry>-<k>`, never a steer. A signal on a question, a tick or a note, also goes into
`questions_to_read`. A note or an edit on a settled card with no mark leaves the card settled, and its note id
goes into `settled_notes_to_read` for the agent's reading (ADR-0005 design); a mark on it follows the table.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from afkv2_config import Refusal

from registry import walk
from schema import invariants, note_rules
from shell import inject

from prompt_lines import FORMAT_0, FORMAT_2, INDENT, NO_CHOICE, NOTE_SEPARATOR, NOTE_WORD, QUOTE_LINE, TICK_WORD

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
    quote: str | None = None
    choices: list[str] | None = None

    @property
    def noted(self) -> bool:
        """The line holds a note: words, or only the text it was on."""
        return bool(self.text) or bool(self.quote)


def _settles(token: str) -> bool:
    return token in SETTLING or bool(LETTER.fullmatch(token))


def apply_mark_table(state: str, lines: list[Line], settled_signal: str | None) -> str:
    """The next point state for the lines of one item (SDD §6, ADR-0002 design). Each line holds a signal."""
    marks = [line.token for line in lines if line.token != NO_CHOICE]
    lone = len(lines) == 1 and len(marks) == 1 and not lines[0].noted and _settles(marks[0])
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
        self.notes = {note["id"]: (self.items.get(note.get("item")), note) for note in doc.get("notes") or []}
        self.v2 = doc["schema"] == FORMAT_2
        self.questions = {question["id"]: question for question in doc.get("questions") or []}

    def owner(self, target: str) -> dict | None:
        """The item that holds an element; None for an element of the `maps` list and for a round banner."""
        path = self.ids[target]
        if path[2:3] != ("items",):
            return None
        return self.doc["rounds"][path[1]]["items"][path[3]]

    def entry(self, target: str) -> dict | None:
        """The format 2 entry that holds an element: a section, story, example or question; None elsewhere."""
        path = self.ids.get(target, ())
        return self.doc[path[0]][path[1]] if path[:1] and path[0] in invariants.ENTRY_LISTS else None

    def is_steer(self, target: str) -> bool:
        return self.entry(target) is None and (target in self.nodes or self.owner(target) is None)

    def on_card(self, target: str) -> bool:
        return self.entry(target) is None and not self.is_steer(target)

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


def parse_response(raw: str, page: _Page, page_format: str = FORMAT_0) -> list[Line]:
    """The lines of a response in the grammar of `page_format`. A refusal names the line the grammar cannot read."""
    rows = [row.removesuffix("\r") for row in raw.split("\n")]
    header = HEADER.fullmatch(rows[0])
    if not header:
        raise Refusal("bad-response", f"item response, field raw: line 1 must be [round R-n], found {rows[0]!r}")
    n = page.current["n"]
    if int(header.group(1)) != n:
        raise Refusal("stale-round", f"item response, field raw: the response answers round {header.group(1)}; "
                                     f"the current round is round {n}")
    if page_format != FORMAT_0:
        return _entries(rows, page)
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


def _bad_line(number: int, row: str) -> Refusal:
    return Refusal("bad-response", f"item response, field raw: line {number} is no line of a known element: {row!r}")


def _entries(rows: list[str], page: _Page) -> list[Line]:
    """The lines of a format 1 response. A note entry and an edit take the indented lines after them; a note
    entry's first indented line may be its `on:` line."""
    lines: list[Line] = []
    open_: tuple[Line, list[str]] | None = None
    for number, row in enumerate(rows[1:], start=2):
        if open_ is not None and row.startswith(INDENT):
            line, words = open_
            if not words and line.quote is None and line.token == NO_CHOICE and row.startswith(QUOTE_LINE) \
                    and row.endswith('"') and len(row) > len(QUOTE_LINE):
                line.quote = row[len(QUOTE_LINE):-1]
            else:
                words.append(row[len(INDENT):])
            continue
        if open_ is not None:
            open_[0].text = "\n".join(open_[1]).rstrip("\n")
            open_ = None
        words = row.split(" ")
        if page.v2 and len(words) > 1 and words[1] == TICK_WORD:
            lines.append(_tick(words, number, page, lines))
            continue
        target, _, token = row.rpartition(" ")
        head, _, word = target.rpartition(" ")
        if word == NOTE_WORD and token.isdigit() and head in page.ids and head not in page.notes:
            open_ = (Line(head, NO_CHOICE, None, number), [])
            lines.append(open_[0])
        elif token == EDIT and target in page.notes:
            open_ = (Line(target, EDIT, None, number), [])
            lines.append(open_[0])
        elif page.accepts(target, token) and token != EDIT:
            lines.append(Line(target, token, None, number))
        elif row.strip():
            raise _bad_line(number, row)
    if open_ is not None:
        open_[0].text = "\n".join(open_[1]).rstrip("\n")
    return _marks_take_first_notes(lines)


def _tick(words: list[str], number: int, page: _Page, lines: list[Line]) -> Line:
    """A format 2 tick line: a question for others and the option ids ticked on it."""
    at = f"item response, field raw: line {number}"
    question, chosen = page.questions.get(words[0]), words[2:]
    if question is None:
        raise Refusal("bad-tick", f"{at} ticks {words[0]!r}, which is no question for others")
    choices = question.get("choices") or {}
    known = {option["id"] for option in choices.get("options") or []}
    unknown = [choice for choice in chosen if choice not in known]
    twice = sorted({choice for choice in chosen if chosen.count(choice) > 1})
    if not chosen:
        raise Refusal("bad-tick", f"{at}: a tick names at least 1 option id of {words[0]!r}")
    if unknown:
        raise Refusal("bad-tick", f"{at}: {', '.join(map(repr, unknown))} is no option of {words[0]!r}")
    if twice:
        raise Refusal("bad-tick", f"{at} names {', '.join(map(repr, twice))} twice")
    if len(chosen) > 1 and not choices.get("several"):
        raise Refusal("bad-tick", f"{at}: {words[0]!r} takes 1 option; the tick names {len(chosen)}")
    if any(line.token == TICK_WORD and line.target == words[0] for line in lines):
        raise Refusal("bad-tick", f"{at} ticks {words[0]!r} a second time; a send holds 1 tick per question")
    return Line(words[0], TICK_WORD, None, number, choices=chosen)


def _marks_take_first_notes(lines: list[Line]) -> list[Line]:
    """A mark line takes the words and noted text of the first note entry on its element, as in format 0."""
    marks = {line.target: line for line in lines
             if line.token not in (NO_CHOICE, EDIT, DELETE, TICK_WORD) and line.text is None}
    kept = []
    for line in lines:
        mark = marks.get(line.target)
        if line.token == NO_CHOICE and mark is not None and mark.text is None and line.text is not None:
            mark.text, mark.quote = line.text, line.quote
            continue
        kept.append(line)
    return kept


def write_session_note(doc: dict, n: int, target: str, item: str | None, text: str, earlier: dict,
                       quote: str | None = None) -> tuple[str, bool]:
    """(the note id, whether the note is new): one note in the session list (ADR-0001 design), with the next k
    of its owner in round n; the owner is its card, or its target for a steer. `quote` is the text the human
    selected, apart from their words. A live note of an earlier response with the same round, target, words
    and noted text is that note: a send that comes twice adds nothing."""
    notes = doc.get("notes") or []
    key = (n, target, text, quote)
    for note in notes:
        if note["id"] in earlier and not note["deleted"] and (note["round"], note["target"], note["text"], note.get("quote")) == key:
            return note["id"], False
    note_id = note_rules.next_note_id(notes, n, item or target)
    note = {"id": note_id, "round": n, "target": target, "item": item, "text": text, "deleted": False}
    if quote is not None:
        note["quote"] = quote
    doc["notes"] = [*notes, note]
    return note_id, True


def _edit(note: dict, line: Line) -> str:
    if not line.text:
        raise Refusal("bad-response", f"item response, field raw: line {line.number} edits a note to no text")
    note.update(text=line.text, deleted=False)
    return line.text


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
            if item is not None and page.on_card(note["target"]):
                by_item.setdefault(item["id"], []).append(line)
        elif line.token not in (DELETE, TICK_WORD) and page.on_card(line.target):
            if line.token != NO_CHOICE or line.noted or seen.count(line.target) > 1:
                by_item.setdefault(page.owner(line.target)["id"], []).append(line)
    return by_item


def _set_state(item: dict, after: str, n: int, lines: list[Line]) -> None:
    before = item.get("state", "open")
    item["state"] = after
    if after not in SETTLED:
        item.pop("settled", None)
    elif before != after:
        item["settled"] = {"by": "mark", "round": n, "signal": lines[0].token}


def apply_response(doc: dict, raw: str, received: str, ids: dict, nodes: dict, page_format: str | None = None) -> dict:
    """Change `doc` in memory and answer what happened. The document stays valid or a Refusal is raised.
    `page_format` is the schema value of the page file, by default the document's own."""
    page = _Page(doc, ids, nodes)
    n = page.current["n"]
    lines = parse_response(raw, page, page_format or doc["schema"])
    signals: dict[int, dict] = {}
    result = {"settled_by_mark": [], "needs_reading": [], "reopened": [], "conflicts": [], "steers": [], "notes": []}
    if page.v2:
        result.update(questions_to_read=[], settled_notes_to_read=[])

    def write(target: str, item: str | None, line: Line) -> str:
        note_id, new = write_session_note(doc, n, target, item, line.text or "", page.notes, line.quote)
        if new:
            result["notes"].append(note_id)
        return note_id

    for item_id, group in _table_lines(lines, page).items():
        item = page.items[item_id]
        before = item.get("state", "open")
        waits = page.v2 and before in SETTLED and all(line.token in (NO_CHOICE, EDIT) for line in group)
        after = before if waits else apply_mark_table(before, group, (item.get("settled") or {}).get("signal"))
        for line in group:
            signal = {"target": line.target, "item": item_id, "mark": None if line.token in (NO_CHOICE, EDIT) else line.token,
                      "note": None, "text": line.text, "conflict": len(group) > 1 and not waits, **_quote(line)}
            if line.token == EDIT:
                _edit(page.notes[line.target][1], line)
                signal.update(note=line.target, action=EDIT)
            elif line.noted:
                signal["note"] = write(line.target, item_id, line)
            if waits and signal["note"]:
                result["settled_notes_to_read"].append(signal["note"])
            signals[line.number] = signal
        _set_state(item, after, n, group)
        for line in group:
            signals[line.number].update(state=after, reopened=before in SETTLED and after == "open")
        if before != after:
            if after in result:
                result[after].append(item_id)
            if before in SETTLED and after == "open":
                result["reopened"].append(item_id)
        if len(group) > 1 and not waits:
            result["conflicts"].append(item_id)

    for line in lines:
        if line.number in signals:
            continue
        entry = page.entry(page.notes[line.target][1]["target"] if line.token in (EDIT, DELETE) else line.target)
        owner = {} if entry is None else {"item": entry["id"]}
        if line.token == TICK_WORD:
            signals[line.number] = {"target": line.target, "item": line.target, "mark": invariants.TICK,
                                    "choices": line.choices, "note": None, "text": None}
        elif line.token == EDIT:
            item, note = page.notes[line.target]
            signals[line.number] = {"target": line.target, "item": item and item["id"], "mark": None,
                                    "note": line.target, "text": _edit(note, line), "steer": True, "action": EDIT}
            if entry is not None:
                del signals[line.number]["steer"]
        elif line.token == DELETE:
            item, note = page.notes[line.target]
            note["deleted"] = True
            settled = (item or {}).get("settled") or {}
            rests_on_it = settled.get("signal") == line.target and item.get("state") == "settled_by_note"
            if rests_on_it:
                _set_state(item, "open", n, [])
                result["reopened"].append(item["id"])
            signals[line.number] = {"target": line.target, "item": item and item["id"], "mark": None, "note": line.target,
                                    "text": None, "action": DELETE, "state": item.get("state", "open") if item else None,
                                    "reopened": rests_on_it}
        elif line.noted and entry is not None:
            signals[line.number] = {"target": line.target, "item": entry["id"], "mark": None, "text": line.text,
                                    "note": write(line.target, entry["id"], line), **_quote(line)}
        elif line.noted:
            signals[line.number] = {"target": line.target, "item": None, "mark": None, "text": line.text,
                                    "note": write(line.target, None, line), "steer": True, **_quote(line)}
            result["steers"].append(line.target)
        else:
            continue
        signals[line.number].update(owner)
        if entry is not None and entry["id"] in page.questions:
            result["questions_to_read"].append(signals[line.number])

    if not signals:
        raise Refusal("no-signal", "item response, field raw: the response holds no signal: no mark and no note")
    ordered = [signals[number] for number in sorted(signals)]
    for signal in ordered:
        signal["stamp"] = invariants.ingest_stamp(doc["session"]["id"], n, received, raw, signal)
    page.current["responses"] = [*(page.current.get("responses") or []), {"received": received, "raw": raw, "signals": ordered}]
    return {"round": n, "signals": ordered, **result}


def _quote(line: Line) -> dict:
    """The noted text of a signal; a format 0 line has none, so its signal keeps its fields."""
    return {"quote": line.quote} if line.quote is not None else {}


def _read_raw(path: str) -> str:
    try:
        return Path(path).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise Refusal("unreadable", f"raw response {path}: {error}") from error


def cmd_ingest(args, *, check, check_changed, elements, save_copy, page_format=None) -> dict:
    """The verb. `check`, `check_changed`, `elements` and `save_copy` are the engine's own checks and copy;
    `page_format` is the schema value of the page file. The document is written in format 1, or 2 as it was."""
    raw = _read_raw(args.raw_file)
    doc, _ = check(args.document)
    _, ids, nodes = elements(doc)
    settled_before = invariants.settled_rounds(doc)
    received = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = apply_response(doc, raw, received, ids, nodes, page_format)
    check_changed(doc)
    document = Path(args.document)
    inject.write_if_changed(document, json.dumps(doc, indent=2, ensure_ascii=False).encode("utf-8"))
    if invariants.settled_rounds(doc) != settled_before:
        save_copy(document, doc)
    return {"ok": True, "verb": "ingest", **answer}
