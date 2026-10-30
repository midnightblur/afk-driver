"""Write the page document of one grill session (schema afkv2.page/0, SDD §4).

Verbs, run from the repository root:
  build          --doc D --session S --ticket K --round-input F --ticket-file T [--replace]
  apply-readings --doc D --readings F
  pending        --doc D

The engine stays the check of the whole document; this script holds the grill's own rules:
the decided-card contract, the picture before a critical-aspect question, the settle-by-note
fields, and that no asking card is lost when a round closes.
"""

from __future__ import annotations

import copy
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from grill_common import Parser, Refusal, read_json, serve, write_json

SCHEMA = "afkv2.page/0"
KINDS = {"decided", "confirm", "debate", "signoff", "info"}
ASKING = KINDS - {"info"}
NEW_STATES = {"open", "blocked"}
PICTURES = {"map", "graph", "table", "sequence", "run-strip", "freestyle"}
GRADES = {"repo", "spec", "pattern"}
ENGINE_ITEM_FIELDS = {"notes", "settled"}
ITEM_INPUT_FIELDS = {"id", "kind", "node", "state", "body", "critical", "decided", "carries"} | ENGINE_ITEM_FIELDS
TICKET_CARD = "i-ticket"


def _components(component):
    """Every component of a tree: the root, its children, and the components in table cells."""
    yield component
    for child in component.get("children") or []:
        yield from _components(child)
    rows = (component.get("props") or {}).get("rows")
    if isinstance(rows, list):
        for row in rows:
            for cell in row if isinstance(row, list) else []:
                if isinstance(cell, dict):
                    yield from _components(cell)


def _map_nodes(doc):
    return [node for chart in doc.get("maps") or [] for node in (chart.get("props") or {}).get("nodes") or []]


def _used_ids(doc):
    ids = set()
    for chart in doc.get("maps") or []:
        ids.add(chart.get("id"))
    ids.update(node.get("id") for node in _map_nodes(doc))
    for rnd in doc.get("rounds") or []:
        for item in rnd["items"]:
            ids.add(item["id"])
            ids.update(c.get("id") for c in _components(item["body"]))
    ids.discard(None)
    return ids


def current_round(doc):
    return next((rnd for rnd in doc.get("rounds") or [] if rnd.get("state") == "current"), None)


def _live_notes(item):
    return [note for note in item.get("notes") or [] if not note.get("deleted")]


def _text(value, component_id):
    return {"type": "text", "id": component_id, "props": {"text": value}}


def _decided_fields(item_id, decided, known_ids):
    """The six fields of a decided card as components, and whether the card holds all six."""
    decided = decided if isinstance(decided, dict) else {}
    alternatives = decided.get("alternatives") or []
    grade, evidence = decided.get("grade"), decided.get("evidence")
    depends_on = decided.get("depends_on") or []
    whole = (bool(decided.get("decision")) and bool(alternatives) and bool(evidence) and grade in GRADES
             and bool(decided.get("why")) and bool(decided.get("reverse")) and set(depends_on) <= known_ids)
    label = f"{grade}: {evidence}" if grade in GRADES else f"not graded: {evidence}"
    parts = [("decision", decided.get("decision")),
             ("why", decided.get("why")),
             ("alternatives", "Alternatives beaten: " + "; ".join(alternatives) if alternatives else None),
             ("evidence", label if evidence else None),
             ("reverse", f"reverse: {decided['reverse']}" if decided.get("reverse") else None),
             ("scope", f"HL: none · depends-on: {', '.join(depends_on) or 'none'}")]
    return [_text(value, f"{item_id}-{name}") for name, value in parts if value], whole


