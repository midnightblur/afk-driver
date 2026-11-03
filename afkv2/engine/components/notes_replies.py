"""Notes and replies (CMP-2): one row per note with the replies that answer it, newest round first.

Display only. The human writes a note as a native lavish annotation; the poll turns it into a note line.
A note on a card, and a reply about a card, is a row on that card (`card-notes`). The slot table
(`notes-and-replies`) holds the rest: the steers (notes on a map or a map node, kept on the round, and older
steers kept on a card), and replies that name no card.
Each row has an HTML id. `row_targets` names the element that an annotation on a row stands for.
"""

from html import escape
from typing import NamedTuple

from registry import register_component, walk
from schema.note_rules import round_target
from shell.page import round_colour

ROW_PREFIX = "afkv2-nr-"
TEXT_CLASS = "afkv2-nr-text"
DIM_CLASS = "afkv2-nr-dim"
CARD_TABLE = " afkv2-nr-table--card"
OPEN_ROUNDS = 2
LABEL_LIMIT = 60
CARD_COLUMNS = ("#", "Where you wrote it", "Your note", "My answer / what changed")
SESSION_COLUMNS = (*CARD_COLUMNS, "Open")


class Row(NamedTuple):
    """One row. A loaded component module is in no package, so a dataclass cannot read its annotations."""
    round: int
    row_id: str
    number: str
    title: str
    cells: list
    link: str
    home: str | None
    target: str | None
    is_note: bool


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
    return found


def _is_steer(item: dict | None, note: dict, elements: dict) -> bool:
    """A note on the round is a steer; so is a note on a card whose target is a map, a map node or no card's part."""
    if item is None:
        return True
    where = elements.get(note["target"])
    return where is not None and (where["map"] is not None or where["item"] is None)


def _notes(doc: dict) -> list[tuple[dict | None, dict]]:
    """(the card or None, note) for every live note, in document order: per round, its cards' notes, then its steers."""
    found = []
    for r in doc["rounds"]:
        found += [(item, note) for item in r["items"] for note in item.get("notes") or []]
        found += [(None, note) for note in r.get("notes") or []]
    return [(item, note) for item, note in found if not note["deleted"]]


def _pairs(doc: dict, notes: list[tuple[dict, dict]]) -> tuple[dict, list[tuple[int, int, dict]]]:
    """Replies by note id, and the replies that answer no note as (round, index, reply).

    A reply answers a note when its `about` holds the note's target, item id or note id. A reply looks
    for such notes in its own round first, then in the round before."""
    by_note, alone = {}, []
    for round_ in doc["rounds"]:
        n = round_["n"]
        for index, reply in enumerate(round_.get("replies") or []):
            about = set(reply.get("about") or [])
            matched = []
            for look in (n, n - 1):
                matched = [note for item, note in notes if note["round"] == look
                           and about & {note["target"], note["id"], *([item["id"]] if item else [])}]
                if matched:
                    break
            for note in matched:
                by_note.setdefault(note["id"], []).append(reply)
            if not matched:
                alone.append((n, index, reply))
    return by_note, alone


def _where(item: dict | None, note: dict, elements: dict) -> str:
    target = elements.get(note["target"]) or {"item": item, "label": None, "map": None}
    if target.get("round"):
        return escape(target["label"])
    if _is_steer(item, note, elements):
        place = f'Map: {escape(target["map"] or target["label"] or note["target"])}'
        if target["map"] is not None:
            place += f' <span class="{DIM_CLASS}">· {escape(target["label"] or note["target"])}</span>'
        return place
    if note["target"] == item["id"]:
        return "The card"
    return escape(target["label"] or note["target"])


def _link(element: str, words: str) -> str:
    return f'<a href="#{escape(element)}" title="{escape(element)}">{words}</a>'


def _answer(replies: list[dict]) -> str:
    if not replies:
        return f'<span class="{DIM_CLASS}">No answer yet</span>'
    return "".join(f'<p class="{TEXT_CLASS}">{escape(reply["text"])}</p>' for reply in replies)


def _reply_home(reply: dict, elements: dict, notes: list[tuple[dict, dict]]) -> str | None:
    """The card that a reply which answers no note is about: the first card, card element or note in `about`."""
    by_note = {note["id"]: (item, note) for item, note in notes}
    for about in reply.get("about") or []:
        if about in by_note:
            item, note = by_note[about]
            return None if _is_steer(item, note, elements) else item["id"]
        where = elements.get(about)
        if where and where["item"] is not None and where["map"] is None:
            return where["item"]["id"]
    return None


