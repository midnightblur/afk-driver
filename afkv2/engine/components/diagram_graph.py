"""Graph (CMP-5): nodes and arrows, with grouped boxes for module structure."""

from registry import register_component
from shell.diagram_boxes import boxes_schema, check_boxes, draw_boxes, nested_labels
from shell.diagram_parts import figure


def render_graph(props, children):
    return figure(props, draw_boxes(props), children)


register_component("graph", boxes_schema({}, []), render_graph, nested=nested_labels, check=check_boxes)
