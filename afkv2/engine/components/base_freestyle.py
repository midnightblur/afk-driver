"""Freestyle (CMP-10): any HTML or SVG fragment. The page marks each use."""

from html import escape

from registry import register_component


def render_freestyle(props, children):
    return ('<figure class="afkv2-freestyle" data-afkv2-freestyle="1">'
            f'<figcaption>Freestyle: {escape(props["reason"])}</figcaption>'
            f'<div class="afkv2-freestyle-body">{props["html"]}</div></figure>' + "".join(children))


register_component("freestyle", {
    "type": "object", "additionalProperties": False, "required": ["reason"],
    "properties": {"reason": {"type": "string", "minLength": 1}},
}, render_freestyle, takes_html=True)
