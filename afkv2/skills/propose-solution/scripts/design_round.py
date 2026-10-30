"""Write the page document of one propose-solution session (schema afkv2.page/0, SDD §4).

Verbs, run from the repository root:
  build --doc D --session S --ticket K --round-input F [--replace]
  next  --doc D

The grill's round builder writes the document. This script adds what only this skill knows: the
critical aspects in their fixed order, the layers from the top down, the human-locked aspects, the
fork cards, and the maps that show all three.

An item of the round input may name one of `aspect`, `layer` or `locked`, and may hold a `fork`.
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL.parent / "grill" / "scripts"))

import round_document as rd  # noqa: E402
from fork_cards import expand_fork  # noqa: E402
from grill_common import Parser, Refusal, read_json, serve  # noqa: E402

SKILL_NAME = "propose-solution"
GROUPS = {
    "aspect": {"file": "ASPECTS.md", "row": re.compile(r"^\| \d+ \| `([\w-]+)` \| ([^|]+?) \|", re.M),
               "map": "m-aspects", "title": "Critical aspects", "prefix": "aspect-", "edges": True},
    "layer": {"file": "DRAFT.md", "row": re.compile(r"^\| (L[1-9]) \| ([^|]+?) \|", re.M),
              "map": "m-layers", "title": "Design layers", "prefix": "layer-", "edges": True},
    "locked": {"file": "DRAFT.md", "row": re.compile(r"^\| (HL-[1-9]) \| ([^|]+?) \|", re.M),
               "map": "m-locked", "title": "Human-locked aspects", "prefix": "locked-", "edges": False},
}
ASPECT_KINDS = {"confirm", "debate"}


def group_rows(group):
    """The (key, label) rows of one group, in order, from the one file that owns them."""
    spec = GROUPS[group]
    return spec["row"].findall((SKILL / spec["file"]).read_text("utf-8"))


def group_keys(group):
    return [key for key, _ in group_rows(group)]


def node_id(group, key):
    return f"{GROUPS[group]['prefix']}{key.lower()}"


def _reserved_nodes():
    return {node_id(group, key) for group in GROUPS for key in group_keys(group)}


def _tagged(raw):
    """A round-input item with its tag turned into a map node, and its fork turned into a debate card."""
    if not isinstance(raw, dict):
        raise Refusal("bad-item", f"item without an id: {raw!r}")
    raw = dict(raw)
    where = f"item {raw.get('id')}"
    tags = [group for group in GROUPS if group in raw]
    if raw.get("node") in _reserved_nodes() or len(tags) > 1 or (tags and raw.get("node")):
        raise Refusal("bad-item", f"{where}: one of {sorted(GROUPS)} or one node of your own map, not both")
    if "fork" in raw:
        raw = expand_fork(raw)
    elif raw.get("kind") == "debate":
        raise Refusal("not-a-fork", f"{where}: a debate card comes from a `fork` field, so its options stand side by side")
    if not tags:
        if raw.get("kind") == "signoff":
            raise Refusal("signoff-untagged", f"{where}: a sign-off card names its aspect in `locked`")
        return raw
    group = tags[0]
    key = raw.pop(group)
    if key not in group_keys(group):
        raise Refusal("bad-item", f"{where}: {group} {key!r} is not one of {group_keys(group)}")
    raw["node"] = node_id(group, key)
    if group == "aspect":
        if raw.get("kind") not in ASPECT_KINDS:
            raise Refusal("aspect-kind", f"{where}: an aspect question is a `confirm` card or a fork, "
                                         f"so the human answers it; not {raw.get('kind')!r}")
        raw["critical"] = True
    if group == "locked" and raw.get("kind") != "signoff":
        raise Refusal("bad-item", f"{where}: `locked` names the aspect of a `signoff` card")
    return raw


def _empty():
    return {"maps": [], "rounds": []}


def _view(doc_path, replace=False):
    """The document as the next round will find it."""
    doc = read_json(doc_path) if Path(doc_path).exists() else _empty()
    if replace:
        rd._drop_unanswered_round(doc)
    return doc


def _live(doc, item, round_n):
    waiting = item["kind"] in rd.ASKING and item["state"] in ("open", "blocked", "needs_reading")
    return waiting and not rd._carried(doc, item, round_n)


def _cards(doc, node):
    return [(rnd["n"], item) for rnd in doc["rounds"] for item in rnd["items"] if item.get("node") == node]


def is_settled(doc, node):
    """True when the node has a card and no card of it still waits."""
    cards = _cards(doc, node)
    return bool(cards) and not any(_live(doc, item, n) for n, item in cards)


def _check_carriers(doc, items):
    """A card that carries a card of an aspect, a layer or a locked aspect stays on that node, so the node stays open."""
    nodes = {item["id"]: item.get("node") for rnd in doc["rounds"] for item in rnd["items"]}
    nodes.update({item["id"]: item.get("node") for item in items})
    reserved = _reserved_nodes()
    for item in items:
        for carried in item.get("carries") or []:
            if nodes.get(carried) in reserved and item.get("node") != nodes[carried]:
                raise Refusal("carry-node", f"item {item['id']} carries {carried}, so it must tag {nodes[carried]} too")


def _check_order(doc, items):
    asked = {node for rnd in doc["rounds"] for node in (item.get("node") for item in rnd["items"])}
    aspects_done = all(is_settled(doc, node_id("aspect", key)) for key in group_keys("aspect"))
    for item in items:
        node = item.get("node")
        for group in ("aspect", "layer"):
            sequence = [node_id(group, key) for key in group_keys(group)]
            if node in sequence:
                missed = [earlier for earlier in sequence[:sequence.index(node)] if earlier not in asked]
                if missed:
                    raise Refusal("out-of-order", f"item {item['id']}: ask {missed[0]} first; the order is fixed")
        drafting = node in {node_id(group, key) for group in ("layer", "locked") for key in group_keys(group)}
        if drafting and not aspects_done:
            raise Refusal("aspects-first", f"item {item['id']}: the draft waits until every critical aspect is settled")
        asked.add(node)


def _node_state(doc, node, items):
    if any(item.get("node") == node for item in items):
        return "focus"
    return "settled" if is_settled(doc, node) else "open"


def _design_maps(doc, items, own_maps):
    reserved = {spec["map"] for spec in GROUPS.values()}
    if own_maps is None:
        own_maps = [chart for chart in doc.get("maps") or [] if chart.get("id") not in reserved]
    elif any(isinstance(chart, dict) and chart.get("id") in reserved for chart in own_maps):
        raise Refusal("bad-round", f"the map ids {sorted(reserved)} belong to this skill")
    maps = []
    for group, spec in GROUPS.items():
        keys = group_keys(group)
        nodes = [{"id": node_id(group, key), "label": label, "state": _node_state(doc, node_id(group, key), items)}
                 for key, label in group_rows(group)]
        props = {"title": spec["title"], "nodes": nodes}
        if spec["edges"]:
            props["edges"] = [{"from": node_id(group, a), "to": node_id(group, b)} for a, b in zip(keys, keys[1:])]
        maps.append({"type": "map", "id": spec["map"], "props": props})
    return [*maps, *own_maps]


def build_design_round(doc_path, session, round_input, replace=False):
    """Check the round against the fixed orders, then let the grill's builder write it; write nothing on a refusal."""
    if not isinstance(round_input, dict) or not isinstance(round_input.get("items", []), list):
        raise Refusal("bad-round", "the round input is one JSON object, and items is a list")
    doc = _view(doc_path, replace)
    items = [_tagged(raw) for raw in round_input.get("items") or []]
    _check_carriers(doc, items)
    _check_order(doc, items)
    built = copy.deepcopy(round_input)
    built["items"] = items
    built["maps"] = _design_maps(doc, items, round_input.get("maps"))
    return rd.build_round_document(doc_path, session, built, None, replace)