def _rows(doc: dict) -> list[Row]:
    """Every row of the page, in document order: the notes, then the replies that answer no note."""
    elements = _elements(doc)
    notes = _notes(doc)
    by_note, alone = _pairs(doc, notes)
    counts: dict[int, int] = {}

    def number(n: int) -> str:
        counts[n] = counts.get(n, 0) + 1
        return f"R{n}.{counts[n]}"

    rows = []
    for item, note in notes:
        n, steer = note["round"], _is_steer(item, note, elements)
        cells = [_where(item, note, elements), f'<q class="{TEXT_CLASS}">{escape(note["text"])}</q>',
                 _answer(by_note.get(note["id"], []))]
        words = "Open round" if (elements.get(note["target"]) or {}).get("round") else "Open map"
        link = _link(note["target"], words) if steer else _link(item["id"], "Open card")
        rows.append(Row(n, ROW_PREFIX + note["id"], number(n), note["id"], cells, link,
                        None if steer else item["id"], note["target"] if steer else item["id"], True))
    for n, index, reply in alone:
        about = reply.get("about") or []
        home = _reply_home(reply, elements, notes)
        cells = [f'<span class="{DIM_CLASS}">From me</span>', "", _answer([reply])]
        rows.append(Row(n, f"{ROW_PREFIX}reply-{n}-{index + 1}", number(n), f"reply {index + 1} of round {n}", cells,
                        _link(about[0], "Open") if about else "", home, home, False))
    return rows


def _tr(row: Row, colour: str, link: bool) -> str:
    cells = [*row.cells, row.link] if link else row.cells
    tds = "".join(f"<td>{cell}</td>" for cell in cells)
    return (f'<tr class="afkv2-nr-row" id="{escape(row.row_id)}" style="--afkv2-round: {escape(colour)}">'
            f'<td class="afkv2-nr-num"><span title="{escape(row.title)}">{row.number}</span></td>{tds}</tr>')


def _count(k: int, word: str) -> str:
    return f"{k} {word}" if k == 1 else f"{k} {word}s"


def _table(columns: tuple, body: str, modifier: str = "") -> str:
    head = "".join(f"<th>{escape(name)}</th>" for name in columns)
    return f'<table class="afkv2-nr-table{modifier}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _group(round_: dict, rows: list[Row]) -> str:
    """The group row of a round, then its rows."""
    n = round_["n"]
    notes = sum(row.is_note for row in rows)
    words = [_count(notes, "note") + " from you"] if notes else []
    if len(rows) > notes:
        words.append(_count(len(rows) - notes, "answer") + " from me")
    head = (f'<tr class="afkv2-nr-group" id="{ROW_PREFIX}round-{n}" data-afkv2-nr-round="{n}" '
            f'style="--afkv2-round: {escape(round_colour(round_))}"><td colspan="{len(SESSION_COLUMNS)}">'
            f'<span class="afkv2-round-chip">R-{n}</span> Round {n} — {", ".join(words)}</td></tr>')
    return head + "".join(_tr(row, round_colour(round_), True) for row in rows)


def render_card_notes(props, children):
    """The rows of one card, newest round first, in a table without the link column."""
    doc = props["document"]
    colours = {r["n"]: round_colour(r) for r in doc["rounds"]}
    rows = sorted((row for row in _rows(doc) if row.home == props["item"]), key=lambda row: -row.round)
    if not rows:
        return "".join(children)
    return _table(CARD_COLUMNS, "".join(_tr(row, colours[row.round], False) for row in rows), CARD_TABLE) + "".join(children)


def render_notes_replies(props, children):
    """The rows that stand on no card, grouped by round, newest first; rounds older than the one before fold."""
    doc = props["document"]
    by_round: dict[int, list[Row]] = {}
    for row in _rows(doc):
        if row.home is None:
            by_round.setdefault(row.round, []).append(row)
    if not by_round:
        return "".join(children)
    current = next(r["n"] for r in doc["rounds"] if r["state"] == "current")
    rounds = sorted((r for r in doc["rounds"] if r["n"] in by_round), key=lambda r: -r["n"])
    recent = [_group(r, by_round[r["n"]]) for r in rounds if r["n"] > current - OPEN_ROUNDS]
    earlier = [r for r in rounds if r["n"] <= current - OPEN_ROUNDS]
    html = ('<h2 class="afkv2-section-h">Notes on the whole session</h2>'
            '<p class="afkv2-nr-intro">Your notes on a map, and my answers that name no card, newest round '
            'first. A note on a card stays on that card.</p>')
    if recent:
        html += _table(SESSION_COLUMNS, "".join(recent))
    if earlier:
        span = f"round {earlier[0]['n']}" if len(earlier) == 1 else f"rounds {earlier[-1]['n']} to {earlier[0]['n']}"
        total = sum(len(by_round[r["n"]]) for r in earlier)
        folded = _table(SESSION_COLUMNS, "".join(_group(r, by_round[r["n"]]) for r in earlier))
        html += (f'<details class="afkv2-nr-earlier" id="{ROW_PREFIX}earlier"><summary>Earlier rounds ({span}, '
                 f'{_count(total, "row")})</summary>{folded}</details>')
    return html + "".join(children)


def row_targets(props) -> dict:
    """The element that an annotation on a row stands for: the card of a note or of a reply about a card, or
    the node of a steer. A reply that names no card, and a group row, stand for no element."""
    return {row.row_id: row.target for row in _rows(props["document"]) if row.target}


register_component("notes-and-replies", {
    "type": "object", "additionalProperties": False, "required": ["document"],
    "properties": {"document": {"type": "object"}},
}, render_notes_replies, targets=row_targets)

register_component("card-notes", {
    "type": "object", "additionalProperties": False, "required": ["document", "item"],
    "properties": {"document": {"type": "object"}, "item": {"type": "string"}},
}, render_card_notes)