def _item(raw, known_ids, degraded):
    if not isinstance(raw, dict) or not raw.get("id"):
        raise Refusal("bad-item", f"item without an id: {raw!r}")
    item_id = raw["id"]
    where = f"item {item_id}"
    engine_written = ENGINE_ITEM_FIELDS & set(raw)
    if engine_written:
        raise Refusal("engine-field", f"{where}: the engine writes {sorted(engine_written)}")
    unknown = set(raw) - ITEM_INPUT_FIELDS
    if unknown:
        raise Refusal("bad-item", f"{where}: unknown fields {sorted(unknown)}")
    if raw.get("kind") not in KINDS:
        raise Refusal("bad-item", f"{where}: kind {raw.get('kind')!r} is not one of {sorted(KINDS)}")
    state = raw.get("state", "open")
    if state not in NEW_STATES:
        raise Refusal("bad-item", f"{where}: a new card is open or blocked, not {state!r}")
    kind, body = raw["kind"], copy.deepcopy(raw.get("body"))
    if kind == "decided":
        fields, whole = _decided_fields(item_id, raw.get("decided"), known_ids)
        if not whole:
            kind = "confirm"
            degraded.append(item_id)
        if body:
            body["children"] = [*(body.get("children") or []), *fields]
        elif fields:
            body = {**fields[0], "children": fields[1:]}
    if not isinstance(body, dict) or not body.get("type"):
        raise Refusal("bad-item", f"{where}: body is required, one component")
    for component in _components(body):
        if "html" in component and component.get("type") != "freestyle":
            raise Refusal("not-freestyle", f"{where}: only a freestyle component holds html, "
                                           f"not {component.get('type')!r}")
    if raw.get("critical") and body["type"] not in PICTURES:
        raise Refusal("no-picture", f"{where}: a critical-aspect question needs a picture of the current state "
                                    f"as the body root, above the question; the root is {body['type']!r}")
    carries = raw.get("carries") or []
    if not set(carries) <= known_ids:
        raise Refusal("bad-item", f"{where}: carries an unknown card: {sorted(set(carries) - known_ids)}")
    if carries:
        body["children"] = [*(body.get("children") or []), _text(f"Carries {', '.join(carries)}.", f"{item_id}-carries")]
    item = {"id": item_id, "kind": kind, "state": state, "body": body}
    if raw.get("node"):
        item["node"] = raw["node"]
    return item


def _ticket_card(ticket):
    """The info card that shows what the ticket says, comments and links included."""
    children = [_text(ticket.get("description") or "(no description)", f"{TICKET_CARD}-description")]
    if ticket.get("comments"):
        children.append({"type": "table", "id": f"{TICKET_CARD}-comments", "props": {
            "columns": ["Author", "Comment"],
            "rows": [[c.get("author") or "?", c.get("text") or ""] for c in ticket["comments"]]}})
    if ticket.get("comments_cut"):
        children.append(_text(f"{ticket['comments_cut']} more comments were not returned.", f"{TICKET_CARD}-cut"))
    if ticket.get("links"):
        children.append({"type": "table", "id": f"{TICKET_CARD}-links", "props": {
            "columns": ["Relation", "Ticket", "Title", "Status", "Description"],
            "rows": [[link.get("relation") or "", link.get("key") or "", link.get("title") or "",
                      link.get("status") or "", link.get("description") or ""] for link in ticket["links"]]}})
    if ticket.get("unread_links"):
        children.append({"type": "table", "id": f"{TICKET_CARD}-unread", "props": {
            "columns": ["Ticket not read", "Reason"],
            "rows": [[link.get("key") or "", link.get("reason") or ""] for link in ticket["unread_links"]]}})
    return {"id": TICKET_CARD, "kind": "info", "state": "open", "body": {
        "type": "text", "id": f"{TICKET_CARD}-title",
        "props": {"text": f"{ticket['key']}: {ticket.get('title') or ''}"}, "children": children}}


def _carries_card(item, card_id):
    """True when the item states that it carries the card; a mention in other text or in depends-on carries nothing."""
    stated = next((c for c in _components(item["body"]) if c.get("id") == f"{item['id']}-carries"), {})
    return re.search(rf"(?<![\w-]){re.escape(card_id)}(?![\w-])", (stated.get("props") or {}).get("text", "")) is not None


def returning(doc):
    """Asking cards of the rounds before the current one that the human noted or reopened in this send."""
    current = current_round(doc)
    if not current:
        return []
    steer_targets = {node.get("id") for node in _map_nodes(doc)}
    found = []
    for rnd in doc["rounds"]:
        if rnd is current:
            continue
        for item in rnd["items"]:
            noted = any(note.get("round") == current["n"] and note.get("target") not in steer_targets
                        for note in _live_notes(item))
            reopened = item["state"] == "needs_reading" or (item["state"] == "open" and item.get("settled"))
            if item["kind"] in ASKING and (noted or (reopened and not _carried(doc, item, rnd["n"]))):
                found.append(item)
    return found


def _carried(doc, item, own_round):
    """True when a card of a later round than the item's last note carries it: the point lives there now."""
    after = max([own_round, *(note.get("round", own_round) for note in _live_notes(item))])
    return any(_carries_card(card, item["id"]) for rnd in doc["rounds"] if rnd["n"] > after for card in rnd["items"])


