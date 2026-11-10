"""Write the page document of one page session (schema afkv2.page/1 or afkv2.page/2, SDD §4).

Verbs, run from the repository root:
  build          --doc D --session S [--ticket K] --round-input F [--ticket-file T] [--replace] [--private]
                 The skill is the name part of `<skill>-<session>.json`. `--private` marks a new page private.
                 The round input's `ticket_projects` adds Jira projects to `session.links`, and its
                 `ticket_titles` adds the hover title of each reference (page_links.py).
  apply-readings --doc D --readings F

The engine stays the check of the whole document; this script holds the grill's own rules:
the decided-card contract, the picture before a critical-aspect question, the settle-by-note
fields, and that no asking card is lost when a round closes.

Every note is in the session list (ADR-0001 design). A new session's page is format 2. A format 0 document is
read through the engine's format 0 reader, and its next write is format 1 (ADR-0002 design). A format 1 or 2
document keeps its format.
"""

from __future__ import annotations

import copy
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from grill_common import PLUGIN_ROOT, Parser, Refusal, read_json, serve, write_json, write_text
from page_links import links_for, project_keys, reference_titles

SCHEMA = "afkv2.page/1"
FORMAT_0 = "afkv2.page/0"
# The step of a page by its writer, until the round input names one (SDD §4 Session).
STEPS = {"grill": "Requirements grill", "propose-solution": "Solution design", "to-subtasks": "Plan approval"}
KINDS = {"decided", "confirm", "debate", "signoff", "info"}
ASKING = KINDS - {"info"}
NEW_STATES = {"open", "blocked"}
SETTLED_STATES = {"settled_by_mark", "settled_by_note"}
PICTURES = {"map", "graph", "table", "sequence", "run-strip", "freestyle"}
GRADES = {"repo", "spec", "pattern"}
ENGINE_ITEM_FIELDS = {"notes", "settled"}
ITEM_INPUT_FIELDS = {"id", "kind", "title", "node", "state", "body", "critical", "decided", "carries"} | ENGINE_ITEM_FIELDS
# The lists of a version 2 page, by the name of 1 entry (SDD §4). The round input sends only the entries that changed.
ENTRY_LISTS = {"sections": "section", "stories": "story", "examples": "example", "questions": "question"}
# The input fields of a sent entry that the builder does not store: its 1 change line and its place.
ENTRY_INPUT_FIELDS = ("change", "after")
# The document rules that refuse a version 2 write by their own name (engine/schema/invariants.py).
NAMED_RULES = ("everyone-answered", "answer-no-signal", "drop-no-reason", "assume-no-card", "reply-many-notes")
REPLY_FIELDS = {"text", "notes", "changed"}
READINGS = ("settle", "open", "unblock", "replies")
# The readings of a version 2 page, each with its fields (SDD §3 row "reading tool").
READINGS_V2 = {"keep": ("note", "reply", "changed"), "answer": ("question", "text", "choices", "role", "date", "signal"),
               "drop": ("question", "reason", "note"), "assume": ("question", "text", "card")}
TICKET_CARD = "i-ticket"
TICKET_TITLE = "What the ticket says"
FOLD_OVER = 600
SESSION_TEXT_LIMIT = 40
# The label of the optional block that names what a decision serves (ADR-0004 design).
DRIVEN_BY_LABEL = "Driven by"


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


def page_engine():
    """The engine module: its format readers, its version values and its checks."""
    folder = str(PLUGIN_ROOT / "engine")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import engine
    return engine


def is_version_2(doc):
    """A version 0 or 1 page asks the engine nothing."""
    schema = doc.get("schema")
    return schema not in (SCHEMA, FORMAT_0) and schema == page_engine().SCHEMA_V2


def is_page(raw):
    """True for a page document of a version this builder writes: 0 (read as 1), 1 or 2."""
    return isinstance(raw, dict) and (raw.get("schema") in (SCHEMA, FORMAT_0) or is_version_2(raw))


def format_1(doc):
    """The document in format 1, or 2 as it is: a format 0 document goes through the engine's one format 0
    reader, which changes nothing on disk."""
    if doc.get("schema") != FORMAT_0:
        return doc
    return page_engine().read_v0_as_v1(doc)


def session_notes(doc):
    """The live notes of the session list."""
    return [note for note in format_1(doc).get("notes") or [] if not note.get("deleted")]


def _notes_of(doc, item):
    return [note for note in session_notes(doc) if note.get("item") == item["id"]]


def _node_ids(component):
    return [node.get("id") for node in (component.get("props") or {}).get("nodes") or []]


def steer_targets(doc):
    """The ids a steer names: every element of a listed map, and every node of a map held in a card."""
    found = set()
    for chart in doc.get("maps") or []:
        for part in _components(chart):
            found.add(part.get("id"))
            found.update(_node_ids(part))
    for rnd in doc.get("rounds") or []:
        for item in rnd["items"]:
            found.update(node for part in _components(item["body"]) if part.get("type") == "map"
                         for node in _node_ids(part))
    found.discard(None)
    return found


