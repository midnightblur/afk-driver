"""Notes and replies (CMP-2): one row per note with the answers that stand in it, newest round first.

Display only. The human writes a note as a native lavish annotation; the poll turns it into a note line.
Every note comes from the session list (ADR-0001 design). The session table (`notes-and-replies`) holds
every row of the session: each note, card notes included, and each answer that stands in no note's row.
A note on a card, and an answer about a card, is also a row on that card (`card-notes`).
An answer stands in the row of each note it names (`notes`); on a format 0 page, by its `about` list.
Each row has an HTML id. A row of a card has `ROW_PREFIX` + key on the card and `SESSION_PREFIX` + key
as its copy of the session table. A row of no card has `ROW_PREFIX` + key there. `row_targets` names the element
that an annotation on a row stands for.
On a version 2 page (`_plain`) no visible text and no hover text holds a raw element id or a round code: each
element reads as its label, a round as "Round 3", a row number as `3.1` and its hover text as `note 1 of round 3`. Versions 0 and 1 show as before.
A page build renders the session table before the cards: it reads the rows anew, and each card of that build reads
the same rows, so a build indexes the elements of the document once.
"""

from html import escape
from typing import NamedTuple

from registry import register_component, walk
from schema.note_rules import round_target
from shell import parts_v2
from shell.page import V2, round_colour
from shell.rounds import round_chip

ROW_PREFIX = "afkv2-nr-"
SESSION_PREFIX = "afkv2-ns-"
TEXT_CLASS = "afkv2-nr-text"
DIM_CLASS = "afkv2-nr-dim"
CHANGED_CLASS = "afkv2-nr-changed"
CARD_TABLE = " afkv2-nr-table--card"
OPEN_ROUNDS = 2
LABEL_LIMIT = 60
NOTED_TEXT_COLUMN = "Noted text"
CARD_COLUMNS = ("#", "Where you wrote it", NOTED_TEXT_COLUMN, "Your note", "My answer / what changed")
SESSION_COLUMNS = (*CARD_COLUMNS, "Open")


class Row(NamedTuple):
    """One row. A loaded component module is in no package, so a dataclass cannot read its annotations.
    `key` is the note id, or `reply-<round>-<k>`; `answers` holds the (round, index) of each answer shown."""
    round: int
    key: str
    number: str
    title: str
    cells: list
    link: str
    home: str | None
    target: str | None
    is_note: bool
    answers: tuple


def _short(text: str) -> str:
    words = " ".join(text.split())
    return words if len(words) <= LABEL_LIMIT else words[:LABEL_LIMIT - 1] + "…"


def _label(part: dict) -> str | None:
    props = part.get("props") or {}
    for key in ("title", "label", "text"):
        if isinstance(props.get(key), str) and props[key].strip():
            return _short(props[key])
    return None


def _elements(doc: dict) -> dict:
    """Every element id: `{"item": the card that holds it or None, "label", "map": the map title of a node}`.
    A round banner also has `"round"`: its round number."""
    found = {round_target(r["n"]): {"item": None, "label": f"Round {r['n']}", "map": None, "round": r["n"]}
             for r in doc["rounds"]}

    def add_tree(component, item, root_is_map=False):
        for path, part in walk(component):
            if part.get("id"):
                found[part["id"]] = {"item": item, "label": _label(part), "map": None}
            if part["type"] == "map" or (root_is_map and not path):
                title = _label(part) or part.get("id") or "the map"
                for node in (part.get("props") or {}).get("nodes") or []:
                    label = node.get("label")
                    found[node["id"]] = {"item": item, "label": _short(label) if isinstance(label, str) else None,
                                         "map": title}

    for map_ in doc.get("maps") or []:
        add_tree(map_, None, root_is_map=True)
    for round_ in doc["rounds"]:
        for item in round_["items"]:
            found[item["id"]] = {"item": item, "label": None, "map": None}
            add_tree(item["body"], item)
    if _plain(doc):
        _add_parts(doc, found)
    return found


def _plain(doc: dict) -> bool:
    return doc["schema"] == V2


def _add_parts(doc: dict, found: dict) -> None:
    """Version 2: each card and each entry of the page parts (a section, a question for others...) reads as its
    `visible_label`; a part of a card with no label of its own reads as its card. An entry is a part of no
    card."""
    parts = {entry["id"] for kind in parts_v2.ENTRY_LISTS for entry in doc.get(kind) or []}
    parts |= {option["id"] for question in doc.get("questions") or []
              for option in (question.get("choices") or {}).get("options") or []}
    for element in parts:
        found.setdefault(element, {"item": None, "label": parts_v2.visible_label(doc, "element", element),
                                   "map": None, "part": True})
    for entry in found.values():
        if entry["item"] is not None and entry["label"] is None:
            entry["label"] = parts_v2.visible_label(doc, "element", entry["item"]["id"])