def _close_current(doc, new_items):
    current = current_round(doc)
    if current is None:
        raise Refusal("bad-document", "no round is current")
    if not current.get("responses"):
        raise Refusal("round-not-sent", f"round {current['n']} has no answer yet; ingest its answer first")
    unread = [item["id"] for item in current["items"] if item["state"] == "needs_reading"]
    if unread:
        raise Refusal("round-pass-open", f"round {current['n']}: read these points first: {', '.join(unread)}")
    returned = [item for item in current["items"]
                if item["kind"] in ASKING and item["state"] in NEW_STATES] + returning(doc)
    lost = [item["id"] for item in returned if not any(_carries_card(new, item["id"]) for new in new_items)]
    if lost:
        raise Refusal("missing-carry", f"these points return, and no new card carries them: {', '.join(lost)}")
    current["state"] = "settled"


def _drop_unanswered_round(doc):
    """Take back the current round so a corrected one replaces it; the round before it is current again."""
    current = current_round(doc)
    if current is None:
        raise Refusal("round-not-replaceable", "no round is current")
    if current.get("responses"):
        raise Refusal("round-answered", f"round {current['n']} has an answer; a new round carries its points")
    doc["rounds"].remove(current)
    if doc["rounds"]:
        doc["rounds"][-1]["state"] = "current"


def _apply_maps(doc, maps, n):
    if maps is None:
        return
    before = {node["id"]: node for node in _map_nodes(doc)}
    for chart in maps:
        for node in chart.get("props", {}).get("nodes", []):
            old = before.get(node.get("id"))
            node["round"] = old["round"] if old and old.get("state") == node.get("state") else n
    doc["maps"] = maps


def build_round_document(doc_path, session, round_input, ticket=None, replace=False):
    """Create the document or append the next round; write nothing on a refusal.

    `round_input` holds banner, items and optional maps, replies, colour. An item may carry
    `critical` (a picture must be the body root), `decided` (the six decided-card fields; a gap
    makes it a confirm card) and `carries` (the older cards it asks again). `ticket` adds the
    ticket card to round 1. `replace` rewrites a current round that has no answer.
    """
    doc_path = Path(doc_path)
    round_input = copy.deepcopy(round_input)
    if not isinstance(round_input, dict):
        raise Refusal("bad-round", "the round input must be one JSON object")
    if {"responses"} & set(round_input):
        raise Refusal("engine-field", "the engine writes responses")
    if not isinstance(round_input.get("banner"), dict):
        raise Refusal("bad-round", "banner is required: settled, unlocks, parked")
    if not isinstance(round_input.get("items", []), list):
        raise Refusal("bad-round", "items must be a list")
    if doc_path.exists():
        doc = read_json(doc_path)
        if doc.get("schema") != SCHEMA:
            raise Refusal("bad-schema", f"{doc_path} has schema {doc.get('schema')!r}; this skill writes {SCHEMA}")
        if (doc.get("session") or {}).get("id") != session["id"]:
            raise Refusal("bad-session", f"{doc_path} belongs to session {(doc.get('session') or {}).get('id')!r}")
    else:
        started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        doc = {"schema": SCHEMA, "session": {**session, "started": started}, "maps": [], "rounds": []}
    if replace:
        _drop_unanswered_round(doc)
    n = max((rnd["n"] for rnd in doc["rounds"]), default=0) + 1
    _apply_maps(doc, round_input.get("maps"), n)
    used = _used_ids(doc)
    raw_items = round_input.get("items") or []
    known = used | {raw.get("id") for raw in raw_items if isinstance(raw, dict)}
    degraded = []
    items = [_item(raw, known, degraded) for raw in raw_items]
    if doc["rounds"]:
        _close_current(doc, items)
    elif ticket and ticket.get("key"):
        items.insert(0, _ticket_card(ticket))
    nodes = {node.get("id") for node in _map_nodes(doc)}
    for item in items:
        if item.get("node") and item["node"] not in nodes:
            raise Refusal("bad-item", f"item {item['id']}: node {item['node']!r} is not on a map")
        new = [item["id"], *(c.get("id") for c in _components(item["body"]) if c.get("id"))]
        reused = sorted(set(new) & used)
        if reused or len(set(new)) != len(new):
            raise Refusal("id-reused", f"item {item['id']}: an id is reused: {reused or new}")
        used.update(new)
    built = {"n": n, "state": "current", "banner": round_input["banner"], "items": items}
    for optional in ("colour", "replies"):
        if optional in round_input:
            built[optional] = round_input[optional]
    doc["rounds"].append(built)
    write_json(doc_path, doc)
    return {"ok": True, "doc": str(doc_path), "round": n, "items": [item["id"] for item in items if item["id"] != TICKET_CARD],
            "degraded": degraded}


def _current_item(current, item_id):
    for item in current["items"]:
        if item["id"] == item_id:
            return item
    raise Refusal("not-in-round", f"{item_id} is not a card of round {current['n']}; a settled round is never rewritten")