def element_ids(doc):
    """Every id a note, an answer or a change list may name: cards, components, maps, map nodes and the round
    banners `R-<n>`, as the engine counts them."""
    return _used_ids(doc) | steer_targets(doc) | {f"R-{rnd['n']}" for rnd in doc.get("rounds") or []}


def refuse_bad_links(doc, answers, changed=()):
    """Refuse `bad-link` when an answer names a note or an element that does not exist, or a change list an element."""
    notes, elements = {note["id"] for note in doc.get("notes") or []}, element_ids(doc)
    bad = [f"note {value!r}" for answer in answers for value in answer.get("notes") or [] if value not in notes]
    bad += [f"element {value!r}" for value in [*changed, *(v for answer in answers for v in answer.get("changed") or [])]
            if value not in elements]
    if bad:
        raise Refusal("bad-link", f"these ids name nothing: {', '.join(dict.fromkeys(bad))}")


def card_notes(doc, item, targets):
    """The live notes that name a card and are no steer. An older document names a card in a steer."""
    return [note for note in _notes_of(doc, item) if note.get("target") not in targets]


def steers(doc):
    """Every live steer, oldest round first: the notes that name no card, and the steers an older document
    kept on a card."""
    doc = format_1(doc)
    targets = steer_targets(doc)
    found = [note for note in session_notes(doc) if note.get("item") is None or note.get("target") in targets]
    return sorted(found, key=lambda note: note.get("round", 0))


def holds_sign_mark(item):
    """True when the human signed this card with a `sign` mark; no note and no other mark signs."""
    settled = item.get("settled") or {}
    return item["state"] == "settled_by_mark" and settled.get("by") == "mark" and settled.get("signal") == "sign"


def signature_missing(item):
    """True for a `signoff` card that reads as settled and holds no `sign` mark."""
    return item["kind"] == "signoff" and item["state"] in SETTLED_STATES and not holds_sign_mark(item)


def _text(value, component_id):
    return {"type": "text", "id": component_id, "props": {"text": value}}


def _labelled(component_id, label, value, **extra):
    component = _text(value, component_id)
    component["props"].update(label=label, **extra)
    return component


def _decided_fields(item_id, decided, known_ids):
    """The six fields of a decided card as labelled text components, and whether the card holds all six.

    The decision comes first, in bold. A sent `driven_by` list adds a "Driven by" block right after it. The alternatives are a list under a label that calls them rejected,
    so they never read as parts of the decision. The grade is a badge on the evidence label."""
    decided = decided if isinstance(decided, dict) else {}
    alternatives = [str(a) for a in decided.get("alternatives") or []]
    grade, evidence = decided.get("grade"), decided.get("evidence")
    depends_on = decided.get("depends_on") or []
    whole = (bool(decided.get("decision")) and bool(alternatives) and bool(evidence) and grade in GRADES
             and bool(decided.get("why")) and bool(decided.get("reverse")) and set(depends_on) <= known_ids)
    fields = []
    if decided.get("decision"):
        fields.append({**_labelled(f"{item_id}-decision", "Decision", decided["decision"]), "style": "font-weight: 600"})
    driven_by = decided.get("driven_by")
    if driven_by is None:
        driven_by = []
    if not isinstance(driven_by, list) or not all(isinstance(value, str) and value.strip() for value in driven_by):
        raise Refusal("bad-item", f"item {item_id}: driven_by is a list of non-empty id strings: {driven_by!r}")
    if driven_by:
        fields.append(_labelled(f"{item_id}-driven-by", DRIVEN_BY_LABEL, ", ".join(driven_by)))
    if decided.get("why"):
        fields.append(_labelled(f"{item_id}-why", "Why this one", decided["why"]))
    if alternatives:
        listed = "\n".join("- " + " ".join(a.split()) for a in alternatives)
        fields.append(_labelled(f"{item_id}-alternatives", "Other options considered (rejected)", listed, markdown=True))
    if evidence:
        fields.append(_labelled(f"{item_id}-evidence", "Evidence", evidence,
                                badge=grade if grade in GRADES else "not graded"))
    if decided.get("reverse"):
        fields.append(_labelled(f"{item_id}-reverse", "To undo", decided["reverse"]))
    fields.append(_labelled(f"{item_id}-scope", "Depends on", ", ".join(depends_on) or "no other card"))
    return fields, whole


def require_decided(raw):
    """Refuse `no-decided-fields` for a `decided` card with no `decided` object: a card with all its fields stays
    decided, and a card with a gap in them degrades to `confirm` and is listed in `degraded`."""
    if raw.get("kind") == "decided" and not isinstance(raw.get("decided"), dict):
        raise Refusal("no-decided-fields", f"item {raw.get('id')}: a decided card holds its fields in `decided`, an "
                                           "object; send them, or send the card as `confirm`")


