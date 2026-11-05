"""Tests for the visualize skill: the authoring guide for page documents.

Until the page engine exists, every example is checked by a recorded fake of
the page document v0 contract (SDD §4 field tables). A format 1 document is checked
for its own fields, then as the format 0 view of it. When the engine file
exists, every example also goes through `engine check` and must answer ok.
"""

import copy
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "fakes"))

from fake_v1_facts import V1_WORD  # noqa: E402

PLUGIN = Path(__file__).resolve().parents[2]
SKILL_DIR = PLUGIN / "skills" / "visualize"
SKILL_MD = SKILL_DIR / "SKILL.md"
PAGES_DIR = SKILL_DIR / "components"
ALL_COMPONENTS = SKILL_DIR / "examples" / "all-components.json"
ENGINE = PLUGIN / "engine" / "engine.py"

SCHEMA = "afkv2.page/0"
SCHEMA_1 = "afkv2.page/1"

# PRD catalog id -> the page that holds its entry.
CATALOG = {
    "CMP-1": "round-banner.md",
    "CMP-2": "notes-and-replies.md",
    "CMP-3": "map.md",
    "CMP-4": "card.md",
    "CMP-5": "graph.md",
    "CMP-6": "table.md",
    "CMP-7": "sequence.md",
    "CMP-8": "run-strip.md",
    "CMP-9": "chip-and-text.md",
    "CMP-10": "freestyle.md",
}
ENTRY_SECTIONS = ("## Holds", "## Use it when", "## How it looks", "## Example")
# PRD table K id -> the page of its chart component, with the props each chart requires beside `caption`.
CHART_PAGES = {
    "K-01": "tile.md", "K-02": "bars.md", "K-03": "line.md", "K-35": "bullet.md", "K-36": "box-plot.md",
    "K-37": "range.md", "K-38": "signed-bars.md", "K-47": "flame.md", "K-48": "sparkline.md", "K-49": "waterfall.md",
}
CHART_FIELDS = {"tile": {"value", "label", "grade", "source"}, "bars": {"items"}, "line": {"points"},
                "bullet": {"label", "value", "target", "bands"}, "range": {"items", "means"}, "signed-bars": {"items"},
                "box-plot": {"items"}, "flame": {"root"}, "sparkline": {"rows"}, "waterfall": {"spans"}}
# The diagram text, code block and diff components (PRD EG-13, EG-15): the page of each, with its required props.
TEXT_PAGES = {"diagram": "diagram.md", "code": "code.md", "diff": "diff.md"}
TEXT_FIELDS = {"diagram": {"caption", "text"}, "code": {"text"}, "diff": {"text"}}

# Recorded fake of the page document v0 contract: SDD §4 field sets, props as the guide states them.

DOC_FIELDS = {"schema", "session", "maps", "rounds"}
SESSION_FIELDS = {"id", "skill", "feature", "ticket", "started"}
SKILLS = {"grill", "propose-solution", "propose-verification"}
ROUND_FIELDS = {"n", "state", "colour", "banner", "items", "responses", "replies", "notes"}
BANNER_FIELDS = {"settled", "unlocks", "parked"}
REPLY_FIELDS = {"text", "about"}
ITEM_FIELDS = {"id", "kind", "title", "node", "state", "body", "settled", "notes", "carries"}
ITEM_KINDS = {"decided", "confirm", "debate", "signoff", "info"}
POINT_STATES = {"open", "blocked", "needs_reading", "settled_by_mark", "settled_by_note"}
SETTLED_FIELDS = {"by", "round", "signal", "reading"}
NOTE_FIELDS = {"id", "round", "target", "text", "deleted"}
COMPONENT_FIELDS = {"type", "id", "props", "style", "fold", "children", "html"}
NODE_STATES = {"open", "settled", "focus"}
TONES = {"removed", "kept", "new", "proposed"}
# A chip also takes the state and certainty tones; a sequence message takes 3 tones (SDD §4 "Other parts").
STATE_TONES = {"open", "blocked", "settled", "measured", "inferred", "estimated", "unverified", "you"}
MESSAGE_TONES = {"removed", "kept", "new"}
ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$")


class Refused(Exception):
    """The fake refuses a document, naming the place and the field."""


def _need(cond, where, field):
    if not cond:
        raise Refused(f"{where}: {field}")


def _only(obj, allowed, where):
    _need(isinstance(obj, dict), where, "is not an object")
    extra = set(obj) - allowed
    _need(not extra, where, f"unknown field {sorted(extra)}")


def _objects(value, where, field):
    _need(isinstance(value, list) and all(isinstance(v, dict) for v in value), where, field)
    return value


def _text_list(value, where, field):
    _need(isinstance(value, list) and all(isinstance(v, str) for v in value), where, field)


def _ids(value, where, field):
    objs = _objects(value, where, field)
    _need(all(isinstance(o.get("id"), str) for o in objs), where, f"{field}[].id")
    return {o["id"] for o in objs}


def _check_marks(part, where):
    """The tip and you of a graph node, map node, run-strip step or sequence message."""
    tip = part.get("tip")
    _need(tip is None or (isinstance(tip, str) and 0 < len(tip) <= 300), where, "tip (1 to 300 characters)")
    _need(isinstance(part.get("you", False), bool), where, "you (true or false)")


def _check_graph(kind, props, where, ids, last_round):
    nodes = _objects(props.get("nodes"), where, "props.nodes")
    _need(nodes, where, "props.nodes")
    groups = _ids(props.get("groups", []), where, "props.groups")
    node_ids = set()
    for n, node in enumerate(nodes):
        _need(isinstance(node.get("id"), str), where, f"props.nodes[{n}].id")
        _need(isinstance(node.get("label"), str), where, f"props.nodes[{n}].label")
        if kind == "map":
            _need(node.get("state") in NODE_STATES, where, f"props.nodes[{n}].state")
            rnd = node.get("round")
            _need(isinstance(rnd, int) and 1 <= rnd <= last_round, where,
                  f"props.nodes[{n}].round (1..{last_round})")
            _need(node["id"] not in ids, where, f"node id {node['id']} not unique")
            ids.add(node["id"])
        _need(node.get("group") is None or node["group"] in groups, where,
              f"props.nodes[{n}].group")
        _check_marks(node, f"{where}.props.nodes[{n}]")
        node_ids.add(node["id"])
    for e, edge in enumerate(_objects(props.get("edges", []), where, "props.edges")):
        _need(edge.get("from") in node_ids and edge.get("to") in node_ids, where,
              f"props.edges[{e}]")


