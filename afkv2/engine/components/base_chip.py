"""Chip and styled text (CMP-9), with the 4 semantic tones."""

from html import escape

from registry import register_component

TONES = ["removed", "kept", "new", "proposed"]


def render_chip(props, children):
    return (f'<span class="afkv2-chip afkv2-tone--{props["tone"]}">{escape(props["text"])}</span>'
            + "".join(children))


def render_text(props, children):
    tone = props.get("tone")
    style = f" afkv2-tone--{tone}" if tone else ""
    tail = f'<div class="afkv2-children">{"".join(children)}</div>' if children else ""
    return f'<div class="afkv2-text{style}"><p>{escape(props["text"])}</p>{tail}</div>'


register_component("chip", {
    "type": "object", "additionalProperties": False, "required": ["text", "tone"],
    "properties": {"text": {"type": "string"}, "tone": {"enum": TONES}},
}, render_chip, inline=True)

register_component("text", {
    "type": "object", "additionalProperties": False, "required": ["text"],
    "properties": {"text": {"type": "string"}, "tone": {"enum": TONES}},
}, render_text)
