"""Round banner (CMP-1): round number, colour, what settled, what it unlocks, parked items."""

from html import escape

from registry import register_component

LISTS = (("settled", "What settled"), ("unlocks", "What it unlocks"), ("parked", "Parked"))


def _list(values):
    if not values:
        return '<p class="afkv2-none">Nothing.</p>'
    return "<ul>" + "".join(f"<li>{escape(value)}</li>" for value in values) + "</ul>"


def render_round_banner(props, children):
    n = props["n"]
    state = "current round" if props["current"] else "settled round"
    lists = "".join(f'<div class="afkv2-banner-list"><h3>{title}</h3>{_list(props[key])}</div>'
                    for key, title in LISTS)
    return (f'<header class="afkv2-banner" data-afkv2-banner="{n}" '
            f'style="--afkv2-round: {escape(props["colour"])}">'
            f'<h2><span class="afkv2-round-chip">R-{n}</span> Round {n}: {state}</h2>'
            f'<div class="afkv2-banner-lists">{lists}</div></header>' + "".join(children))


TEXT_LIST = {"type": "array", "items": {"type": "string"}}

register_component("round-banner", {
    "type": "object", "additionalProperties": False,
    "required": ["n", "colour", "current", "settled", "unlocks", "parked"],
    "properties": {"n": {"type": "integer", "minimum": 1}, "colour": {"type": "string"},
                   "current": {"type": "boolean"}, "settled": TEXT_LIST,
                   "unlocks": TEXT_LIST, "parked": TEXT_LIST},
}, render_round_banner)