def _check_props(comp, where, ids, last_round):
    kind = comp["type"]
    props = comp.get("props", {})
    _need(isinstance(props, dict), where, "props")
    if kind == "freestyle":
        _need(isinstance(comp.get("html"), str) and comp["html"], where, "html")
        _need(isinstance(props.get("reason"), str) and props["reason"], where, "props.reason")
        _need("id" in comp, where, "id (a freestyle use needs an id to be reported)")
        return
    _need("html" not in comp, where, "html (freestyle only)")
    if kind in ("chip", "text"):
        _need(isinstance(props.get("text"), str), where, "props.text")
        tone = props.get("tone")
        _need(tone is None or tone in TONES or (kind == "chip" and tone in STATE_TONES), where, "props.tone")
        _need(kind == "text" or (tone is None) != (props.get("set") is None), where, "props.tone (a tone or a set)")
        _need(kind == "chip" or "set" not in props, where, "props.set (a chip only)")
        _need(isinstance(props.get("markdown", False), bool), where, "props.markdown")
    elif kind == "table":
        cols = props.get("columns")
        rows = props.get("rows")
        _text_list(cols, where, "props.columns")
        _need(isinstance(rows, list) and rows, where, "props.rows")
        for r, row in enumerate(rows):
            _need(isinstance(row, list) and len(row) == len(cols), where, f"props.rows[{r}]")
            for c, cell in enumerate(row):
                if not isinstance(cell, str):
                    _check_component(cell, f"{where}.rows[{r}][{c}]", ids, last_round)
    elif kind in ("graph", "map"):
        _check_graph(kind, props, where, ids, last_round)
    elif kind == "sequence":
        actors = _ids(props.get("actors", []), where, "props.actors")
        _need(actors, where, "props.actors")
        msgs = _objects(props.get("messages"), where, "props.messages")
        _need(msgs, where, "props.messages")
        for m, msg in enumerate(msgs):
            _need(msg.get("from") in actors and msg.get("to") in actors, where,
                  f"props.messages[{m}]")
            _need(isinstance(msg.get("text"), str), where, f"props.messages[{m}].text")
            _need(msg.get("tone") is None or msg["tone"] in MESSAGE_TONES, where, f"props.messages[{m}].tone")
            _check_marks(msg, f"{where}.props.messages[{m}]")
    elif kind == "run-strip":
        lanes = [k for k in ("current", "proposed") if k in props]
        _need(lanes, where, "props.current or props.proposed")
        for lane in lanes:
            for s, step in enumerate(_objects(props[lane], where, f"props.{lane}")):
                _need(isinstance(step.get("label"), str), where, f"props.{lane}[{s}].label")
                _need(step.get("tone") is None or step["tone"] in TONES, where,
                      f"props.{lane}[{s}].tone")
                _check_marks(step, f"{where}.props.{lane}[{s}]")
    elif kind in TEXT_FIELDS:
        missing = TEXT_FIELDS[kind] - set(props)
        _need(not missing, where, f"props {sorted(missing)} (required)")
        _need(all(isinstance(props[field], str) and props[field] for field in TEXT_FIELDS[kind]), where,
              f"props {sorted(TEXT_FIELDS[kind])} (text)")
        _need(kind != "diagram" or len(props["caption"]) <= 160, where, "props.caption (1 to 160 characters)")
    elif kind in CHART_FIELDS:
        caption = props.get("caption")
        _need(isinstance(caption, str) and 0 < len(caption) <= 160, where, "props.caption (1 to 160 characters)")
        missing = CHART_FIELDS[kind] - set(props)
        _need(not missing, where, f"props {sorted(missing)} (required)")
    else:
        raise Refused(f"{where}: unknown type {kind!r}")


def _check_component(comp, where, ids, last_round):
    _only(comp, COMPONENT_FIELDS, where)
    _need(isinstance(comp.get("type"), str), where, "type")
    if "id" in comp:
        _need(isinstance(comp["id"], str), where, "id")
        _need(comp["id"] not in ids, where, f"id {comp['id']} not unique")
        ids.add(comp["id"])
    if "style" in comp:
        _need(isinstance(comp["style"], str), where, "style")
    if "fold" in comp:
        _need(isinstance(comp["fold"], str) and comp["fold"], where, "fold")
    _check_props(comp, where, ids, last_round)
    for i, child in enumerate(_objects(comp.get("children", []), where, "children")):
        _check_component(child, f"{where}.children[{i}]", ids, last_round)


def _walk_components(comp):
    yield comp
    for child in comp.get("children", []):
        yield from _walk_components(child)
    if comp.get("type") == "table":
        for row in comp["props"]["rows"]:
            for cell in row:
                if isinstance(cell, dict):
                    yield from _walk_components(cell)


def _check_settled(item, iw, last_round, node_ids):
    state = item.get("state", "open")
    settled = item.get("settled")
    if state not in ("settled_by_mark", "settled_by_note"):
        _need(settled is None, iw, "settled (only on a settled point)")
        return
    _only(settled, SETTLED_FIELDS, f"{iw}.settled")
    by = "note" if state == "settled_by_note" else "mark"
    _need(settled.get("by") == by, f"{iw}.settled", f"by (expected {by})")
    rnd = settled.get("round")
    _need(isinstance(rnd, int) and 1 <= rnd <= last_round, f"{iw}.settled", "round")
    _need(isinstance(settled.get("signal"), str) and settled["signal"], f"{iw}.settled", "signal")
    if by == "note":
        _need(isinstance(settled.get("reading"), str) and settled["reading"], f"{iw}.settled",
              "reading (required when by = note)")
        live = {n["id"] for n in item.get("notes", [])
                if not n["deleted"] and n["target"] not in node_ids}
        _need(settled["signal"] in live, f"{iw}.settled",
              "signal (must name a live note on the item)")


def _note_id_ok(note_id, rnd, owner):
    """Mirrors engine/schema/note_rules.py: the old form `N-<round>-<owner>` or the new `N-<round>-<owner>-<k>`."""
    return bool(re.fullmatch(rf"N-{rnd}-{re.escape(str(owner))}(-[1-9][0-9]*)?", note_id or ""))


def _check_notes(item, iw, last_round):
    for n, note in enumerate(_objects(item.get("notes", []), iw, "notes")):
        where = f"{iw}.notes[{n}]"
        _only(note, NOTE_FIELDS, where)
        _need(set(note) == NOTE_FIELDS, where, "missing field")
        rnd = note["round"]
        _need(isinstance(rnd, int) and 1 <= rnd <= last_round, where, "round")
        _need(_note_id_ok(note["id"], rnd, item["id"]), where, "id (N-<round>-<item>[-<k>])")
        _need(isinstance(note["target"], str), where, "target")
        _need(isinstance(note["text"], str), where, "text")
        _need(isinstance(note["deleted"], bool), where, "deleted")


