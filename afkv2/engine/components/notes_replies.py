"""Notes and replies (CMP-2): one table, one row per note with the replies that answer it, newest round first.

Display only. The human writes a note as a native lavish annotation; the poll turns it into a note line.
Each row has an HTML id. `row_targets` names the element that an annotation on a row stands for.
"""

from html import escape

from registry import register_component, walk
from shell.page import round_colour

ROW_PREFIX = "afkv2-nr-"
TEXT_CLASS = "afkv2-nr-text"
OPEN_ROUNDS = 2
LABEL_LIMIT = 60
COLUMNS = ("#", "Where you wrote it", "Your note", "My answer / what changed", "Card")


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
    """Every element id: `{"item": the card that holds it or None, "label", "map": the map title of a node}`."""
    found = {}

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


def _is_steer(note: dict, elements: dict) -> bool:
    where = elements.get(note["target"])
    return where is not None and (where["map"] is not None or where["item"] is None)


def _notes(doc: dict) -> list[tuple[dict, dict]]:
    """(item, note) for every live note, in document order."""
    return [(item, note) for r in doc["rounds"] for item in r["items"]
            for note in item.get("notes") or [] if not note["deleted"]]


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
                           and about & {note["target"], item["id"], note["id"]}]
                if matched:
                    break
            for note in matched:
                by_note.setdefault(note["id"], []).append(reply)
            if not matched:
                alone.append((n, index, reply))
    return by_note, alone


def _where(item: dict, note: dict, elements: dict) -> str:
    target = elements.get(note["target"]) or {"item": item, "label": None, "map": None}
    if _is_steer(note, elements):
        place = f'Map: {escape(target["map"] or target["label"] or note["target"])}'
        if target["map"] is not None:
            place += f' <span class="afkv2-nr-dim">· {escape(target["label"] or note["target"])}</span>'
        return place
    place = escape(item.get("title") or item["id"])
    if note["target"] != item["id"]:
        place += f' <span class="afkv2-nr-dim">· {escape(target["label"] or note["target"])}</span>'
    return place


def _link(item: dict, note: dict, elements: dict) -> str:
    if _is_steer(note, elements):
        return f'<a href="#{escape(note["target"])}" title="{escape(note["target"])}">Open map</a>'
    return f'<a href="#{escape(item["id"])}" title="{escape(item["id"])}">Open card</a>'


def _answer(replies: list[dict]) -> str:
    if not replies:
        return '<span class="afkv2-nr-dim">No answer yet</span>'
    return "".join(f'<p class="{TEXT_CLASS}">{escape(reply["text"])}</p>' for reply in replies)


def _row(row_id: str, number: str, title: str, cells: list[str], colour: str) -> str:
    tds = "".join(f"<td>{cell}</td>" for cell in cells)
    return (f'<tr class="afkv2-nr-row" id="{escape(row_id)}" style="--afkv2-round: {escape(colour)}">'
            f'<td class="afkv2-nr-num"><span title="{escape(title)}">{number}</span></td>{tds}</tr>')


def _count(k: int, word: str) -> str:
    return f"{k} {word}" if k == 1 else f"{k} {word}s"


def _group(round_: dict, rows: list[tuple[str, str]]) -> str:
    """The group row of a round and its rows. `rows` is (kind, html), kind `note` or `reply`."""
    n = round_["n"]
    notes = sum(kind == "note" for kind, _ in rows)
    alone = len(rows) - notes
    words = [_count(notes, "note") + " from you"] if notes else []
    if alone:
        words.append(_count(alone, "answer") + " from me")
    head = (f'<tr class="afkv2-nr-group" id="{ROW_PREFIX}round-{n}" data-afkv2-nr-round="{n}" '
            f'style="--afkv2-round: {escape(round_colour(round_))}"><td colspan="{len(COLUMNS)}">'
            f'<span class="afkv2-round-chip">R-{n}</span> Round {n} — {", ".join(words)}</td></tr>')
    return head + "".join(html for _, html in rows)


def _table(groups: list[str]) -> str:
    head = "".join(f"<th>{escape(name)}</th>" for name in COLUMNS)
    return (f'<table class="afkv2-nr-table"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(groups)}</tbody></table>')


def _round_rows(doc: dict) -> dict[int, list[tuple[str, str]]]:
    elements = _elements(doc)
    notes = _notes(doc)
    by_note, alone = _pairs(doc, notes)
    colours = {r["n"]: round_colour(r) for r in doc["rounds"]}
    rows: dict[int, list[tuple[str, str]]] = {}
    for item, note in notes:
        n = note["round"]
        number = f"R{n}.{len(rows.get(n, [])) + 1}"
        cells = [_where(item, note, elements), f'<q class="afkv2-nr-text">{escape(note["text"])}</q>',
                 _answer(by_note.get(note["id"], [])), _link(item, note, elements)]
        rows.setdefault(n, []).append(("note", _row(ROW_PREFIX + note["id"], number, note["id"], cells, colours[n])))
    for n, index, reply in alone:
        number = f"R{n}.{len(rows.get(n, [])) + 1}"
        about = reply.get("about") or []
        link = f'<a href="#{escape(about[0])}" title="{escape(about[0])}">Open</a>' if about else ""
        cells = ['<span class="afkv2-nr-dim">From me</span>', "", _answer([reply]), link]
        rows.setdefault(n, []).append(
            ("reply", _row(f"{ROW_PREFIX}reply-{n}-{index + 1}", number, f"reply {index + 1} of round {n}", cells,
                           colours[n])))
    return rows


def render_notes_replies(props, children):
    doc = props["document"]
    rows = _round_rows(doc)
    if not rows:
        return "".join(children)
    current = next(r["n"] for r in doc["rounds"] if r["state"] == "current")
    rounds = sorted((r for r in doc["rounds"] if r["n"] in rows), key=lambda r: -r["n"])
    recent = [_group(r, rows[r["n"]]) for r in rounds if r["n"] > current - OPEN_ROUNDS]
    earlier = [r for r in rounds if r["n"] <= current - OPEN_ROUNDS]
    html = ('<h2 class="afkv2-section-h">Notes and replies</h2>'
            '<p class="afkv2-nr-intro">Newest rounds come first. Each row is one of your notes, word for word, '
            'with my answer. The last column opens the card.</p>')
    if recent:
        html += _table(recent)
    if earlier:
        span = f"round {earlier[0]['n']}" if len(earlier) == 1 else f"rounds {earlier[-1]['n']} to {earlier[0]['n']}"
        total = sum(len(rows[r["n"]]) for r in earlier)
        html += (f'<details class="afkv2-nr-earlier" id="{ROW_PREFIX}earlier"><summary>Earlier rounds ({span}, '
                 f'{_count(total, "row")})</summary>{_table([_group(r, rows[r["n"]]) for r in earlier])}</details>')
    return html + "".join(children)


def row_targets(props) -> dict:
    """The element that an annotation on a note row stands for: the note's card, or the node of a steer.
    A row of a reply alone, and a group row, stand for no element."""
    doc = props["document"]
    elements = _elements(doc)
    return {ROW_PREFIX + note["id"]: note["target"] if _is_steer(note, elements) else item["id"]
            for item, note in _notes(doc)}


register_component("notes-and-replies", {
    "type": "object", "additionalProperties": False, "required": ["document"],
    "properties": {"document": {"type": "object"}},
}, render_notes_replies, targets=row_targets)
