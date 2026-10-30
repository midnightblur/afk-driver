"""Tests for the visualize skill: the authoring guide for page documents.

Until the page engine exists, every example is checked by a recorded fake of
the page document v0 contract (SDD §4 field tables). When the engine file
exists, every example also goes through `engine check` and must answer ok.
"""

import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
SKILL_DIR = PLUGIN / "skills" / "visualize"
SKILL_MD = SKILL_DIR / "SKILL.md"
PAGES_DIR = SKILL_DIR / "components"
ALL_COMPONENTS = SKILL_DIR / "examples" / "all-components.json"
ENGINE = PLUGIN / "engine" / "engine.py"

SCHEMA = "afkv2.page/0"

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

# Recorded fake of the page document v0 contract: SDD §4 field sets, props as the guide states them.

DOC_FIELDS = {"schema", "session", "maps", "rounds"}
SESSION_FIELDS = {"id", "skill", "feature", "ticket", "started"}
SKILLS = {"grill", "propose-solution", "propose-verification"}
ROUND_FIELDS = {"n", "state", "colour", "banner", "items", "responses", "replies"}
BANNER_FIELDS = {"settled", "unlocks", "parked"}
REPLY_FIELDS = {"text", "about"}
ITEM_FIELDS = {"id", "kind", "node", "state", "body", "settled", "notes"}
ITEM_KINDS = {"decided", "confirm", "debate", "signoff", "info"}
POINT_STATES = {"open", "blocked", "needs_reading", "settled_by_mark", "settled_by_note"}
SETTLED_FIELDS = {"by", "round", "signal", "reading"}
NOTE_FIELDS = {"id", "round", "target", "text", "deleted"}
COMPONENT_FIELDS = {"type", "id", "props", "style", "children", "html"}
NODE_STATES = {"open", "settled", "focus"}
TONES = {"removed", "kept", "new", "proposed"}
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
        _need(tone is None or tone in TONES, where, "props.tone")
        _need(kind == "text" or tone in TONES, where, "props.tone")
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
    elif kind == "run-strip":
        lanes = [k for k in ("current", "proposed") if k in props]
        _need(lanes, where, "props.current or props.proposed")
        for lane in lanes:
            for s, step in enumerate(_objects(props[lane], where, f"props.{lane}")):
                _need(isinstance(step.get("label"), str), where, f"props.{lane}[{s}].label")
                _need(step.get("tone") is None or step["tone"] in TONES, where,
                      f"props.{lane}[{s}].tone")
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


def _check_settled(item, iw, last_round):
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
        _need(settled["signal"] in {n["id"] for n in item.get("notes", [])}, f"{iw}.settled",
              "signal (must name a note on the item)")


def _check_notes(item, iw, last_round):
    for n, note in enumerate(_objects(item.get("notes", []), iw, "notes")):
        where = f"{iw}.notes[{n}]"
        _only(note, NOTE_FIELDS, where)
        _need(set(note) == NOTE_FIELDS, where, "missing field")
        rnd = note["round"]
        _need(isinstance(rnd, int) and 1 <= rnd <= last_round, where, "round")
        _need(note["id"] == f"N-{rnd}-{item['id']}", where, "id (N-<round>-<item>)")
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
        _need(item.get("state", "open") in POINT_STATES, iw, "state")
        _need(item.get("node") is None or item["node"] in node_ids, iw, "node must resolve")
        _check_notes(item, iw, last_round)
        _check_settled(item, iw, last_round)
        _need("body" in item, iw, "body")
        _check_component(item["body"], f"{iw}.body", ids, last_round)
        components.extend(_walk_components(item["body"]))


def _check_document(doc):
    _only(doc, DOC_FIELDS, "document")
    _need(doc.get("schema") == SCHEMA, "document", f"schema (expected {SCHEMA})")
    session = doc.get("session")
    _only(session, SESSION_FIELDS, "session")
    _need(set(session) == SESSION_FIELDS, "session", "missing field")
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
    for r in rounds:
        for p, reply in enumerate(r.get("replies", [])):
            for target in reply.get("about", []):
                _need(target in ids, f"round {r['n']}.replies[{p}]", f"about {target} must resolve")
    return components


def check_document(doc):
    """Return every component of a valid document; raise Refused otherwise."""
    try:
        return _check_document(doc)
    except (KeyError, TypeError, AttributeError) as exc:
        raise Refused(f"malformed document: {type(exc).__name__}: {exc}") from exc


# Fragments: ```json fragment=<level> blocks in the guide.

FENCE = re.compile(r"```json fragment=(\w+)\n(.*?)\n```", re.S)
LEVELS = {"document", "round", "banner", "reply", "item", "component", "map"}


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