def _check_round(r, ids, node_ids, last_round, components):
    where = f"round {r.get('n')}"
    _only(r, ROUND_FIELDS, where)
    _need(r.get("state") in ("current", "settled"), where, "state")
    _need("banner" in r and "items" in r, where, "banner and items")
    _only(r["banner"], BANNER_FIELDS, f"{where}.banner")
    for key in sorted(BANNER_FIELDS):
        _need(key in r["banner"], f"{where}.banner", f"{key} (required)")
        _text_list(r["banner"][key], f"{where}.banner", key)
    _need(not r.get("responses"), where, "responses (written only by ingest)")
    for p, reply in enumerate(_objects(r.get("replies", []), where, "replies")):
        _only(reply, REPLY_FIELDS, f"{where}.replies[{p}]")
        _need(isinstance(reply.get("text"), str), f"{where}.replies[{p}]", "text")
        _text_list(reply.get("about", []), f"{where}.replies[{p}]", "about")
    for item in _objects(r["items"], where, "items"):
        iw = f"item {item.get('id')}"
        _only(item, ITEM_FIELDS, iw)
        _need(isinstance(item.get("id"), str), iw, "id")
        _need(item["id"] not in ids, iw, "id not unique")
        ids.add(item["id"])
        _need(item.get("kind") in ITEM_KINDS, iw, "kind")
        _need(item.get("title") is None or (isinstance(item["title"], str) and 0 < len(item["title"]) <= 90), iw, "title")
        _need(item.get("state", "open") in POINT_STATES, iw, "state")
        _need(item.get("node") is None or item["node"] in node_ids, iw, "node must resolve")
        _check_notes(item, iw, last_round)
        _check_settled(item, iw, last_round, node_ids)
        _need("body" in item, iw, "body")
        _check_component(item["body"], f"{iw}.body", ids, last_round)
        components.extend(_walk_components(item["body"]))


def _check_document(doc):
    _only(doc, DOC_FIELDS, "document")
    _need(doc.get("schema") == SCHEMA, "document", f"schema (expected {SCHEMA})")
    session = doc.get("session")
    _only(session, SESSION_FIELDS | {"links"}, "session")
    _need(SESSION_FIELDS <= set(session), "session", "missing field")
    _need(session["skill"] in SKILLS, "session", "skill")
    _need(isinstance(session["started"], str) and bool(ISO_UTC.match(session["started"])),
          "session", "started (ISO-8601 UTC)")
    rounds = _objects(doc.get("rounds"), "document", "rounds")
    _need(rounds, "document", "rounds")
    _need([r.get("n") for r in rounds] == list(range(1, len(rounds) + 1)), "rounds", "n in order")
    _need(sum(r.get("state") == "current" for r in rounds) == 1, "rounds",
          "exactly one round is current")
    last_round = len(rounds)
    ids = set()
    components = []
    maps = _objects(doc.get("maps", []), "document", "maps")
    for m, mp in enumerate(maps):
        _need(mp.get("type") == "map", f"maps[{m}]", "type (map)")
        _check_component(mp, f"maps[{m}]", ids, last_round)
        components.append(mp)
    node_ids = {n["id"] for mp in maps for n in mp["props"]["nodes"]}
    for r in rounds:
        _check_round(r, ids, node_ids, last_round, components)
    ids.update(f"R-{r['n']}" for r in rounds)  # the banner of each round is an element (note_rules.round_target)
    note_ids = set()
    for r in rounds:
        for n, note in enumerate(_objects(r.get("notes", []), f"round {r['n']}", "notes")):
            _only(note, NOTE_FIELDS, f"round {r['n']}.notes[{n}]")
            _need(_note_id_ok(note.get("id"), r["n"], note.get("target")), f"round {r['n']}.notes[{n}]",
                  "id (N-<round>-<target>[-<k>])")
    for note in (n for r in rounds for n in [*(n for item in r["items"] for n in item.get("notes", [])),
                                             *r.get("notes", [])]):
        _need(note["id"] not in note_ids, f"note {note['id']}", "id not unique")
        note_ids.add(note["id"])
        _need(note["target"] in ids, f"note {note['id']}", "target must resolve")
    for r in rounds:
        for p, reply in enumerate(r.get("replies", [])):
            for target in reply.get("about", []):
                _need(target in ids or target in note_ids, f"round {r['n']}.replies[{p}]",
                      f"about {target} must resolve")
    return components


# Format 1 (SDD §4): one session note list, the new session fields, answer ids and links.
DOC_FIELDS_1 = DOC_FIELDS | {"notes", "value_sets"}
SESSION_FIELDS_1 = {"short_title", "step", "private", "takeovers"}
SKILLS_1 = {"grill", "propose-solution", "to-subtasks", "use-lavish"}
ANSWER_FIELDS_1 = {"id", "text", "notes", "changed", "about"}


def _format_0_view(doc):
    """Check the format 1 fields; return the document as format 0, every note back on its card or round."""
    _only(doc, DOC_FIELDS_1, "document")
    session = doc.get("session")
    _only(session, SESSION_FIELDS | SESSION_FIELDS_1 | {"links"}, "session")
    _need(session.get("skill") in SKILLS_1, "session", "skill")
    _need(isinstance(session.get("step"), str) and session["step"], "session", "step (required)")
    _need(isinstance(session.get("private", False), bool), "session", "private")
    view = copy.deepcopy(doc)
    view["schema"] = SCHEMA
    view.pop("value_sets", None)
    view["session"] = {k: v for k, v in session.items() if k not in SESSION_FIELDS_1}
    view["session"].setdefault("ticket", None)
    view["session"]["skill"] = "grill"
    rounds = {r.get("n"): r for r in view.get("rounds") or []}
    cards = {item.get("id"): item for r in rounds.values() for item in r.get("items") or []}
    for n, note in enumerate(_objects(view.pop("notes", []), "document", "notes")):
        _only(note, NOTE_FIELDS | {"item", "quote"}, f"notes[{n}]")
        quote = note.pop("quote", None)
        _need(quote is None or (isinstance(quote, str) and len(quote) <= 300), f"notes[{n}]", "quote")
        item = note.pop("item", None)
        holder = cards.get(item) if item is not None else rounds.get(note.get("round"))
        _need(holder is not None, f"notes[{n}]", "item or round must resolve")
        holder.setdefault("notes", []).append(note)
    for r in rounds.values():
        r.pop("changed", None)
        for p, reply in enumerate(r.get("replies") or []):
            _only(reply, ANSWER_FIELDS_1, f"round {r.get('n')}.replies[{p}]")
            reply.pop("id", None)
            reply["about"] = [*reply.pop("notes", []), *reply.pop("changed", []), *reply.get("about", [])]
    return view


def _check_value_chips(components, value_sets):
    """A value chip names a set of the document, and its text is a value of that set (SDD §4)."""
    for comp in components:
        props = comp.get("props") or {}
        if comp["type"] != "chip" or "set" not in props:
            continue
        named = (value_sets or {}).get(props["set"])
        _need(named is not None, f"chip {props['text']}", f"set {props['set']} (names no value set)")
        _need(props["text"] in named["values"], f"chip {props['text']}", f"text (no value of the set {props['set']})")


