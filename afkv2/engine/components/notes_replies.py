"""Notes and replies (CMP-2): per round, newest first, each collapsible, the agent's replies on top.

Display only. The human writes a note as a native lavish annotation; the poll turns it into a note line.
"""

from html import escape

from registry import register_component, walk
from shell.page import round_colour


def _map_nodes(doc):
    found = set()
    components = [*(doc.get("maps") or []), *(item["body"] for r in doc["rounds"] for item in r["items"])]
    for component in components:
        for _, part in walk(component):
            if part["type"] == "map":
                found.update(node["id"] for node in (part.get("props") or {}).get("nodes") or [])
    return found


def _reply(reply):
    about = reply.get("about") or []
    line = f'<p class="afkv2-nr-about">About {escape(", ".join(about))}</p>' if about else ""
    return f'<li class="afkv2-nr-reply"><p class="afkv2-nr-text">{escape(reply["text"])}</p>{line}</li>'


def _note(note, nodes):
    note_id, target = escape(note["id"]), escape(note["target"])
    what = f"Steer on {target}" if note["target"] in nodes else f"Note on {target}"
    attrs = f'data-afkv2-note="{note_id}" data-afkv2-note-target="{target}"'
    if note["deleted"]:
        return (f'<li class="afkv2-nr-note afkv2-nr-note--deleted" {attrs}><p class="afkv2-nr-head">{what} '
                f'({note_id}): deleted</p><p class="afkv2-nr-text">{escape(note["text"])}</p></li>')
    return (f'<li class="afkv2-nr-note" {attrs}><p class="afkv2-nr-head">{what} ({note_id})</p>'
            f'<p class="afkv2-nr-text">{escape(note["text"])}</p></li>')


def _signal(signal):
    parts = [escape(signal["target"])]
    if signal.get("mark"):
        parts.append(f'mark {escape(signal["mark"])}')
    if signal.get("note"):
        parts.append(f'note {escape(signal["note"])}')
    if signal.get("action"):
        parts.append(escape(signal["action"]))
    if signal.get("conflict"):
        parts.append("more than one line for this point")
    if signal.get("reopened"):
        parts.append("reopened")
    if signal.get("state"):
        parts.append(f'now {escape(signal["state"]).replace("_", " ")}')
    return f'<li class="afkv2-nr-signal">{" · ".join(parts)}</li>'


def _list(name, rows):
    return f'<ul class="{name}">{"".join(rows)}</ul>'


def _round(round_, notes, nodes):
    n = round_["n"]
    replies = round_.get("replies") or []
    signals = [signal for response in reversed(round_.get("responses") or []) for signal in response["signals"]]
    if not (replies or notes or signals):
        return ""
    sections = []
    if replies:
        rows = [_reply(reply) for reply in replies]
        sections.append(_list("afkv2-nr-replies", rows))
    if notes:
        rows = [_note(note, nodes) for note in notes]
        sections.append(_list("afkv2-nr-notes", rows))
    if signals:
        rows = [_signal(signal) for signal in signals]
        sections.append('<h3 class="afkv2-nr-h">What you sent</h3>' + _list("afkv2-nr-signals", rows))
    count = f"{len(replies)} replies, {sum(not note['deleted'] for note in notes)} notes"
    return (f'<details class="afkv2-nr-round" open data-afkv2-nr-round="{n}" '
            f'style="--afkv2-round: {escape(round_colour(round_))}"><summary>'
            f'<span class="afkv2-round-chip">R-{n}</span> Round {n}: {count}</summary>{"".join(sections)}</details>')


def render_notes_replies(props, children):
    doc = props["document"]
    nodes = _map_nodes(doc)
    by_round = {}
    for round_ in doc["rounds"]:
        for item in round_["items"]:
            for note in item.get("notes") or []:
                by_round.setdefault(note["round"], []).append(note)
    rounds = "".join(_round(r, by_round.get(r["n"], []), nodes) for r in sorted(doc["rounds"], key=lambda r: -r["n"]))
    heading = '<h2 class="afkv2-section-h">Notes and replies</h2>' if rounds else ""
    return heading + rounds + "".join(children)


register_component("notes-and-replies", {
    "type": "object", "additionalProperties": False, "required": ["document"],
    "properties": {"document": {"type": "object"}},
}, render_notes_replies)