def all_fragments():
    out = []
    for page in [SKILL_MD, *sorted(PAGES_DIR.glob("*.md"))]:
        for level, frag in fragments(page):
            out.append((page.name, level, frag))
    return out


def _example():
    return json.loads(ALL_COMPONENTS.read_text("utf-8"))


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


def _settle(state, **settled):
    def mutate(d):
        _at("i-data")(d).update(state=state, settled=settled, notes=[_note("i-data")])
    return mutate


def _next_round(d):
    """Make round 1 settled and round 2 current, with one new card."""
    _round(d)["state"] = "settled"
    d["rounds"].append({
        "n": 2, "state": "current",
        "banner": {"settled": ["The data change"], "unlocks": [], "parked": []},
        "items": [{"id": "i-format-2", "kind": "debate", "node": "n-format",
                   "body": {"type": "text", "props": {"text": "Reopens i-format."}}}],
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
    ("note round", _set(_at("i-data"), "notes", [_note("i-data", 2)]), "notes[0]: round"),
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
     _settle("settled_by_note", by="note", round=1, signal="N-1-i-data"), "reading"),
    ("note settle names no note",
     _settle("settled_by_note", by="note", round=1, signal="N-1-i-flow", reading="x"),
     "must name a note"),
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
    ("freestyle reason", _set(_at("f-load-curve"), "props", {}), "props.reason"),
    ("freestyle id", _drop(_at("f-load-curve"), "id"), "id"),
    ("freestyle html", _drop(_at("f-load-curve"), "html"), "html"),
]


@pytest.mark.parametrize("mutate, field", [(m, f) for _, m, f in REFUSALS],
                         ids=[name for name, _, _ in REFUSALS])
def test_fake_refuses_a_broken_document(mutate, field):
    doc = _example()
    mutate(doc)
    with pytest.raises(Refused, match=re.escape(field)):
        check_document(doc)


@pytest.mark.parametrize("state, settled", [
    ("settled_by_note", {"by": "note", "round": 1, "signal": "N-1-i-data",
                         "reading": "Accepts the field change."}),
    ("settled_by_mark", {"by": "mark", "round": 1, "signal": "accept"}),
])
def test_fake_accepts_a_settled_point(state, settled):
    doc = _example()
    _at("i-data")(doc).update(state=state, settled=copy.deepcopy(settled), notes=[_note("i-data")])
    check_document(doc)


def test_fake_accepts_a_settled_round_and_a_next_round():
    doc = _next_round(_example())
    components = check_document(doc)
    assert doc["rounds"][0]["state"] == "settled"
    assert doc["rounds"][1]["state"] == "current"
    assert any(c.get("props", {}).get("text") == "Reopens i-format." for c in components)


def test_examples_carry_no_note_and_no_response():
    for label, doc in all_documents():
        for rnd in doc["rounds"]:
            assert not rnd.get("responses"), label
            assert not any(item.get("notes") for item in rnd["items"]), label


def test_card_page_settled_example_has_the_schema_shape():
    text = (PAGES_DIR / "card.md").read_text("utf-8")
    found = re.findall(r"`(\{\"by\": .*?\})`", text)
    assert found, "card.md has no settled example"
    for raw in found:
        settled = json.loads(raw)
        assert set(settled) == SETTLED_FIELDS
        assert settled["by"] == "note"
        assert settled["signal"].startswith(f"N-{settled['round']}-")


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


def test_one_entry_per_catalog_component():
    pages = {p.name for p in PAGES_DIR.glob("*.md")}
    assert pages == set(CATALOG.values())
    index = SKILL_MD.read_text("utf-8")
    for cmp_id, name in CATALOG.items():
        text = (PAGES_DIR / name).read_text("utf-8")
        for section in ENTRY_SECTIONS:
            assert section in text, f"{cmp_id} ({name}) has no {section!r}"
        assert fragments(PAGES_DIR / name), f"{cmp_id} ({name}) has no example fragment"
        assert f"components/{name}" in index, f"SKILL.md does not point at {name}"


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
        assert doc["schema"] == SCHEMA


def test_all_components_document_uses_every_component():
    doc = _example()
    components = check_document(doc)
    types = {c["type"] for c in components}
    assert types >= {"map", "graph", "table", "sequence", "run-strip", "chip", "text", "freestyle"}
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
    v1 = re.compile(r"afk(?!v2)", re.I)
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


@pytest.mark.skipif(not ENGINE.exists(), reason="page engine not merged yet; the fake above checks")
@pytest.mark.parametrize("label, doc", all_documents(), ids=lambda v: v if isinstance(v, str) else "")
def test_engine_check_accepts_every_example(label, doc, tmp_path):
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(doc), "utf-8")
    run = subprocess.run([sys.executable, str(ENGINE), "check", str(path)],
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr
    assert json.loads(run.stdout)["ok"] is True