def _item(raw, known_ids, degraded, earlier_cards=frozenset(), version_2=False):
    if not isinstance(raw, dict) or not raw.get("id"):
        raise Refusal("bad-item", f"item without an id: {raw!r}")
    item_id = raw["id"]
    where = f"item {item_id}"
    engine_written = ENGINE_ITEM_FIELDS & set(raw)
    if engine_written:
        raise Refusal("engine-field", f"{where}: the engine writes {sorted(engine_written)}")
    unknown = set(raw) - ITEM_INPUT_FIELDS - ({"section"} if version_2 else set())
    if unknown:
        raise Refusal("bad-item", f"{where}: unknown fields {sorted(unknown)}")
    if raw.get("kind") not in KINDS:
        raise Refusal("bad-item", f"{where}: kind {raw.get('kind')!r} is not one of {sorted(KINDS)}")
    state = raw.get("state", "open")
    if state not in NEW_STATES:
        raise Refusal("bad-item", f"{where}: a new card is open or blocked, not {state!r}")
    require_decided(raw)
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
    if not set(carries) <= earlier_cards:
        raise Refusal("bad-item", f"{where}: carries no card of an earlier round: {sorted(set(carries) - earlier_cards)}")
    item = {"id": item_id, "kind": kind, "state": state, "body": body}
    for optional in ("title", "node", "carries", "section"):
        if raw.get(optional):
            item[optional] = raw[optional]
    return item


def reference(key):
    """A ticket key as the page writes it: a GitHub issue number gets `#`, so the page links it."""
    key = str(key or "")
    return f"#{key}" if key.isdigit() else key


def _ticket_card(ticket):
    """The info card that shows what the ticket says, comments and links included.

    The description is Markdown, folded when it is long. A linked ticket shows its title and status only.
    Each key is a reference, so the page links the ticket and each linked ticket.
    """
    description = _text(ticket.get("description") or "(no description)", f"{TICKET_CARD}-description")
    description["props"]["markdown"] = True
    if len(description["props"]["text"]) > FOLD_OVER:
        description["fold"] = "The ticket text"
    children = [description]
    if ticket.get("comments"):
        children.append({"type": "table", "id": f"{TICKET_CARD}-comments", "props": {
            "columns": ["Author", "Comment"],
            "rows": [[c.get("author") or "?", c.get("text") or ""] for c in ticket["comments"]]}})
    if ticket.get("comments_cut"):
        children.append(_text(f"{ticket['comments_cut']} more comments were not returned.", f"{TICKET_CARD}-cut"))
    if ticket.get("links"):
        children.append({"type": "table", "id": f"{TICKET_CARD}-links", "props": {
            "columns": ["Relation", "Ticket", "Title", "Status"],
            "rows": [[link.get("relation") or "", reference(link.get("key")), link.get("title") or "",
                      link.get("status") or ""] for link in ticket["links"]]}})
    if ticket.get("unread_links"):
        children.append({"type": "table", "id": f"{TICKET_CARD}-unread", "props": {
            "columns": ["Ticket not read", "Reason"],
            "rows": [[reference(link.get("key")), link.get("reason") or ""] for link in ticket["unread_links"]]}})
    return {"id": TICKET_CARD, "kind": "info", "title": TICKET_TITLE, "state": "open", "body": {
        "type": "text", "id": f"{TICKET_CARD}-title",
        "props": {"text": f"{reference(ticket['key'])}: {ticket.get('title') or ''}"}, "children": children}}


def _carries_card(item, card_id):
    """True when the item states that it carries the card; a mention in other text or in depends-on carries nothing.

    The `carries` field states it. A card built before that field states it in its text component `<id>-carries`."""
    if card_id in (item.get("carries") or []):
        return True
    stated = next((c for c in _components(item["body"]) if c.get("id") == f"{item['id']}-carries"), {})
    return re.search(rf"(?<![\w-]){re.escape(card_id)}(?![\w-])", (stated.get("props") or {}).get("text", "")) is not None


def returning(doc):
    """Asking cards of the rounds before the current one that the human noted or reopened in this send. On a
    version 2 page a note leaves a settled card settled: the agent reads it with `keep`, or asks again on a card."""
    doc = format_1(doc)
    current = current_round(doc)
    if not current:
        return []
    targets = steer_targets(doc)
    reopened = {signal.get("item") for response in current.get("responses") or []
                for signal in response.get("signals") or [] if signal.get("reopened")}
    found = []
    stays = SETTLED_STATES if is_version_2(doc) else set()
    for rnd in doc["rounds"]:
        if rnd is current:
            continue
        for item in rnd["items"]:
            noted = item["state"] not in stays and any(note.get("round") == current["n"]
                                                        for note in card_notes(doc, item, targets))
            unread = item["state"] == "needs_reading" and not _carried(doc, item, rnd["n"])
            if item["kind"] in ASKING and (noted or item["id"] in reopened or unread):
                found.append(item)
    return found


def _carried(doc, item, own_round):
    """True when a card of a later round than the item's last note carries it: the point lives there now."""
    after = max([own_round, *(note.get("round", own_round) for note in _notes_of(doc, item))])
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


def shown_record(doc_path):
    """The file that names the round `present` showed or recorded with `--no-show`; schema afkv2.page/0 has no field for it."""
    return Path(doc_path).with_suffix(".shown.txt")


def record_shown(doc_path):
    write_text(shown_record(doc_path), f"{current_round(read_json(doc_path))['n']}\n")


