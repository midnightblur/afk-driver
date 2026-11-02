"""Map (CMP-3): a diagram that keeps the high-level view, coloured settled, open and current focus."""

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
    return f"afkv2-node--{state}", f' data-afkv2-element="{escape(node["id"])}"', above


def render_map(props, children):
    return figure(props, draw_boxes(props, HEAD_HEIGHT, _node_parts), children)


register_component("map", boxes_schema({"state": {"enum": list(STATE_WORDS)}, "round": {"type": "integer", "minimum": 1}},
                                       ["state", "round"]),
                   render_map, nested=nested_labels, check=check_boxes)