def _is_steer(item: dict | None, note: dict, elements: dict) -> bool:
    """A note on the round is a steer; so is a note on a card whose target is a map, a map node or no card's part."""
    if item is None:
        return True
    where = elements.get(note["target"])
    return where is not None and (where["map"] is not None or where["item"] is None)


def _notes(doc: dict) -> list[tuple[dict | None, dict]]:
    """(the card or None, note) for every live note of the session list, in its order. A note names its card
    in `item`; a steer names none."""
    cards = {item["id"]: item for r in doc["rounds"] for item in r["items"]}
    return [(cards.get(note.get("item")), note) for note in doc.get("notes") or [] if not note["deleted"]]


def _about_matches(reply: dict, n: int, notes: list[tuple[dict | None, dict]]) -> list[str]:
    """Format 0: the notes whose target, card id or note id the reply's `about` holds, in the reply's own
    round first, then in the round before."""
    about = set(reply.get("about") or [])
    for look in (n, n - 1):
        matched = [note["id"] for item, note in notes if note["round"] == look
                   and about & {note["target"], note["id"], *([item["id"]] if item else [])}]
        if matched:
            return matched
    return []


def _pairs(doc: dict, notes: list[tuple[dict | None, dict]]) -> tuple[dict, list[tuple[int, int, dict]]]:
    """Answers by note id as (round, index, answer), and the answers that stand in no note's row.

    An answer with `notes` stands in the row of each live note it names. An answer with only `about`, read
    on format 0 pages, pairs the format 0 way (`_about_matches`)."""
    live = {note["id"] for _, note in notes}
    by_note, alone = {}, []
    for round_ in doc["rounds"]:
        n = round_["n"]
        for index, reply in enumerate(round_.get("replies") or []):
            if reply.get("notes"):
                matched = [note_id for note_id in dict.fromkeys(reply["notes"]) if note_id in live]
            else:
                matched = _about_matches(reply, n, notes)
            for note_id in matched:
                by_note.setdefault(note_id, []).append((n, index, reply))
            if not matched:
                alone.append((n, index, reply))
    return by_note, alone


def _raw(element: str) -> str:
    return element


def _namer(doc: dict, elements: dict):
    """The words for an element with no label of its own, and the hover text of a link to an element: the raw id
    on versions 0 and 1; on version 2 its label in `elements`, else its `visible_label`."""
    if not _plain(doc):
        return _raw
    return lambda element: ((elements.get(element) or {}).get("label")
                            or parts_v2.visible_label(doc, "element", element))


def _where(item: dict | None, note: dict, elements: dict, name=_raw) -> str:
    target = elements.get(note["target"]) or {"item": item, "label": None, "map": None}
    if target.get("round") or target.get("part"):
        return escape(target["label"])
    if _is_steer(item, note, elements):
        place = f'Map: {escape(target["map"] or target["label"] or name(note["target"]))}'
        if target["map"] is not None:
            place += f' <span class="{DIM_CLASS}">· {escape(target["label"] or name(note["target"]))}</span>'
        return place
    if note["target"] == item["id"]:
        return "The card"
    return escape(target["label"] or name(note["target"]))


def _link(element: str, words: str, name=_raw) -> str:
    return f'<a href="#{escape(element)}" title="{escape(name(element))}" data-lavish-action="afkv2-nr-link">{words}</a>'


def change_links(reply: dict, elements: dict, name=_raw) -> str:
    """One link to each element in the answer's `changed` list, in its order; nothing for an empty list. `name`
    gives the words of an element with no label and the hover text (`_namer`)."""
    changed = list(dict.fromkeys(reply.get("changed") or []))
    if not changed:
        return ""
    links = ", ".join(_link(element, escape((elements.get(element) or {}).get("label") or name(element)), name)
                      for element in changed)
    return f'<p class="{CHANGED_CLASS}">Changed: {links}</p>'


def _answer(replies: list[dict], elements: dict, name=_raw) -> str:
    if not replies:
        return f'<span class="{DIM_CLASS}">No answer yet</span>'
    return "".join(f'<p class="{TEXT_CLASS}">{escape(reply["text"])}</p>{change_links(reply, elements, name)}'
                   for reply in replies)