def _was_shown(doc_path, current):
    record = shown_record(doc_path)
    return record.is_file() and record.read_text("utf-8").strip() == str(current["n"])


def _drop_unanswered_round(doc, doc_path):
    """Take back a current round the human never saw, so a corrected one replaces it; the round before it is current again.

    The scripts cannot see unsent marks: they live only in the browser. So a shown round with no answer refuses.
    """
    current = current_round(doc)
    if current is None:
        raise Refusal("round-not-replaceable", "no round is current")
    if current.get("responses"):
        raise Refusal("round-answered", f"round {current['n']} has an answer; a new round carries its points")
    if _was_shown(doc_path, current):
        raise Refusal("round-shown", f"round {current['n']} was shown and has no answer; an answer may be in progress "
                                     "in the browser, so wait for it; a new round then carries its points")
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


def _answers(doc, note):
    """True when an answer names the note; an answer of a format 0 page, in the note's round or later, names it,
    its element or its card in `about`."""
    named = {note["id"], note.get("target"), note.get("item")} - {None}
    return any(note["id"] in (answer.get("notes") or [])
               or (rnd["n"] >= note.get("round", 0) and named & set(answer.get("about") or []))
               for rnd in doc.get("rounds") or [] for answer in rnd.get("replies") or [])


def unanswered_note_warnings(doc, round_n):
    """A warning for each live note of round `round_n` that no answer names (SDD §6); the round still builds."""
    return [{"code": "unanswered-note", "note": note["id"],
             "reason": f"note {note['id']} of round {round_n} has no answer; answer each note"}
            for note in doc.get("notes") or [] if note.get("round") == round_n and not note.get("deleted")
            and not _answers(doc, note)]


def _session_text(session, round_input, n):
    """Write the step, and the short title in round 1 only; answer the warning for a later title (SDD §6)."""
    if round_input.get("step") is not None:
        session["step"] = round_input["step"]
    title = round_input.get("short_title")
    if title is None:
        return []
    if n == 1:
        session["short_title"] = title
        return []
    return [{"code": "ignored-title", "reason": f"the short title is written in round 1 only; round {n} keeps "
                                                f"{session.get('short_title')!r}, not {title!r}"}]


def _stored(entry):
    return {key: value for key, value in entry.items() if key != "changes"}


def _change_line(where, line, n):
    """The 1 change line of a sent entry, for round `n`; the builder writes its round."""
    if not isinstance(line, dict) or line.get("round", n) != n:
        raise Refusal("no-change-line", f"{where} changed, so it carries exactly 1 change line for round {n} in "
                                        f"`change`, an object {{cause, text, notes | card | question}}: {line!r}")
    return {"round": n, **{key: value for key, value in line.items() if key != "round"}}


def _place_after(stored, entry, after, where, name):
    """The list with the entry right after the other entry of the list that `after` names; `after: null` puts it
    first."""
    if after is None:
        return [entry, *(old for old in stored if old["id"] != entry["id"])]
    if after == entry["id"] or not any(old["id"] == after for old in stored):
        raise Refusal("bad-entry", f"{where}: after {after!r} names no other {name} of the list; a same-round "
                                   f"{name} counts only when it is sent before this one")
    rest = [old for old in stored if old["id"] != entry["id"]]
    at = next(k for k, old in enumerate(rest) if old["id"] == after) + 1
    return [*rest[:at], entry, *rest[at:]]


def _place_question(stored, entry, after, where):
    """The list with the question right after the question that `after` names."""
    return _place_after(stored, entry, after, where, "question")


def _place_section(stored, entry, after, where):
    """The list with the section right after the stored or earlier-sent same-round section that `after` names (ADR-0001 design)."""
    return _place_after(stored, entry, after, where, "section")


# The lists whose entries take `after`, each with its placer.
PLACERS = {"questions": _place_question, "sections": _place_section}


def _merge_entries(doc, round_input, n):
    """Merge the sent entries of the 4 lists into the document by id; answer their ids in the order sent.

    An entry left out keeps its text and its change list exactly. A sent entry holds every field but `changes`,
    + `change`: its 1 change line for round `n`; a question or a section may add `after`, the entry it follows, or null to go first. A new entry
    goes to the end of its list. A line of round `n` that a replaced round wrote gives way to the new one; an entry
    of the replaced round that the new round leaves out keeps that round's text and line (decision D-20)."""
    changed = []
    for kind, name in ENTRY_LISTS.items():
        sent = round_input.get(kind)
        if sent is None:
            continue
        if not isinstance(sent, list):
            raise Refusal("bad-entry", f"{kind} is a list of the entries that changed")
        stored = list(doc.get(kind) or [])
        for raw in sent:
            if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw["id"]:
                raise Refusal("bad-entry", f"{kind}: an entry without an id: {raw!r}")
            where = f"{name} {raw['id']}"
            if "changes" in raw:
                raise Refusal("bad-entry", f"{where}: the builder writes changes; send 1 change line in `change`")
            if "after" in raw and kind not in PLACERS:
                raise Refusal("bad-entry", f"{where}: only a question or a section takes `after`")
            if raw["id"] in changed:
                raise Refusal("bad-entry", f"{where} is sent twice")
            entry = {key: copy.deepcopy(value) for key, value in raw.items() if key not in ENTRY_INPUT_FIELDS}
            old = next((old for old in stored if old["id"] == raw["id"]), None)
            order = [old["id"] for old in stored] + ([] if old else [raw["id"]])
            placed = PLACERS[kind](stored, entry, raw["after"], where) if "after" in raw else None
            # A round rebuilt by `replace` resends its own entries: an entry with a line of round `n` is no repeat.
            replaced = old is not None and any(line["round"] == n for line in old.get("changes") or [])
            if (old is not None and not replaced and _stored(old) == entry
                    and (placed is None or [e["id"] for e in placed] == order)):
                raise Refusal("unchanged-entry", f"{where} is sent unchanged; send only the entries that changed")
            entry["changes"] = [*(line for line in (old or {}).get("changes") or [] if line["round"] != n),
                                _change_line(where, raw.get("change"), n)]
            if placed is not None:
                stored = placed
            elif old is not None:
                stored = [entry if other["id"] == entry["id"] else other for other in stored]
            else:
                stored.append(entry)
            changed.append(raw["id"])
        doc[kind] = stored
    return changed