def _settle(current, entry):
    item = _current_item(current, entry.get("item"))
    if item["state"] != "needs_reading":
        raise Refusal("not-needs-reading", f"{item['id']} is {item['state']}, not needs_reading")
    if item["kind"] == "info":
        raise Refusal("info-card", f"{item['id']} asks nothing, so a note on it settles nothing; reply only")
    if entry.get("note") not in {note["id"] for note in _live_notes(item)}:
        raise Refusal("no-note", f"{item['id']} has no live note {entry.get('note')!r}")
    reading = (entry.get("reading") or "").strip()
    if not reading:
        raise Refusal("no-reading", f"{item['id']}: a point settled by a note needs its reading")
    item["state"] = "settled_by_note"
    item["settled"] = {"by": "note", "round": current["n"], "signal": entry["note"], "reading": reading}
    current.setdefault("replies", []).append({"text": f"Settled by your note: {reading}", "about": [item["id"]]})


def _return_to_open(current, entry):
    item = _current_item(current, entry.get("item"))
    if item["state"] != "needs_reading":
        raise Refusal("not-needs-reading", f"{item['id']} is {item['state']}, not needs_reading")
    reply = (entry.get("reply") or "").strip()
    if not reply:
        raise Refusal("no-reply", f"{item['id']}: say why the point returns")
    item["state"] = "open"
    current.setdefault("replies", []).append({"text": reply, "about": [item["id"]]})


def _unblock(current, item_id):
    item = _current_item(current, item_id)
    if item["state"] != "blocked":
        raise Refusal("not-blocked", f"{item_id} is {item['state']}, not blocked")
    item["state"] = "open"


def apply_readings(doc_path, readings):
    """Apply one batch of readings, all or nothing. Keys: settle, open, unblock, replies."""
    doc = read_json(doc_path)
    current = current_round(doc)
    if current is None:
        raise Refusal("bad-document", "no round is current")
    if not isinstance(readings, dict) or not readings or set(readings) - {"settle", "open", "unblock", "replies"}:
        raise Refusal("bad-payload", "readings: one object with settle, open, unblock, replies")
    for entry in readings.get("settle") or []:
        _settle(current, entry)
    for entry in readings.get("open") or []:
        _return_to_open(current, entry)
    for item_id in readings.get("unblock") or []:
        _unblock(current, item_id)
    for reply in readings.get("replies") or []:
        current.setdefault("replies", []).append(reply)
    write_json(doc_path, doc)
    return {"ok": True, **pending(doc)}


def pending(doc):
    """What the round pass still has to read, from the document alone."""
    current = current_round(doc)
    if current is None:
        raise Refusal("bad-document", "no round is current")
    nodes = {node.get("id") for node in _map_nodes(doc)}

    def card(item):
        return {"id": item["id"], "kind": item["kind"], "state": item["state"],
                "notes": [note for note in _live_notes(item) if note.get("target") not in nodes]}

    responses = current.get("responses") or []
    steers = [note for rnd in doc["rounds"] for item in rnd["items"] for note in _live_notes(item)
              if note.get("target") in nodes]
    by_state = {state: [item["id"] for item in current["items"] if item["state"] == state]
                for state in ("open", "blocked", "settled_by_mark", "settled_by_note")}
    return {"round": current["n"],
            "needs_reading": [card(item) for item in current["items"] if item["state"] == "needs_reading"],
            "returned": [card(item) for item in returning(doc)],
            "steers": steers,
            "signals": responses[-1].get("signals", []) if responses else [],
            **by_state}


def main(argv):
    parser = Parser(add_help=False)
    parser.add_argument("verb", choices=["build", "apply-readings", "pending"])
    parser.add_argument("--doc", required=True)
    parser.add_argument("--session")
    parser.add_argument("--ticket")
    parser.add_argument("--round-input")
    parser.add_argument("--ticket-file")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--readings")
    args = parser.parse_args(argv)
    if args.verb == "build":
        if not (args.session and args.ticket and args.round_input):
            raise Refusal("usage", "build needs --session, --ticket and --round-input", 2)
        round_input = read_json(args.round_input)
        ticket = read_json(args.ticket_file) if args.ticket_file else None
        feature = Path(args.doc).parent.parent.name
        session = {"id": args.session, "skill": "grill", "feature": feature, "ticket": args.ticket}
        return build_round_document(args.doc, session, round_input, ticket, args.replace)
    if args.verb == "apply-readings":
        if not args.readings:
            raise Refusal("usage", "apply-readings needs --readings", 2)
        return apply_readings(args.doc, read_json(args.readings))
    return {"ok": True, **pending(read_json(args.doc))}


if __name__ == "__main__":
    sys.exit(serve(main))