def _check_tips(doc):
    """A format 1 component may take `tip`, 1 to 300 characters; the format 0 view drops it."""
    def strip(obj):
        if isinstance(obj, dict):
            if isinstance(obj.get("type"), str) and "tip" in obj:
                tip = obj.pop("tip")
                _need(isinstance(tip, str) and 0 < len(tip) <= 300, f"component {obj['type']}", "tip (1 to 300 characters)")
            for value in obj.values():
                strip(value)
        elif isinstance(obj, list):
            for value in obj:
                strip(value)
    strip(doc.get("maps"))
    for r in doc.get("rounds") or []:
        for item in r.get("items") or []:
            strip(item.get("body"))


def check_document(doc):
    """Return every component of a valid document; raise Refused otherwise."""
    try:
        if isinstance(doc, dict) and doc.get("schema") == SCHEMA_1:
            view = _format_0_view(doc)
            _check_tips(view)
            components = _check_document(view)
            _check_value_chips(components, doc.get("value_sets"))
            return components
        components = _check_document(doc)
        _check_value_chips(components, None)
        return components
    except (KeyError, TypeError, AttributeError) as exc:
        raise Refused(f"malformed document: {type(exc).__name__}: {exc}") from exc


# Fragments: ```json fragment=<level> blocks in the guide.

FENCE = re.compile(r"```json fragment=(\w+)\n(.*?)\n```", re.S)
LEVELS = {"document", "round", "banner", "reply", "answer", "item", "component", "map"}
NOTE_ID = re.compile(r"N-(\d+)-(.+)-(\d+)")


def fragments(path):
    text = path.read_text("utf-8")
    found = [(m.group(1), json.loads(m.group(2))) for m in FENCE.finditer(text)]
    assert len(found) == text.count("```json"), f"{path.name}: a json fence is not a fragment"
    return found


def wrap(level, frag):
    """Put a fragment into the smallest whole document that holds it.

    The wrapper supplies every item and map node the fragment names, so id
    resolution is proven on all-components.json only (see the refusal tests).
    """
    if level == "document":
        return frag
    if level == "answer":
        return _wrap_answer(frag)
    doc = {
        "schema": SCHEMA,
        "session": {"id": "s-wrap", "skill": "grill", "feature": "example",
                    "ticket": "PROJ-123", "started": "2026-01-01T09:00:00Z"},
        "maps": [],
        "rounds": [{"n": 1, "state": "current",
                    "banner": {"settled": [], "unlocks": [], "parked": []}, "items": []}],
    }
    current = doc["rounds"][0]
    if level == "round":
        doc["rounds"] = [frag]
        current = frag
    elif level == "banner":
        current["banner"] = frag
    elif level == "reply":
        for target in frag.get("about", []):
            current["items"].append({"id": target, "kind": "info",
                                     "body": {"type": "text", "props": {"text": "x"}}})
        current["replies"] = [frag]
    elif level == "item":
        current["items"].append(frag)
    elif level == "component":
        current["items"].append({"id": "i-wrap", "kind": "info", "body": frag})
    elif level == "map":
        doc["maps"].append(frag)
    for item in current["items"]:
        node = item.get("node")
        known = {n["id"] for mp in doc["maps"] for n in mp["props"]["nodes"]}
        if node and node not in known:
            doc["maps"].append({"type": "map", "id": f"m-{node}", "props": {
                "title": "wrap", "nodes": [{"id": node, "label": node, "state": "focus",
                                            "round": 1}]}})
    return doc


def _wrap_answer(frag):
    """A format 1 answer, {text, notes, changed}, in the smallest format 1 document: each note and element it names."""
    notes = [{"id": nid, "round": 1, "target": NOTE_ID.fullmatch(nid).group(2),
              "item": NOTE_ID.fullmatch(nid).group(2), "text": "x", "deleted": False} for nid in frag.get("notes", [])]
    ids = dict.fromkeys([*(n["item"] for n in notes), *frag.get("changed", [])])
    items = [{"id": i, "kind": "info", "body": {"type": "text", "props": {"text": "x"}}} for i in ids]
    return {
        "schema": SCHEMA_1,
        "session": {"id": "s-wrap", "skill": "grill", "feature": "example", "ticket": "PROJ-123",
                    "started": "2026-01-01T09:00:00Z", "step": "Requirements grill"},
        "maps": [], "notes": notes,
        "rounds": [{"n": 1, "state": "current", "banner": {"settled": [], "unlocks": [], "parked": []},
                    "items": items, "replies": [frag]}],
    }


def all_fragments():
    out = []
    for page in [SKILL_MD, *sorted(PAGES_DIR.glob("*.md"))]:
        for level, frag in fragments(page):
            out.append((page.name, level, frag))
    return out


def _example():
    return json.loads(ALL_COMPONENTS.read_text("utf-8"))


def _example_v0():
    """The format 0 view of the example: the fake's refusal tests and the format 0 ingest tests start from it."""
    return _format_0_view(_example())


def all_documents():
    docs = [("all-components.json", _example())]
    docs += [(f"{name}:{level}", wrap(level, frag)) for name, level, frag in all_fragments()]
    return docs


def _find(obj, wanted):
    """Return the object with this id anywhere in the document, or None."""
    if isinstance(obj, dict):
        if obj.get("id") == wanted:
            return obj
        obj = list(obj.values())
    if isinstance(obj, list):
        for value in obj:
            hit = _find(value, wanted)
            if hit is not None:
                return hit
    return None


def _at(wanted):
    def locate(d):
        hit = _find(d, wanted)
        assert hit is not None, f"the example has no id {wanted}"
        return hit
    return locate


def _round(d):
    return d["rounds"][0]


def _props(wanted):
    return lambda d: _at(wanted)(d)["props"]


def _cell(d):
    return _props("t-order-fields")(d)["rows"][0][2]


def _note(item_id, rnd=1):
    return {"id": f"N-{rnd}-{item_id}", "round": rnd, "target": item_id,
            "text": "Accepts it.", "deleted": False}


def _set(path_fn, key, value):
    def mutate(d):
        path_fn(d)[key] = value
    return mutate


def _drop(path_fn, key):
    def mutate(d):
        path_fn(d).pop(key)
    return mutate


def _extra_round(d):
    d["rounds"].append({"n": 2, "state": "current",
                        "banner": {"settled": [], "unlocks": [], "parked": []}, "items": []})


def _settle(state, notes=(), **settled):
    def mutate(d):
        _at("i-data")(d).update(state=state, settled=settled, notes=list(notes))
    return mutate


