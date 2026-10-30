"""Tests for the visualize skill: the authoring guide for page documents.

Until the page engine exists, every example is checked by a recorded fake of
the page document v0 contract (SDD §4 field tables). When the engine file
exists, every example also goes through `engine check` and must answer ok.
"""

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


def _text_list(value, where, field):
    _need(isinstance(value, list) and all(isinstance(v, str) for v in value), where, field)


def _check_props(comp, where, ids):
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
                    _check_component(cell, f"{where}.rows[{r}][{c}]", ids)
    elif kind in ("graph", "map"):
        nodes = props.get("nodes")
        _need(isinstance(nodes, list) and nodes, where, "props.nodes")
        groups = {g["id"] for g in props.get("groups", [])}
        node_ids = set()
        for n, node in enumerate(nodes):
            _need(isinstance(node.get("id"), str), where, f"props.nodes[{n}].id")
            _need(isinstance(node.get("label"), str), where, f"props.nodes[{n}].label")
            if kind == "map":
                _need(node.get("state") in NODE_STATES, where, f"props.nodes[{n}].state")
                _need(isinstance(node.get("round"), int) and node["round"] >= 1, where,
                      f"props.nodes[{n}].round")
                _need(node["id"] not in ids, where, f"node id {node['id']} not unique")
                ids.add(node["id"])
            _need(node.get("group") is None or node["group"] in groups, where,
                  f"props.nodes[{n}].group")
            node_ids.add(node["id"])
        for e, edge in enumerate(props.get("edges", [])):
            _need(edge.get("from") in node_ids and edge.get("to") in node_ids, where,
                  f"props.edges[{e}]")
    elif kind == "sequence":
        actors = {a["id"] for a in props.get("actors", [])}
        _need(actors, where, "props.actors")
        msgs = props.get("messages")
        _need(isinstance(msgs, list) and msgs, where, "props.messages")
        for m, msg in enumerate(msgs):
            _need(msg.get("from") in actors and msg.get("to") in actors, where,
                  f"props.messages[{m}]")
            _need(isinstance(msg.get("text"), str), where, f"props.messages[{m}].text")
    elif kind == "run-strip":
        lanes = [k for k in ("current", "proposed") if k in props]
        _need(lanes, where, "props.current or props.proposed")
        for lane in lanes:
            for s, step in enumerate(props[lane]):
                _need(isinstance(step.get("label"), str), where, f"props.{lane}[{s}].label")
                _need(step.get("tone") is None or step["tone"] in TONES, where,
                      f"props.{lane}[{s}].tone")
    else:
        raise Refused(f"{where}: unknown type {kind!r}")


def _check_component(comp, where, ids):
    _only(comp, COMPONENT_FIELDS, where)
    _need(isinstance(comp.get("type"), str), where, "type")
    if "id" in comp:
        _need(comp["id"] not in ids, where, f"id {comp['id']} not unique")
        ids.add(comp["id"])
    if "style" in comp:
        _need(isinstance(comp["style"], str), where, "style")
    _check_props(comp, where, ids)
    children = comp.get("children", [])
    _need(isinstance(children, list), where, "children")
    for i, child in enumerate(children):
        _check_component(child, f"{where}.children[{i}]", ids)


def _walk_components(comp):
    yield comp
    for child in comp.get("children", []):
        yield from _walk_components(child)
    if comp.get("type") == "table":
        for row in comp["props"]["rows"]:
            for cell in row:
                if isinstance(cell, dict):
                    yield from _walk_components(cell)