def check_version_2(doc):
    """Run the engine's document check on a version 2 document in memory; a broken rule refuses by its name."""
    try:
        page_engine().check_in_memory(doc, NAMED_RULES)
    except Exception as error:
        if not hasattr(error, "code"):
            raise
        raise Refusal(error.code, error.reason) from error


def _upgrade(doc, doc_path, upgrade, replace=False):
    """Write a version 0 or 1 page as version 2, only when a new session took it over in its current round (SDD §4
    Migration and backfill). The document is in memory, read as version 1. The caller records the first version 2
    round in `session.upgraded`: the replies of older rounds keep the notes they name. `replace` of the round that
    upgraded the page sends `upgrade` again: the page is version 2 already, and the rebuilt round stays that round."""
    if upgrade is not True:
        raise Refusal("bad-round", f"upgrade is true, false or left out: {upgrade!r}")
    current = current_round(doc) if Path(doc_path).exists() else None
    if replace and current is not None and is_version_2(doc) and doc["session"].get("upgraded") == current["n"]:
        return
    taken_over = current is not None and any(entry.get("round") == current["n"]
                                             for entry in doc["session"].get("takeovers") or [])
    if is_version_2(doc) or not taken_over:
        raise Refusal("upgrade-not-taken-over", "upgrade writes a version 0 or 1 page as version 2 only after a new "
                                                "session took it over in its current round (page_round.py take-over)")
    doc["schema"] = page_engine().SCHEMA_V2