def _next_round(d):
    """Settle round 1 and open round 2, which carries the point still open."""
    for wanted in ("i-data", "i-flow"):
        _at(wanted)(d).update(state="settled_by_mark",
                              settled={"by": "mark", "round": 1, "signal": "accept"})
    _round(d)["state"] = "settled"
    d["rounds"].append({
        "n": 2, "state": "current",
        "banner": {"settled": ["The data change"], "unlocks": [], "parked": []},
        "items": [{"id": "i-format-2", "kind": "debate", "node": "n-format",
                   "body": {"type": "text", "props": {"text": "Carried from i-format."}}}],
    })
    return d


def _reuse_id_in_next_round(d):
    _next_round(d)["rounds"][1]["items"][0]["id"] = "i-data"


REFUSALS = [
    ("schema value", _set(lambda d: d, "schema", "afkv2.page/9"), "schema"),
    ("document field", _set(lambda d: d, "html_page", "<html>"), "unknown field"),
    ("round field", _set(_round, "extra", 1), "unknown field"),
    ("item field", _set(_at("i-data"), "options", []), "unknown field"),
    ("component field in a body", _set(lambda d: _at("i-data")(d)["body"], "label", "x"),
     "unknown field"),
    ("component field in a cell", _set(_cell, "extra", 1), "unknown field"),
    ("session skill", _set(lambda d: d["session"], "skill", "review"), "skill"),
    ("session started", _set(lambda d: d["session"], "started", "2026-01-05 09:00"), "started"),
    ("session field missing", _drop(lambda d: d["session"], "ticket"), "missing field"),
    ("two current rounds", _extra_round, "exactly one round is current"),
    ("no current round", _set(_round, "state", "settled"), "exactly one round is current"),
    ("round order", _set(_round, "n", 2), "n in order"),
    ("banner list missing", _drop(lambda d: _round(d)["banner"], "parked"), "parked"),
    ("banner not an object", _set(_round, "banner", "x"), "is not an object"),
    ("responses", _set(_round, "responses", [{"received": "x", "raw": "x", "signals": []}]),
     "responses"),
    ("reply target", _set(lambda d: _round(d)["replies"][0], "about", ["i-missing"]),
     "must resolve"),
    ("reply without text", _drop(lambda d: _round(d)["replies"][0], "text"), "replies[0]: text"),
    ("item id twice", _set(_at("i-flow"), "id", "i-data"), "not unique"),
    ("item id not text", _set(_at("i-flow"), "id", 7), "item 7: id"),
    ("item id in a later round", _reuse_id_in_next_round, "not unique"),
    ("component id twice", _set(_at("g-modules"), "id", "t-order-fields"), "not unique"),
    ("component id not text", _set(_at("g-modules"), "id", 7), "children[0]: id"),
    ("map node id twice", _set(_at("n-data"), "id", "n-export"), "not unique"),
    ("item kind", _set(_at("i-data"), "kind", "question"), "kind"),
    ("item state", _set(_at("i-data"), "state", "closed"), "state"),
    ("item node", _set(_at("i-data"), "node", "n-missing"), "node must resolve"),
    ("item without body", _drop(_at("i-data"), "body"), "body"),
    ("note missing a field", _set(_at("i-data"), "notes", [{"id": "N-1-i-data"}]), "missing field"),
    ("note unknown field", _set(_at("i-data"), "notes", [{**_note("i-data"), "x": 1}]),
     "unknown field"),
    ("note id", _set(_at("i-data"), "notes", [{**_note("i-data"), "id": "n1"}]), "id (N-"),
    ("note round past the last", _set(_at("i-data"), "notes", [_note("i-data", 2)]),
     "notes[0]: round"),
    ("note round 0", _set(_at("i-data"), "notes", [_note("i-data", 0)]), "notes[0]: round"),
    ("note target not text", _set(_at("i-data"), "notes", [{**_note("i-data"), "target": 7}]),
     "notes[0]: target"),
    ("note target unknown", _set(_at("i-data"), "notes", [{**_note("i-data"), "target": "nope"}]),
     "target must resolve"),
    ("note text not text", _set(_at("i-data"), "notes", [{**_note("i-data"), "text": 7}]),
     "notes[0]: text"),
    ("note deleted not a flag", _set(_at("i-data"), "notes", [{**_note("i-data"), "deleted": "no"}]),
     "notes[0]: deleted"),
    ("note id twice", _set(_at("i-data"), "notes", [_note("i-data"), _note("i-data")]),
     "id not unique"),
    ("settled on an open point",
     _set(_at("i-data"), "settled", {"by": "mark", "round": 1, "signal": "x"}),
     "only on a settled point"),
    ("settled state without settled", _set(_at("i-data"), "state", "settled_by_mark"),
     "is not an object"),
    ("settled field", _settle("settled_by_mark", by="mark", round=1, signal="accept", x=1),
     "unknown field"),
    ("settled by differs from state", _settle("settled_by_mark", by="note", round=1, signal="accept"),
     "by (expected mark)"),
    ("settled round 0", _settle("settled_by_mark", by="mark", round=0, signal="accept"),
     "settled: round"),
    ("settled round past the last", _settle("settled_by_mark", by="mark", round=2, signal="accept"),
     "settled: round"),
    ("settled signal missing", _settle("settled_by_mark", by="mark", round=1), "settled: signal"),
    ("settled signal empty", _settle("settled_by_mark", by="mark", round=1, signal=""),
     "settled: signal"),
    ("note settle without reading",
     _settle("settled_by_note", [_note("i-data")], by="note", round=1, signal="N-1-i-data"),
     "reading"),
    ("note settle names no note",
     _settle("settled_by_note", [_note("i-data")], by="note", round=1, signal="N-1-i-flow",
             reading="x"),
     "must name a live note"),
    ("note settle by a write-in",
     _settle("settled_by_note", by="note", round=1, signal="write-in", reading="x"),
     "must name a live note"),
    ("note settle names a deleted note",
     _settle("settled_by_note", [{**_note("i-data"), "deleted": True}], by="note", round=1,
             signal="N-1-i-data", reading="x"),
     "must name a live note"),
    ("note settle names a steer",
     _settle("settled_by_note", [{**_note("i-data"), "target": "n-data"}], by="note", round=1,
             signal="N-1-i-data", reading="x"),
     "must name a live note"),
    ("map node round past the last", _set(_at("n-export"), "round", 2), "nodes[0].round"),
    ("map node round 0", _set(_at("n-export"), "round", 0), "nodes[0].round"),
    ("map node state", _set(_at("n-export"), "state", "done"), "state"),
    ("map nodes malformed", _set(_props("m-scope"), "nodes", ["x"]), "props.nodes"),
    ("unknown type", _set(lambda d: _at("i-data")(d)["body"], "children", [{"type": "button"}]),
     "unknown type"),
    ("html outside freestyle", _set(_at("i-data-question"), "html", "<b>x</b>"), "freestyle only"),
    ("chip without tone", _drop(lambda d: _cell(d)["props"], "tone"), "props.tone"),
    ("chip tone", _set(lambda d: _cell(d)["props"], "tone", "green"), "props.tone"),
    ("table row width", lambda d: _props("t-order-fields")(d)["rows"][0].pop(), "props.rows"),
    ("graph edge", _set(lambda d: _props("g-modules")(d)["edges"][0], "to", "g-missing"),
     "props.edges"),
    ("graph group", _set(_at("g-controller"), "group", "nope"), "group"),
    ("sequence actor", _set(lambda d: _props("q-export")(d)["messages"][0], "to", "nobody"),
     "props.messages"),
    ("sequence actors malformed", _set(_props("q-export"), "actors", ["user"]), "props.actors"),
    ("run strip lanes", _set(_at("r-export-run"), "props", {}), "props.current"),
    ("freestyle reason", _set(_at("f-score-radar"), "props", {}), "props.reason"),
    ("freestyle id", _drop(_at("f-score-radar"), "id"), "id"),
    ("freestyle html", _drop(_at("f-score-radar"), "html"), "html"),
]


