"""Diagram text (EG-13, ADR-0006 design): Mermaid text that the engine draws as a picture, through the cache of
engine diagrams, with a 1-line caption (PR-13). The picture takes a note as a whole."""

from html import escape

import diagrams
from registry import register_component

CAPTION = {"type": "string", "minLength": 1, "maxLength": 160}
TEXT_LIMIT = 20000


def render_diagram(props, children):
    picture = diagrams.diagram_picture(props["text"], props.get("id"))
    return (f'<figure class="afkv2-diagram afkv2-diagram--text">{picture}'
            f'<figcaption class="afkv2-diagram-caption">{escape(props["caption"])}</figcaption></figure>'
            + "".join(children))


def diagram_targets(props):
    """A note on a picture names the SVG id of its theme: it stands for the diagram."""
    element = props.get("id")
    if not element:
        return {}
    return {diagrams.svg_id(diagrams.svg_base(element), theme): element for theme, _ in diagrams.THEMES}


register_component("diagram", {
    "type": "object", "additionalProperties": False, "required": ["caption", "text"],
    "properties": {"caption": CAPTION, "text": {"type": "string", "minLength": 1, "maxLength": TEXT_LIMIT}},
}, render_diagram, targets=diagram_targets, takes_id=True)