def build_round_document(doc_path, session, round_input, ticket=None, replace=False, links=None):
    """Create the document or append the next round; write nothing on a refusal.

    `round_input` holds banner, items and optional maps, replies, colour, short_title (round 1), step and
    changed (the element ids the agent changed this round), tips and value_sets. A reply is {text, notes, changed}.
    `tips` replaces the document's tips catalog; omitting it keeps the stored tips. `value_sets` adds each sent
    set to the document's value sets, by name, and replaces a stored set of the same name. An item may carry
    `critical` (a picture must be the body root), `decided` (the six decided-card fields; a gap
    makes it a confirm card) and `carries` (the older cards it asks again). `ticket` adds the
    ticket card to round 1. `replace` rewrites a current round that has no answer and was never shown.
    `links` replaces `session.links`, the URL templates the page links references with.

    On a version 2 page the round input may add `sections`, `stories`, `examples` and `questions`: only the
    entries that changed (`_merge_entries`), and a card may name its `section`. A version 0 or 1 page refuses
    these fields by name, unless the round input holds `upgrade: true` (`_upgrade`). A version 2 document passes
    the engine's document check before it is written. Only the answer of a version 2 page holds `entries`.
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
    for field in ("short_title", "step"):
        value = round_input.get(field)
        if value is not None and not (isinstance(value, str) and value.strip() and len(value) <= SESSION_TEXT_LIMIT):
            raise Refusal("bad-round", f"{field} is text of 1 to {SESSION_TEXT_LIMIT} characters: {value!r}")
    if not _id_list(round_input.get("changed", [])):
        raise Refusal("bad-round", "changed is a list of element ids")
    if doc_path.exists():
        doc = read_json(doc_path)
        if not is_page(doc):
            raise Refusal("bad-schema", f"{doc_path} has schema {doc.get('schema')!r}; this skill writes "
                                        f"{SCHEMA} and {page_engine().SCHEMA_V2}")
        if (doc.get("session") or {}).get("id") != session["id"]:
            raise Refusal("bad-session", f"{doc_path} belongs to session {(doc.get('session') or {}).get('id')!r}")
        doc = format_1(doc)
    else:
        started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        fields = {"step": STEPS.get(session.get("skill")) or str(session.get("feature"))[:40],
                  "private": False, "takeovers": []}
        doc = {"schema": page_engine().SCHEMA_V2, "session": {**fields, **session, "started": started}, "maps": [], "notes": [],
               "rounds": []}
    upgrading = "upgrade" in round_input and round_input["upgrade"] is not False
    if upgrading:
        _upgrade(doc, doc_path, round_input["upgrade"], replace)
    version_2 = is_version_2(doc)
    sent_lists = [kind for kind in ENTRY_LISTS if kind in round_input]
    if sent_lists and not version_2:
        raise Refusal("bad-round", f"{', '.join(sent_lists)}: only a version 2 page holds these lists; this page is "
                                   f"{doc['schema']}")
    if replace:
        _drop_unanswered_round(doc, doc_path)
    if links:
        doc["session"]["links"] = links
    if "tips" in round_input:
        doc["tips"] = round_input["tips"]
    if "value_sets" in round_input:
        if not isinstance(round_input["value_sets"], dict):
            raise Refusal("bad-round", "value_sets is an object {name: {values, ordered}}")
        doc["value_sets"] = {**(doc.get("value_sets") or {}), **round_input["value_sets"]}
    n = max((rnd["n"] for rnd in doc["rounds"]), default=0) + 1
    if upgrading:
        doc["session"]["upgraded"] = n
    warnings = _session_text(doc["session"], round_input, n)
    _apply_maps(doc, round_input.get("maps"), n)
    used = _used_ids(doc)
    raw_items = round_input.get("items") or []
    known = used | {raw.get("id") for raw in raw_items if isinstance(raw, dict)}
    degraded = []
    earlier = frozenset(item["id"] for rnd in doc["rounds"] for item in rnd["items"])
    items = [_item(raw, known, degraded, earlier, version_2) for raw in raw_items]
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
    for optional in ("colour", "changed"):
        if optional in round_input:
            built[optional] = round_input[optional]
    for reply in round_input.get("replies") or []:
        _reply(built, reply, version_2)
    doc["rounds"].append(built)
    entries = _merge_entries(doc, round_input, n) if version_2 else []
    refuse_bad_links(doc, built.get("replies") or [], built.get("changed") or [])
    unanswered = unanswered_note_warnings(doc, n - 1)
    if version_2 and unanswered:
        raise Refusal("unanswered-note", f"each note gets its own reply before round {n}; these have none: "
                                         f"{', '.join(warning['note'] for warning in unanswered)}")
    warnings += unanswered
    if version_2:
        check_version_2(doc)
    write_json(doc_path, doc)
    answer = {"ok": True, "doc": str(doc_path), "round": n,
              "items": [item["id"] for item in items if item["id"] != TICKET_CARD], "degraded": degraded,
              "warnings": warnings}
    return {**answer, "entries": entries} if version_2 else answer


def _id_list(value):
    return isinstance(value, list) and all(isinstance(entry, str) and entry for entry in value)


def _answer_number(rnd, answer):
    found = re.fullmatch(rf"A-{rnd['n']}-([1-9][0-9]*)", str(answer.get("id") or ""))
    return int(found.group(1)) if found else 0


def _add_answer(rnd, text, notes, changed=()):
    """Append one answer to the round, with the next id `A-<round>-<k>`. An answer with no note answers a mark."""
    replies = rnd.setdefault("replies", [])
    k = max((_answer_number(rnd, old) for old in replies), default=0) + 1
    answer = {"id": f"A-{rnd['n']}-{k}", "text": text}
    if notes:
        answer["notes"] = list(notes)
    if changed:
        answer["changed"] = list(changed)
    replies.append(answer)
    return answer


def _reply(rnd, raw, version_2=False):
    """A reply of the agent, {text, notes, changed}, as an answer of the round: it names 1 or more notes, and
    exactly 1 on a version 2 page."""
    if not isinstance(raw, dict) or set(raw) - REPLY_FIELDS:
        raise Refusal("bad-reply", f"a reply holds only text, notes and changed: {raw!r}")
    if not isinstance(raw.get("text"), str) or not raw["text"].strip():
        raise Refusal("bad-reply", f"a reply needs its text: {raw!r}")
    if not _id_list(raw.get("notes")) or not raw["notes"]:
        raise Refusal("bad-reply", f"a reply names 1 or more note ids in notes: {raw!r}")
    if not _id_list(raw.get("changed", [])):
        raise Refusal("bad-reply", f"changed is a list of element ids: {raw!r}")
    if version_2 and len(raw["notes"]) > 1:
        raise Refusal("reply-many-notes", f"a reply names exactly 1 note on a version 2 page; write 1 reply for each "
                                          f"of {', '.join(raw['notes'])}")
    return _add_answer(rnd, raw["text"], raw["notes"], raw.get("changed") or [])


def _current_item(current, item_id):
    for item in current["items"]:
        if item["id"] == item_id:
            return item
    raise Refusal("not-in-round", f"{item_id} is not a card of round {current['n']}; a settled round is never rewritten")


def _settle(doc, current, entry):
    item = _current_item(current, entry.get("item"))
    if item["state"] != "needs_reading":
        raise Refusal("not-needs-reading", f"{item['id']} is {item['state']}, not needs_reading")
    if item["kind"] == "info":
        raise Refusal("info-card", f"{item['id']} asks nothing, so a note on it settles nothing; reply only")
    if item["kind"] == "signoff":
        raise Refusal("signoff-needs-mark", f"{item['id']} settles only by a `sign` mark; return it with `open`, "
                                            "and a new card asks the human to sign")
    if entry.get("note") not in {note["id"] for note in _notes_of(doc, item)}:
        raise Refusal("no-note", f"{item['id']} has no live note {entry.get('note')!r}")
    reading = (entry.get("reading") or "").strip()
    if not reading:
        raise Refusal("no-reading", f"{item['id']}: a point settled by a note needs its reading")
    if not _id_list(entry.get("changed", [])):
        raise Refusal("bad-reply", f"{item['id']}: changed is a list of element ids")
    item["state"] = "settled_by_note"
    item["settled"] = {"by": "note", "round": current["n"], "signal": entry["note"], "reading": reading}
    _add_answer(current, f"Settled by your note: {reading}", [entry["note"]], entry.get("changed") or [])


def _return_to_open(doc, current, entry, version_2=False):
    """The answer names the card's live notes of this round; a card that returns on marks alone has none. On a
    version 2 page it names only `note`, the 1 note of this round on the card that it answers, or none."""
    item = _current_item(current, entry.get("item"))
    if item["state"] != "needs_reading":
        raise Refusal("not-needs-reading", f"{item['id']} is {item['state']}, not needs_reading")
    reply = (entry.get("reply") or "").strip()
    if not reply:
        raise Refusal("no-reply", f"{item['id']}: say why the point returns")
    if not _id_list(entry.get("changed", [])):
        raise Refusal("bad-reply", f"{item['id']}: changed is a list of element ids")
    of_round = [note["id"] for note in _notes_of(doc, item) if note.get("round") == current["n"]]
    if version_2:
        if entry.get("note") is not None and entry["note"] not in of_round:
            raise Refusal("no-note", f"{item['id']} has no live note {entry['note']!r} of round {current['n']}")
        of_round = [entry["note"]] if entry.get("note") is not None else []
    item["state"] = "open"
    _add_answer(current, reply, of_round, entry.get("changed") or [])


def _unblock(current, item_id):
    item = _current_item(current, item_id)
    if item["state"] != "blocked":
        raise Refusal("not-blocked", f"{item_id} is {item['state']}, not blocked")
    item["state"] = "open"


def _keep(doc, current, entry):
    """The point stays settled: the reply answers the note of this round on the settled card."""
    note = next((note for note in session_notes(doc) if note["id"] == entry.get("note")), None)
    if note is None or note.get("round") != current["n"]:
        raise Refusal("no-note", f"{entry.get('note')!r} is no live note of round {current['n']}")
    item = next((item for rnd in doc["rounds"] for item in rnd["items"] if item["id"] == note.get("item")), None)
    if item is None or item["state"] not in SETTLED_STATES:
        raise Refusal("not-settled", f"note {note['id']} sits on no settled point; `keep` reads a note on a settled card")
    _reply(current, {"text": entry.get("reply"), "notes": [note["id"]], "changed": entry.get("changed") or []}, True)


def _open_question(doc, entry, states=("open",)):
    question = next((q for q in doc.get("questions") or [] if q["id"] == entry.get("question")), None)
    if question is None:
        raise Refusal("not-a-question", f"{entry.get('question')!r} is no question for others of this page")
    if question["state"] not in states:
        raise Refusal("question-closed", f"question {question['id']} is {question['state']}, not {' or '.join(states)}")
    return question


def _answer_question(doc, current, entry):
    """The agent writes the answer from the developer's tick or note of this round; it settles no card."""
    question = _open_question(doc, entry, ("open", "assumed"))
    signal = entry.get("signal")
    ticked = any(tick.get("target") == question["id"] and tick.get("mark") == "tick"
                 for response in current.get("responses") or [] for tick in response.get("signals") or [])
    noted = any(note["id"] == signal and note.get("round") == current["n"] for note in session_notes(doc))
    if not (ticked if signal == "tick" else noted):
        raise Refusal("answer-no-signal", f"question {question['id']}: the answer rests on the developer's tick on it "
                                          f"or a live note of round {current['n']}; {signal!r} is neither")
    question["state"] = "answered"
    question["answer"] = {"text": entry.get("text"), "choices": entry.get("choices") or [], "role": entry.get("role"),
                          "date": entry.get("date"), "signal": entry.get("signal"), "round": current["n"]}