@pytest.mark.parametrize("mutate, field", [(m, f) for _, m, f in REFUSALS],
                         ids=[name for name, _, _ in REFUSALS])
def test_fake_refuses_a_broken_document(mutate, field):
    doc = _example_v0()
    mutate(doc)
    with pytest.raises(Refused, match=re.escape(field)):
        check_document(doc)


@pytest.mark.parametrize("state, settled, notes", [
    ("settled_by_note", {"by": "note", "round": 1, "signal": "N-1-i-data",
                         "reading": "Accepts the field change."}, [_note("i-data")]),
    ("settled_by_note", {"by": "note", "round": 1, "signal": "N-1-i-data",
                         "reading": "Accepts the field change."},
     [{**_note("i-data"), "target": "i-data-question"}]),
    ("settled_by_mark", {"by": "mark", "round": 1, "signal": "accept"}, []),
], ids=["by-note", "by-note-on-a-component", "by-mark"])
def test_fake_accepts_a_settled_point(state, settled, notes):
    doc = _example_v0()
    _at("i-data")(doc).update(state=state, settled=copy.deepcopy(settled), notes=notes)
    check_document(doc)


def test_fake_accepts_a_settled_round_and_a_next_round():
    doc = _next_round(_example_v0())
    components = check_document(doc)
    assert any(c.get("props", {}).get("text") == "Carried from i-format." for c in components)


def _note_on_an_older_card():
    """The card as the real ingest leaves it; the responses of the round are left out, because only ingest writes them."""
    doc = _next_round(_example_v0())
    item = _at("i-data")(doc)
    del item["settled"]
    item.update(state="open", notes=[{**_note("i-data", 2), "id": "N-2-i-data-1"}])
    return doc


def test_fake_accepts_a_note_on_an_older_card():
    check_document(_note_on_an_older_card())


def test_real_ingest_leaves_this_shape_on_an_older_card(tmp_path):
    doc, raw = tmp_path / "doc.json", tmp_path / "raw.txt"
    doc.write_text(json.dumps(_next_round(_example_v0())), "utf-8")
    raw.write_text("[round R-2]\ni-data — | Accepts it.", "utf-8")
    run = subprocess.run([sys.executable, str(ENGINE), "ingest", str(doc), "--raw-file", str(raw)],
                         capture_output=True, text=True, encoding="utf-8", timeout=60,
                         env={**os.environ, "LOCALAPPDATA": str(tmp_path / "local")})
    assert run.returncode == 0, run.stdout + run.stderr
    assert json.loads(run.stdout)["reopened"] == ["i-data"]
    after = json.loads(doc.read_text("utf-8"))
    card = copy.deepcopy(_at("i-data")(_note_on_an_older_card()))
    notes = card.pop("notes")
    assert after["schema"] == SCHEMA_1, "ingest writes format 1"
    assert _find(after, "i-data") == card
    assert after["notes"] == [{**note, "item": "i-data"} for note in notes]
    assert [rnd["state"] for rnd in after["rounds"]] == ["settled", "current"]
    check = subprocess.run([sys.executable, str(ENGINE), "check", str(doc)], capture_output=True, text=True,
                           encoding="utf-8", timeout=60,
                           env={**os.environ, "LOCALAPPDATA": str(tmp_path / "local")})
    assert check.returncode == 0, check.stdout + check.stderr


def test_examples_carry_no_note_and_no_response():
    for label, doc in all_documents():
        for rnd in doc["rounds"]:
            assert not rnd.get("responses"), label
            assert not any(item.get("notes") for item in rnd["items"]), label


def _entry_section(name, heading):
    text = (PAGES_DIR / name).read_text("utf-8")
    return text.split(heading + "\n", 1)[1].split("\n## ", 1)[0]


# The round pass and the answer rules moved to the use-lavish skill (SDD §14 row "visualize guide"; PRD AC-005):
# the guide holds how each component holds, looks and is used, and no rule for reading or answering a round.
MOVED_RULES = (
    "When the human sends a round",
    "with a clear note and no signal that disagrees",
    "Then mark the round `settled` and append the next round",
    "Read every note",
    "Treat Round 0 input as unverified",
    "word for word",
    "group of notes",
    "State your reading",
    "When\n2 steers",
    "Fold long text and secondary detail",
    "A heading states the conclusion",
    "Never repeat the human's note",
)


@pytest.mark.parametrize("rule", MOVED_RULES)
def test_the_guide_holds_no_rule_for_reading_or_answering_a_round(rule):
    text = _guide_text()
    assert " ".join(rule.split()) not in " ".join(text.split()), rule


def test_the_notes_page_shows_the_session_table_of_format_1():
    """PR #171 finding f5: the How it looks section describes the current notes table."""
    looks = " ".join(_entry_section("notes-and-replies.md", "## How it looks").split())
    for fact in ("`# | Where you wrote it | Noted text | Your note | My answer / what changed`",
                 "every note and every answer of the session", "card notes included",
                 "The current round and the round before stay open",
                 "its own closed group", "the note ids in its `notes`"):
        assert fact in looks, fact
    assert "Earlier rounds" not in looks


def test_the_notes_page_holds_the_answer_of_format_1():
    """Ruling D-38: Holds and the Example show the format 1 answer {text, notes, changed}; about is format 0 only."""
    holds = " ".join(_entry_section("notes-and-replies.md", "## Holds").split())
    assert "`rounds[].replies[]` with `text`, `notes` and `changed`" in holds
    assert "`about` is read on format 0 pages only" in holds
    found = fragments(PAGES_DIR / "notes-and-replies.md")
    assert [(level, set(frag)) for level, frag in found] == [("answer", {"text", "notes", "changed"})]


