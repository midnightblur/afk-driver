"""Map (CMP-3): a diagram that keeps the high-level view, coloured settled, open and current focus.

A scope map, whose arrows all stay inside one group, draws each group on its own canvas; the canvases sit
side by side and wrap to a stack on a narrow window. A map with an arrow between groups is one canvas.
"""

from html import escape

from registry import register_component
from shell.diagram_boxes import boxes_schema, check_boxes, draw_boxes, nested_labels
from shell.diagram_parts import figure

STATE_WORDS = {"settled": "settled", "open": "open", "focus": "current focus"}
HEAD_HEIGHT = 22


def _node_parts(node):
    state = node["state"]
    above = (f'<span class="afkv2-node-head"><span class="afkv2-node-state">{STATE_WORDS[state]}</span> '
             f'<span class="afkv2-node-round">R-{node["round"]}</span></span>')
    return f"afkv2-node--{state}", f' id="{escape(node["id"])}" data-afkv2-element="{escape(node["id"])}"', above


def _bands(props):
    """The props of each group, in group order, then of the nodes in no group; None when an arrow joins
    2 bands or the map has no group."""
    groups = props.get("groups") or []
    if not groups:
        return None
    band = {node["id"]: node.get("group") for node in props["nodes"]}
    edges = props.get("edges") or []
    if any(band[edge["from"]] != band[edge["to"]] for edge in edges):
        return None
    order = [group["id"] for group in groups] + [None]
    parts = []
    for group in order:
        nodes = [node for node in props["nodes"] if node.get("group") == group]
        if nodes:
            parts.append({**props, "nodes": nodes, "groups": [g for g in groups if g["id"] == group],
                          "edges": [edge for edge in edges if band[edge["from"]] == group]})
    return parts


def render_map(props, children):
    bands = _bands(props)
    if bands is None:
        return figure(props, draw_boxes(props, HEAD_HEIGHT, _node_parts), children)
    canvases = "".join(f'<div class="afkv2-map-group">{draw_boxes(part, HEAD_HEIGHT, _node_parts)}</div>'
                       for part in bands)
    return figure(props, f'<div class="afkv2-map-groups">{canvases}</div>', children)


register_component("map", boxes_schema({"state": {"enum": list(STATE_WORDS)}, "round": {"type": "integer", "minimum": 1}},
                                       ["state", "round"]),
                   render_map, nested=nested_labels, check=check_boxes)