def _drop_question(doc, current, entry):
    question = _open_question(doc, entry)
    reason = entry.get("reason") or ""
    if not isinstance(reason, str) or not reason.strip():
        raise Refusal("drop-no-reason", f"question {question['id']}: a dropped question needs a reason")
    question["state"] = "dropped"
    question["dropped"] = {"reason": reason, "note": entry.get("note"), "round": current["n"]}


def _assume_question(doc, current, entry):
    question = _open_question(doc, entry)
    question["state"] = "assumed"
    question["assumption"] = {"text": entry.get("text"), "card": entry.get("card"), "round": current["n"]}


def _new_readings(doc, current, readings):
    """keep, answer, drop and assume, each entry with only its own fields; the document check guards the rest."""
    apply = {"keep": _keep, "answer": _answer_question, "drop": _drop_question, "assume": _assume_question}
    for key, fields in READINGS_V2.items():
        for entry in readings.get(key) or []:
            if not isinstance(entry, dict) or set(entry) - set(fields):
                raise Refusal("bad-payload", f"a {key} reading holds only {', '.join(fields)}: {entry!r}")
            apply[key](doc, current, entry)


def apply_readings(doc_path, readings):
    """Apply one batch of readings, all or nothing. Keys: settle, open, unblock, replies, and on a version 2 page
    keep {note, reply}, answer {question, text, choices, role, date, signal}, drop {question, reason, note} and
    assume {question, text, card}. Answer, drop and assume write round = the current round. An `open` entry is
    {item, reply, changed, note}; only a version 2 page reads `note`, and a version 1 page answers every note of the
    round on the card."""
    doc = format_1(read_json(doc_path))
    current = current_round(doc)
    if current is None:
        raise Refusal("bad-document", "no round is current")
    version_2 = is_version_2(doc)
    keys = READINGS + (tuple(READINGS_V2) if version_2 else ())
    if not isinstance(readings, dict) or not readings or set(readings) - set(keys):
        new = sorted(set(readings) & set(READINGS_V2)) if isinstance(readings, dict) and not version_2 else []
        why = f"; {', '.join(new)} only on a version 2 page" if new else ""
        raise Refusal("bad-payload", f"readings: one object with {', '.join(keys)}{why}")
    answered = len(current.get("replies") or [])
    for entry in readings.get("settle") or []:
        _settle(doc, current, entry)
    for entry in readings.get("open") or []:
        _return_to_open(doc, current, entry, version_2)
    for item_id in readings.get("unblock") or []:
        _unblock(current, item_id)
    for reply in readings.get("replies") or []:
        _reply(current, reply, version_2)
    if version_2:
        _new_readings(doc, current, readings)
    refuse_bad_links(doc, (current.get("replies") or [])[answered:])
    if version_2:
        check_version_2(doc)
    write_json(doc_path, doc)
    return {"ok": True, **pending(doc)}