# Each component page states the format 1 marks: the fields, how they look, when to use them (SDD §8 row "visualize").
PART_PAGES = ("graph.md", "map.md", "run-strip.md", "sequence.md")


@pytest.mark.parametrize("name", PART_PAGES)
def test_a_part_page_states_tip_and_you(name):
    holds = " ".join(_entry_section(name, "## Holds").split())
    assert "`tip`" in holds and "`you`" in holds and "300 characters" in holds
    assert "YOU" in _entry_section(name, "## How it looks")
    use = _entry_section(name, "## Use it when")
    assert "`you`" in use and "`tip`" in use
    marked = [frag for level, frag in fragments(PAGES_DIR / name)]
    assert any('"you": true' in json.dumps(frag) and '"tip":' in json.dumps(frag) for frag in marked)


def test_the_sequence_page_states_the_message_tone():
    holds = " ".join(_entry_section("sequence.md", "## Holds").split())
    assert "`tone` (`removed`, `kept` or `new`)" in holds
    assert "tone" in _entry_section("sequence.md", "## How it looks")
    assert any('"tone": "removed"' in json.dumps(frag) for _, frag in fragments(PAGES_DIR / "sequence.md"))


def test_the_chip_page_states_each_state_and_certainty_tone():
    holds = _entry_section("chip-and-text.md", "## Holds")
    for tone in sorted(STATE_TONES):
        assert re.search(rf"^\| `{tone}` \| [^|]+ \| [^|]+ \|$", holds, re.M), tone
    assert "symbol" in _entry_section("chip-and-text.md", "## How it looks")
    assert "certainty" in _entry_section("chip-and-text.md", "## Use it when")
    used = {frag_tone for _, frag in fragments(PAGES_DIR / "chip-and-text.md")
            for frag_tone in re.findall(r'"tone": "(\w+)"', json.dumps(frag))}
    assert used & STATE_TONES


def test_the_chip_page_states_value_chips_and_the_component_tip():
    holds = " ".join(_entry_section("chip-and-text.md", "## Holds").split())
    for fact in ("`set`", "`value_sets`", "`{name: {values, ordered}}`", "a tone or a set, never both", "`tip`",
                 "300 characters"):
        assert fact in holds, fact
    looks = " ".join(_entry_section("chip-and-text.md", "## How it looks").split())
    for fact in ("same colour on the whole page", "strong colour to a faint one", "YOU", "8 different colours"):
        assert fact in looks, fact
    use = _entry_section("chip-and-text.md", "## Use it when")
    assert "value chip" in use and "`tip`" in use
    documents = [frag for level, frag in fragments(PAGES_DIR / "chip-and-text.md") if level == "document"]
    assert any(doc["schema"] == SCHEMA_1 and doc.get("value_sets") and '"set": ' in json.dumps(doc)
               and '"tip": ' in json.dumps(doc) for doc in documents)


@pytest.mark.parametrize("mutate, field", [
    (lambda c: c["props"].update(set="size"), "names no value set"),
    (lambda c: c["props"].update(text="severe"), "no value of the set"),
    (lambda c: c["props"].update(tone="new"), "a tone or a set"),
], ids=["unknown set", "value outside its set", "tone and set"])
def test_fake_refuses_a_value_chip_that_does_not_resolve(mutate, field):
    doc = {"schema": SCHEMA_1,
           "session": {"id": "s-wrap", "skill": "grill", "feature": "example", "ticket": "PROJ-123",
                       "started": "2026-01-01T09:00:00Z", "step": "Requirements grill"},
           "maps": [], "notes": [], "value_sets": {"risk": {"values": ["high", "low"], "ordered": True}},
           "rounds": [{"n": 1, "state": "current", "banner": {"settled": [], "unlocks": [], "parked": []},
                       "items": [{"id": "i-a", "kind": "info",
                                  "body": {"type": "chip", "props": {"text": "high", "set": "risk"}}}]}]}
    check_document(copy.deepcopy(doc))
    mutate(doc["rounds"][0]["items"][0]["body"])
    with pytest.raises(Refused, match=re.escape(field)):
        check_document(doc)


def test_the_page_layout_states_the_session_table_of_every_note():
    """Ruling D-39: the session notes table holds every note, card notes included, with per-round folds."""
    layout = " ".join(SKILL_MD.read_text("utf-8").split("## Page layout\n", 1)[1].split("\n## ", 1)[0].split())
    assert "every note of the session, card notes included" in layout and "one fold per round" in layout
    assert "stand on no card" not in layout


def _frontmatter(path):
    text = path.read_text("utf-8")
    assert text.startswith("---\n"), f"{path} has no frontmatter"
    head = text.split("---\n", 2)[1]
    return dict(line.split(": ", 1) for line in head.strip().splitlines())


def test_every_skill_file_has_agent_skills_frontmatter():
    files = list(SKILL_DIR.rglob("SKILL.md"))
    assert files == [SKILL_MD]
    meta = _frontmatter(SKILL_MD)
    assert meta.get("name") == "visualize"
    assert len(meta.get("description", "")) > 40


def test_the_frontmatter_names_page_format_1():
    description = _frontmatter(SKILL_MD)["description"]
    assert SCHEMA_1 in description and SCHEMA not in description


def test_one_entry_per_catalog_component():
    pages = {p.name for p in PAGES_DIR.glob("*.md")}
    assert pages == set(CATALOG.values()) | set(CHART_PAGES.values()) | set(TEXT_PAGES.values())
    index = SKILL_MD.read_text("utf-8")
    for cmp_id, name in CATALOG.items():
        text = (PAGES_DIR / name).read_text("utf-8")
        for section in ENTRY_SECTIONS:
            assert section in text, f"{cmp_id} ({name}) has no {section!r}"
        assert fragments(PAGES_DIR / name), f"{cmp_id} ({name}) has no example fragment"
        assert f"components/{name}" in index, f"SKILL.md does not point at {name}"


@pytest.mark.parametrize("form", sorted(CHART_PAGES))
def test_each_chart_has_a_page_with_its_props_its_look_and_when_to_use_it(form):
    name = CHART_PAGES[form]
    kind = name.removesuffix(".md")
    text = (PAGES_DIR / name).read_text("utf-8")
    for section in ENTRY_SECTIONS:
        assert section in text, f"{name} has no {section!r}"
    holds = " ".join(_entry_section(name, "## Holds").split())
    assert f"Type `{kind}`" in holds and "`caption`" in holds
    for field in sorted(CHART_FIELDS[kind]):
        assert f"`{field}`" in holds, field
    assert "colour" in _entry_section(name, "## How it looks"), "the page states the cue beside the colour (PR-07)"
    found = fragments(PAGES_DIR / name)
    assert found and all(level == "component" and frag["type"] == kind and frag["props"]["caption"]
                         for level, frag in found)