def _noted(note: dict) -> str:
    quote = note.get("quote")
    return f'<span class="{TEXT_CLASS}">{escape(quote)}</span>' if quote else ""


def _reply_home(reply: dict, elements: dict, notes: list[tuple[dict, dict]]) -> str | None:
    """The card that an answer in no note's row is about: the first card, card element or note in its
    `notes`, then in its `about`."""
    by_note = {note["id"]: (item, note) for item, note in notes}
    for about in [*(reply.get("notes") or []), *(reply.get("about") or [])]:
        if about in by_note:
            item, note = by_note[about]
            return None if _is_steer(item, note, elements) else item["id"]
        where = elements.get(about)
        if where and where["item"] is not None and where["map"] is None:
            return where["item"]["id"]
    return None


def _rows(doc: dict) -> list[Row]:
    """Every row of the page, in document order: the notes, then the answers that stand in no note's row."""
    elements = _elements(doc)
    name = _namer(doc, elements)
    notes = _notes(doc)
    by_note, alone = _pairs(doc, notes)
    counts: dict[int, int] = {}
    note_counts: dict[int, int] = {}

    def number(n: int) -> str:
        counts[n] = counts.get(n, 0) + 1
        return f"{n}.{counts[n]}" if _plain(doc) else f"R{n}.{counts[n]}"

    def note_title(note: dict) -> str:
        """The raw note id on versions 0 and 1; on version 2 `note <k> of round <n>`."""
        n = note["round"]
        note_counts[n] = note_counts.get(n, 0) + 1
        return f"note {note_counts[n]} of round {n}" if _plain(doc) else note["id"]

    rows = []
    for item, note in notes:
        n, steer = note["round"], _is_steer(item, note, elements)
        answers = by_note.get(note["id"], [])
        cells = [_where(item, note, elements, name), _noted(note),
                 f'<q class="{TEXT_CLASS}">{escape(note["text"])}</q>',
                 _answer([reply for _, _, reply in answers], elements, name)]
        place = elements.get(note["target"]) or {}
        words = "Open round" if place.get("round") else "Open" if place.get("part") else "Open map"
        link = _link(note["target"], words, name) if steer else _link(item["id"], "Open card", name)
        rows.append(Row(n, note["id"], number(n), note_title(note), cells, link, None if steer else item["id"],
                        note["target"] if steer else item["id"], True, tuple((r, i) for r, i, _ in answers)))
    for n, index, reply in alone:
        about = reply.get("about") or []
        home = _reply_home(reply, elements, notes)
        cells = [f'<span class="{DIM_CLASS}">From me</span>', "", "", _answer([reply], elements, name)]
        link = _link(about[0], "Open", name) if about else _link(home, "Open card", name) if home else ""
        rows.append(Row(n, f"reply-{n}-{index + 1}", number(n), f"reply {index + 1} of round {n}", cells, link,
                        home, home, False, ((n, index),)))
    return rows


_built: dict = {"doc": None, "rows": []}


def _fresh_rows(doc: dict) -> list[Row]:
    """The rows of the document, read anew; a card of the same document object reads them again from `_built`."""
    _built["doc"], _built["rows"] = doc, _rows(doc)
    return _built["rows"]


def _build_rows(doc: dict) -> list[Row]:
    return _built["rows"] if _built["doc"] is doc else _fresh_rows(doc)


def _session_id(row: Row) -> str:
    """A row on a card keeps `afkv2-nr-` on the card; its session table copy takes `afkv2-ns-`."""
    return (SESSION_PREFIX if row.home else ROW_PREFIX) + row.key


def _tr(row: Row, row_id: str, colour: str, link: bool) -> str:
    cells = [*row.cells, row.link] if link else row.cells
    tds = "".join(f"<td>{cell}</td>" for cell in cells)
    return (f'<tr class="afkv2-nr-row" id="{escape(row_id)}" style="--afkv2-round: {escape(colour)}">'
            f'<td class="afkv2-nr-num"><span title="{escape(row.title)}">{row.number}</span></td>{tds}</tr>')


def _count(k: int, word: str) -> str:
    return f"{k} {word}" if k == 1 else f"{k} {word}s"