def pending(doc):
    """What the round pass still has to read, from the document alone."""
    doc = format_1(doc)
    current = current_round(doc)
    if current is None:
        raise Refusal("bad-document", "no round is current")
    targets = steer_targets(doc)

    def card(item):
        return {"id": item["id"], "kind": item["kind"], "state": item["state"], "notes": card_notes(doc, item, targets)}

    responses = current.get("responses") or []
    by_state = {state: [item["id"] for item in current["items"] if item["state"] == state]
                for state in ("open", "blocked", "settled_by_mark", "settled_by_note")}
    return {"round": current["n"],
            "needs_reading": [card(item) for item in current["items"] if item["state"] == "needs_reading"],
            "returned": [card(item) for item in returning(doc)],
            "steers": steers(doc),
            "signals": responses[-1].get("signals", []) if responses else [],
            **by_state}


def _skill_of(doc, session):
    """The writer that the file name `<skill>-<session>.json` names; grill for any other name."""
    skill = Path(doc).name.removesuffix(f"-{session}.json")
    return skill if skill in {*STEPS, "use-lavish"} else "grill"


def _feature_of(doc):
    """The folder that holds the `pages` folder (a ticket), else the page's own folder (a repository name)."""
    folder = Path(doc).resolve().parent
    return folder.parent.name if folder.name == "pages" else folder.name


def main(argv):
    parser = Parser(add_help=False)
    parser.add_argument("verb", choices=["build", "apply-readings"])
    parser.add_argument("--doc", required=True)
    parser.add_argument("--session")
    parser.add_argument("--ticket")
    parser.add_argument("--round-input")
    parser.add_argument("--ticket-file")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--readings")
    parser.add_argument("--private", action="store_true")
    args = parser.parse_args(argv)
    if args.verb == "build":
        if not (args.session and args.round_input):
            raise Refusal("usage", "build needs --session and --round-input", 2)
        round_input = read_json(args.round_input)
        ticket = read_json(args.ticket_file) if args.ticket_file else None
        session = {"id": args.session, "skill": _skill_of(args.doc, args.session), "feature": _feature_of(args.doc),
                   "ticket": args.ticket, **({"private": True} if args.private else {})}
        earlier = (read_json(args.doc).get("session") or {}).get("links") if Path(args.doc).exists() else None
        keys = [args.ticket, *(link.get("key") for link in [*((ticket or {}).get("links") or []),
                                                             *((ticket or {}).get("unread_links") or [])])]
        held = round_input if isinstance(round_input, dict) else {}
        extra = project_keys("ticket_projects", held.pop("ticket_projects", None))
        titles = reference_titles("ticket_titles", held.pop("ticket_titles", None))
        return build_round_document(args.doc, session, round_input, ticket, args.replace,
                                    links_for(keys, earlier, extra, titles))
    if not args.readings:
        raise Refusal("usage", "apply-readings needs --readings", 2)
    return apply_readings(args.doc, read_json(args.readings))


if __name__ == "__main__":
    sys.exit(serve(main))
