"""Round banner (CMP-1): round number, colour, what changed, what settled, what it unlocks, parked items.

`changed` is the round's list of changed elements as {id, label}, each a link; without it the banner
has no changed list (round 1).
"""

from html import escape

from registry import register_component

LISTS = (("settled", "What settled"), ("unlocks", "What it unlocks"), ("parked", "Parked"))
LIST_CLASS, CHANGED_CLASS = "afkv2-banner-list", "afkv2-banner-changed"


def _list(values):
    if not values:
        return '<p class="afkv2-none">Nothing.</p>'
    return "<ul>" + "".join(f"<li>{value}</li>" for value in values) + "</ul>"


def _changed(entries):
    if entries is None:
        return ""
    links = [f'<a href="#{escape(entry["id"])}">{escape(entry["label"])}</a>' for entry in entries]
    return f'<div class="{LIST_CLASS} {CHANGED_CLASS}"><h3>What changed</h3>{_list(links)}</div>'


def render_round_banner(props, children):
    n = props["n"]
    state = "current round" if props["current"] else "settled round"
    lists = "".join(f'<div class="{LIST_CLASS}"><h3>{title}</h3>{_list(list(map(escape, props[key])))}</div>'
                    for key, title in LISTS)
    return (f'<header class="afkv2-banner" data-afkv2-banner="{n}" '
            f'style="--afkv2-round: {escape(props["colour"])}">'
            f'<h2><span class="afkv2-round-chip">R-{n}</span> Round {n}: {state}</h2>'
            f'<div class="afkv2-banner-lists">{_changed(props.get("changed"))}{lists}</div></header>'
            + "".join(children))


TEXT_LIST = {"type": "array", "items": {"type": "string"}}
CHANGED = {"type": "object", "additionalProperties": False, "required": ["id", "label"],
           "properties": {"id": {"type": "string"}, "label": {"type": "string"}}}

register_component("round-banner", {
    "type": "object", "additionalProperties": False,
    "required": ["n", "colour", "current", "settled", "unlocks", "parked"],
    "properties": {"n": {"type": "integer", "minimum": 1}, "colour": {"type": "string"},
                   "current": {"type": "boolean"}, "settled": TEXT_LIST,
                   "unlocks": TEXT_LIST, "parked": TEXT_LIST, "changed": {"type": "array", "items": CHANGED}},
}, render_round_banner)
