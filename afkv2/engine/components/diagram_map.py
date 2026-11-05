"""Map (CMP-3): a diagram that keeps the high-level view, coloured settled, open and current focus.

A map with groups (a scope map) draws each group on its own canvas; the canvases sit side by side and wrap
to a stack on a narrow window. An arrow inside a group is drawn; an arrow between groups is a line under
the groups: "<part> settles before <part>".
"""

from html import escape

from components.diagram_marks import MARK_FIELDS, marks
from registry import register_component
from shell.diagram_boxes import boxes_schema, check_boxes, draw_boxes, nested_labels
from shell.diagram_parts import figure

STATE_WORDS = {"settled": "settled", "open": "open", "focus": "current focus"}
HEAD_HEIGHT = 22


def _node_parts(node):
    state = node["state"]
    above = (f'<span class="afkv2-node-head"><span class="afkv2-node-state">{STATE_WORDS[state]}</span> '
             f'<span class="afkv2-node-round">R-{node["round"]}</span></span>')
    css, attrs = marks(node)
    return (f"afkv2-node--{state}{css}", f' id="{escape(node["id"])}" data-afkv2-element="{escape(node["id"])}"{attrs}',
            above)


def _bands(props):
    """The props of each group, in group order, then of the nodes in no group, each with the arrows inside
    it; then the arrows between groups. None when the map has no group."""
    groups = props.get("groups") or []
    if not groups:
        return None
    band = {node["id"]: node.get("group") for node in props["nodes"]}
    edges = props.get("edges") or []
    parts = []
    for group in [group["id"] for group in groups] + [None]:
        nodes = [node for node in props["nodes"] if node.get("group") == group]
        if nodes:
            parts.append({**props, "nodes": nodes, "groups": [g for g in groups if g["id"] == group],
                          "edges": [e for e in edges if band[e["from"]] == group == band[e["to"]]]})
    return parts, [edge for edge in edges if band[edge["from"]] != band[edge["to"]]]


def _order(props, crossing):
    """Each arrow between groups as one line."""
    if not crossing:
        return ""
    labels = {node["id"]: node["label"] for node in props["nodes"]}
    lines = "".join(f'<li>{escape(labels[e["from"]])} settles before {escape(labels[e["to"]])}</li>'
                    for e in crossing)
    return f'<ul class="afkv2-map-order">{lines}</ul>'


def render_map(props, children):
    bands = _bands(props)
    if bands is None:
        return figure(props, draw_boxes(props, HEAD_HEIGHT, _node_parts), children)
    parts, crossing = bands
    canvases = "".join(f'<div class="afkv2-map-group">{draw_boxes(part, HEAD_HEIGHT, _node_parts)}</div>'
                       for part in parts)
    return figure(props, f'<div class="afkv2-map-groups">{canvases}</div>{_order(props, crossing)}', children)


register_component("map", boxes_schema({"state": {"enum": list(STATE_WORDS)}, "round": {"type": "integer", "minimum": 1},
                                        **MARK_FIELDS},
                                       ["state", "round"]),
                   render_map, nested=nested_labels, check=check_boxes)