def _entries(group, keys):
    labels = dict(group_rows(group))
    return [{"key": key, "label": labels[key]} for key in keys]


def next_step(doc):
    """Which aspects and layers are still to ask or to settle, and so which phase the session is in."""
    unsettled, unasked = {}, {}
    for group in GROUPS:
        keys = group_keys(group)
        unsettled[group] = [key for key in keys if _cards(doc, node_id(group, key))
                            and not is_settled(doc, node_id(group, key))]
        unasked[group] = [key for key in keys if not _cards(doc, node_id(group, key))]
    if unasked["aspect"] or unsettled["aspect"]:
        phase = "aspects"
    elif unasked["layer"] or unsettled["layer"] or unsettled["locked"]:
        phase = "draft"
    else:
        phase = "write"
    return {"ok": True, "phase": phase,
            "aspects_to_ask": _entries("aspect", unasked["aspect"]), "aspects_open": _entries("aspect", unsettled["aspect"]),
            "layers_to_ask": _entries("layer", unasked["layer"]), "layers_open": _entries("layer", unsettled["layer"]),
            "locked_open": _entries("locked", unsettled["locked"])}


def unfinished(doc):
    """What the design gate refuses: an aspect or a layer with no card, or with a card that still waits."""
    step = next_step(doc)
    failures = [f"aspect {entry['key']} has no card" for entry in step["aspects_to_ask"]]
    failures += [f"aspect {entry['key']} is not settled" for entry in step["aspects_open"]]
    failures += [f"layer {entry['key']} has no card" for entry in step["layers_to_ask"]]
    failures += [f"layer {entry['key']} is not settled" for entry in step["layers_open"]]
    failures += [f"aspect {entry['key']} is not signed" for entry in step["locked_open"]]
    return failures


def main(argv):
    parser = Parser(add_help=False)
    parser.add_argument("verb", choices=["build", "next"])
    parser.add_argument("--doc", required=True)
    parser.add_argument("--session")
    parser.add_argument("--ticket")
    parser.add_argument("--round-input")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    if args.verb == "next":
        return next_step(_view(args.doc))
    if not (args.session and args.ticket and args.round_input):
        raise Refusal("usage", "build needs --session, --ticket and --round-input", 2)
    feature = Path(args.doc).parent.parent.name
    session = {"id": args.session, "skill": SKILL_NAME, "feature": feature, "ticket": args.ticket}
    return build_design_round(args.doc, session, read_json(args.round_input), args.replace)


if __name__ == "__main__":
    sys.exit(serve(main))
