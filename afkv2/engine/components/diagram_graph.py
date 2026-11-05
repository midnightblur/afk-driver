"""Graph (CMP-5): nodes and arrows, with grouped boxes for module structure. A node may carry a tip and a
YOU mark."""

from components.diagram_marks import MARK_FIELDS, marks
from registry import register_component
from shell.diagram_boxes import boxes_schema, check_boxes, draw_boxes, nested_labels
from shell.diagram_parts import figure


def _node_parts(node):
    css, attrs = marks(node)
    return css.strip(), attrs, ""


def render_graph(props, children):
    return figure(props, draw_boxes(props, 0, _node_parts), children)


register_component("graph", boxes_schema(MARK_FIELDS, []), render_graph, nested=nested_labels, check=check_boxes)