def test_the_components_table_has_a_row_for_each_chart_page_and_the_fields_name_the_tip():
    index = SKILL_MD.read_text("utf-8")
    rows = [line for line in index.splitlines() if line.startswith("|")]
    for name in CHART_PAGES.values():
        kind = name.removesuffix(".md")
        assert any(f"`components/{name}`" in line and f"type `{kind}`" in line for line in rows), name
    fields = index[index.index("takes an open `style` field"):index.index("## Page layout")]
    assert "`tip`" in fields and "300" in fields, "SKILL.md states no component tip beside style and fold (f4)"


@pytest.mark.parametrize("kind", sorted(TEXT_PAGES))
def test_the_diagram_code_and_diff_components_each_have_a_page(kind):
    name = TEXT_PAGES[kind]
    text = (PAGES_DIR / name).read_text("utf-8")
    for section in ENTRY_SECTIONS:
        assert section in text, f"{name} has no {section!r}"
    holds = " ".join(_entry_section(name, "## Holds").split())
    assert f"Type `{kind}`" in holds
    for field in sorted(TEXT_FIELDS[kind]):
        assert f"`{field}`" in holds, field
    found = fragments(PAGES_DIR / name)
    assert found and all(level == "component" and frag["type"] == kind for level, frag in found)


def test_the_diagram_page_names_each_diagram_text_kind_and_the_text_fallback():
    text = " ".join((PAGES_DIR / "diagram.md").read_text("utf-8").split())
    for kind in ("stateDiagram", "erDiagram", "classDiagram", "flowchart", "gantt", "quadrantChart", "sankey",
                 "mindmap", "treemap", "gitGraph", "xychart"):
        assert kind in text, kind
    assert "as text" in text and "/afkv2:setup" not in text


def test_the_diff_page_shows_red_minus_and_green_plus():
    look = _entry_section("diff.md", "## How it looks")
    assert "red" in look and "green" in look and "`-`" in look and "`+`" in look


def test_the_fake_refuses_a_diagram_with_no_caption():
    with pytest.raises(Refused, match="caption"):
        check_document(wrap("component", {"type": "diagram", "props": {"text": "flowchart LR; a --> b"}}))


def test_the_fake_refuses_a_chart_with_no_caption():
    frag = {"type": "bars", "props": {"items": [{"label": "a", "value": 1}]}}
    with pytest.raises(Refused, match="caption"):
        check_document(wrap("component", frag))


# The forms a chart component draws, as a freestyle reason would name them (D-49).
CHART_FORM_WORDS = ("line chart", "bar chart", "bullet", "box plot", "range bar", "signed bar", "flame",
                    "sparkline", "waterfall", "tile")


@pytest.mark.parametrize("name,doc", all_documents(), ids=lambda v: v if isinstance(v, str) else "")
def test_no_freestyle_example_draws_a_form_that_a_chart_component_draws(name, doc):
    reasons = [c["props"]["reason"].lower() for c in check_document(doc) if c["type"] == "freestyle"]
    assert not [r for r in reasons for word in CHART_FORM_WORDS if word in r], name


def test_fragment_levels_are_known():
    found = all_fragments()
    assert found
    for name, level, _ in found:
        assert level in LEVELS, f"{name}: unknown fragment level {level}"


@pytest.mark.parametrize("label, doc", all_documents(), ids=lambda v: v if isinstance(v, str) else "")
def test_example_uses_only_schema_v0_fields(label, doc):
    check_document(doc)


def test_every_whole_example_document_carries_the_schema_value():
    whole = [frag for _, level, frag in all_fragments() if level == "document"]
    whole.append(_example())
    for doc in whole:
        assert doc["schema"] in (SCHEMA, SCHEMA_1)


def test_all_components_document_uses_every_component():
    """Ruling D-50: format 1, with every component, the charts, the diagram text, the code block and the diff included."""
    doc = _example()
    assert doc["schema"] == SCHEMA_1
    components = check_document(doc)
    types = {c["type"] for c in components}
    assert types >= {"map", "graph", "table", "sequence", "run-strip", "chip", "text", "freestyle",
                     *CHART_FIELDS, *TEXT_FIELDS}
    current = next(r for r in doc["rounds"] if r["state"] == "current")
    assert any(current["banner"].values()), "round banner is empty"
    assert current.get("replies"), "no agent reply"
    assert {i["kind"] for i in current["items"]} >= {"decided", "confirm", "debate"}
    assert any(i.get("node") for i in current["items"]), "no card links to a map node"
    chip_in_cell = any(
        isinstance(cell, dict) and cell["type"] == "chip"
        for c in components if c["type"] == "table"
        for row in c["props"]["rows"] for cell in row)
    assert chip_in_cell, "no chip inside a table cell"
    tones = {c["props"].get("tone") for c in components if c["type"] in ("chip", "text")}
    assert tones >= TONES


def _guide_text():
    return "\n".join(p.read_text("utf-8") for p in SKILL_DIR.rglob("*") if p.is_file())


def test_guide_states_documents_only_and_the_freestyle_escape():
    text = SKILL_MD.read_text("utf-8")
    assert "never write page HTML" in text
    assert "freestyle" in text and "props.reason" in text
    assert "candidate component" in text


def test_guide_states_the_picture_before_a_critical_aspect_question():
    text = SKILL_MD.read_text("utf-8")
    section = text.split("## Picture before a critical-aspect question", 1)
    assert len(section) == 2, "no picture rule section"
    rule = section[1].split("\n## ", 1)[0]
    for word in ("current state", "code area", "data", "flow"):
        assert word in rule


def test_guide_uses_no_v1_name():
    v1 = V1_WORD
    for path in SKILL_DIR.rglob("*"):
        rel = path.relative_to(SKILL_DIR).as_posix()
        assert not v1.search(rel), rel
        if path.is_file():
            hits = v1.findall(path.read_text("utf-8"))
            assert not hits, f"{rel}: {hits}"


def test_guide_names_no_upstream_caller():
    text = _guide_text()
    refs = set(re.findall(r"/afkv2:[\w-]+", text))
    assert refs <= {"/afkv2:visualize"}, refs
    assert not re.search(r"\b(called|invoked|run) by\b", text, re.I)


@pytest.mark.parametrize("label, doc",
                         [*all_documents(), ("note on an older card", _note_on_an_older_card())],
                         ids=lambda v: v if isinstance(v, str) else "")
def test_engine_check_accepts_every_example(label, doc, tmp_path):
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(doc), "utf-8")
    run = subprocess.run([sys.executable, str(ENGINE), "check", str(path)],
                         capture_output=True, text=True, timeout=60,
                         env={**os.environ, "LOCALAPPDATA": str(tmp_path / "local")})
    assert run.returncode == 0, run.stdout + run.stderr
    assert json.loads(run.stdout)["ok"] is True