def _table(columns: tuple, body: str, modifier: str = "") -> str:
    head = "".join(f"<th>{escape(name)}</th>" for name in columns)
    return f'<table class="afkv2-nr-table{modifier}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _count_line(round_: dict, rows: list[Row], plain: bool) -> str:
    """`R-<n> Round <n> — <k> notes from you, <m> answers from me`: the notes and the answers the rows show.
    `plain` (version 2): the chip reads `Round <n>`, once."""
    n = round_["n"]
    notes = sum(row.is_note for row in rows)
    answers = len({key for row in rows for key in row.answers})
    words = [_count(notes, "note") + " from you"] if notes else []
    if answers:
        words.append(_count(answers, "answer") + " from me")
    if plain:
        return f'{round_chip(n, f"Round {n}", colour=round_colour(round_))} — {", ".join(words)}'
    return f'{round_chip(n, f"R-{n}", colour=round_colour(round_))} Round {n} — {", ".join(words)}'


def _session_rows(round_: dict, rows: list[Row]) -> str:
    return "".join(_tr(row, _session_id(row), round_colour(round_), True) for row in rows)


def _group(round_: dict, rows: list[Row], plain: bool) -> str:
    """The group row of an open round, then its rows."""
    n = round_["n"]
    head = (f'<tr class="afkv2-nr-group" id="{ROW_PREFIX}round-{n}" data-afkv2-nr-round="{n}" '
            f'style="--afkv2-round: {escape(round_colour(round_))}"><td colspan="{len(SESSION_COLUMNS)}">'
            f'{_count_line(round_, rows, plain)}</td></tr>')
    return head + _session_rows(round_, rows)


def _closed_group(round_: dict, rows: list[Row], plain: bool) -> str:
    """An older round: a closed fold whose summary is its count line; one click opens it."""
    n = round_["n"]
    return (f'<details class="afkv2-nr-earlier" id="{ROW_PREFIX}round-{n}" data-afkv2-nr-round="{n}" '
            f'data-afkv2-fold="notes-round-{n}" style="--afkv2-round: {escape(round_colour(round_))}">'
            f'<summary>{_count_line(round_, rows, plain)}</summary>'
            f'{_table(SESSION_COLUMNS, _session_rows(round_, rows))}</details>')


def render_card_notes(props, children):
    """The rows of one card, newest round first, in a table without the link column."""
    doc = props["document"]
    colours = {r["n"]: round_colour(r) for r in doc["rounds"]}
    rows = sorted((row for row in _build_rows(doc) if row.home == props["item"]), key=lambda row: -row.round)
    if not rows:
        return "".join(children)
    body = "".join(_tr(row, ROW_PREFIX + row.key, colours[row.round], False) for row in rows)
    return _table(CARD_COLUMNS, body, CARD_TABLE) + "".join(children)


def render_notes_replies(props, children):
    """Every row of the session, grouped by round, newest first. The current round and the one before are
    open; each older round is its own closed group."""
    doc = props["document"]
    by_round: dict[int, list[Row]] = {}
    for row in _fresh_rows(doc):
        by_round.setdefault(row.round, []).append(row)
    if not by_round:
        return "".join(children)
    current = next(r["n"] for r in doc["rounds"] if r["state"] == "current")
    rounds = sorted((r for r in doc["rounds"] if r["n"] in by_round), key=lambda r: -r["n"])
    plain = _plain(doc)
    recent = [_group(r, by_round[r["n"]], plain) for r in rounds if r["n"] > current - OPEN_ROUNDS]
    older = [_closed_group(r, by_round[r["n"]], plain) for r in rounds if r["n"] <= current - OPEN_ROUNDS]
    html = ('<h2 class="afkv2-section-h">Notes on the whole session</h2>'
            '<p class="afkv2-nr-intro">Every note and every answer of the session, newest round first. A note '
            'on a card also stands under that card.</p>')
    if recent:
        html += _table(SESSION_COLUMNS, "".join(recent))
    return html + "".join(older) + "".join(children)


def row_targets(props) -> dict:
    """The element that an annotation on a row stands for: the card of a note or of an answer about a card,
    in both its rows, or the node of a steer. An answer that names no card, and a group row, stand for no
    element."""
    found = {}
    for row in _rows(props["document"]):
        if row.target:
            found[ROW_PREFIX + row.key] = row.target
            if row.home:
                found[SESSION_PREFIX + row.key] = row.target
    return found


register_component("notes-and-replies", {
    "type": "object", "additionalProperties": False, "required": ["document"],
    "properties": {"document": {"type": "object"}},
}, render_notes_replies, targets=row_targets)

register_component("card-notes", {
    "type": "object", "additionalProperties": False, "required": ["document", "item"],
    "properties": {"document": {"type": "object"}, "item": {"type": "string"}},
}, render_card_notes)