def check_document(doc):
    """Return every component of a valid document; raise Refused otherwise."""
    _only(doc, DOC_FIELDS, "document")
    _need(doc.get("schema") == SCHEMA, "document", f"schema (expected {SCHEMA})")
    session = doc.get("session")
    _only(session, SESSION_FIELDS, "session")
    _need(set(session) == SESSION_FIELDS, "session", "missing field")
    _need(session["skill"] in SKILLS, "session", "skill")
    _need(bool(ISO_UTC.match(session["started"])), "session", "started (ISO-8601 UTC)")
    ids = set()
    components = []
    for m, mp in enumerate(doc.get("maps", [])):
        _need(mp.get("type") == "map", f"maps[{m}]", "type (map)")
        _check_component(mp, f"maps[{m}]", ids)
        components.append(mp)
    node_ids = {n["id"] for mp in doc.get("maps", []) for n in mp["props"]["nodes"]}
    rounds = doc.get("rounds")
    _need(isinstance(rounds, list) and rounds, "document", "rounds")
    _need([r.get("n") for r in rounds] == list(range(1, len(rounds) + 1)), "rounds", "n in order")
    _need(sum(r.get("state") == "current" for r in rounds) == 1, "rounds",
          "exactly one round is current")
    for r in rounds:
        where = f"round {r.get('n')}"
        _only(r, ROUND_FIELDS, where)
        _need(r["state"] in ("current", "settled"), where, "state")
        _need("banner" in r and "items" in r, where, "banner and items")
        _only(r["banner"], BANNER_FIELDS, f"{where}.banner")
        for key, value in r["banner"].items():
            _text_list(value, f"{where}.banner", key)
        _need(not r.get("responses"), where, "responses (written only by ingest)")
        for p, reply in enumerate(r.get("replies", [])):
            _only(reply, REPLY_FIELDS, f"{where}.replies[{p}]")
            _need(isinstance(reply.get("text"), str), f"{where}.replies[{p}]", "text")
            _text_list(reply.get("about", []), f"{where}.replies[{p}]", "about")
        for item in r["items"]:
            iw = f"item {item.get('id')}"
            _only(item, ITEM_FIELDS, iw)
            _need(isinstance(item.get("id"), str), iw, "id")
            _need(item["id"] not in ids, iw, "id not unique")
            ids.add(item["id"])
            _need(item.get("kind") in ITEM_KINDS, iw, "kind")
            _need(item.get("state", "open") in POINT_STATES, iw, "state")
            _need(item.get("node") is None or item["node"] in node_ids, iw, "node must resolve")
            _need(not item.get("notes"), iw, "notes (minted by the engine)")
            _need("body" in item, iw, "body")
            _check_component(item["body"], f"{iw}.body", ids)
            components.extend(_walk_components(item["body"]))
    for r in rounds:
        for p, reply in enumerate(r.get("replies", [])):
            for target in reply.get("about", []):
                _need(target in ids, f"round {r['n']}.replies[{p}]", f"about {target} must resolve")
    return components


# Fragments: ```json fragment=<level> blocks in the guide.

FENCE = re.compile(r"```json fragment=(\w+)\n(.*?)\n```", re.S)
LEVELS = {"document", "round", "banner", "reply", "item", "component", "map"}


def fragments(path):
    return [(m.group(1), json.loads(m.group(2))) for m in FENCE.finditer(path.read_text("utf-8"))]


def wrap(level, frag):
    """Put a fragment into the smallest whole document that holds it."""
    if level == "document":
        return frag
    doc = {
        "schema": SCHEMA,
        "session": {"id": "s-wrap", "skill": "grill", "feature": "example",
                    "ticket": "PROJ-123", "started": "2026-01-01T09:00:00Z"},
        "maps": [],
        "rounds": [{"n": 1, "state": "current", "banner": {}, "items": []}],
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


def all_documents():
    docs = [("all-components.json", json.loads(ALL_COMPONENTS.read_text("utf-8")))]
    docs += [(f"{name}:{level}", wrap(level, frag)) for name, level, frag in all_fragments()]
    return docs




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
    whole.append(json.loads(ALL_COMPONENTS.read_text("utf-8")))
    for doc in whole:
        assert doc["schema"] == SCHEMA


@pytest.mark.parametrize("bad, field", [
    ({"schema": "afkv2.page/9"}, "schema"),
    ({"html_page": "<html>"}, "unknown field"),
])
def test_fake_refuses_a_broken_document(bad, field):
    doc = json.loads(ALL_COMPONENTS.read_text("utf-8"))
    doc.update(bad)
    with pytest.raises(Refused, match=field):
        check_document(doc)


def test_fake_refuses_an_unknown_component_type_and_html_outside_freestyle():
    doc = json.loads(ALL_COMPONENTS.read_text("utf-8"))
    body = doc["rounds"][-1]["items"][0]["body"]
    body["children"] = [{"type": "button", "props": {}}]
    with pytest.raises(Refused, match="unknown type"):
        check_document(doc)
    body["children"] = [{"type": "text", "props": {"text": "x"}, "html": "<b>x</b>"}]
    with pytest.raises(Refused, match="freestyle only"):
        check_document(doc)


def test_all_components_document_uses_every_component():
    doc = json.loads(ALL_COMPONENTS.read_text("utf-8"))
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
