"""Signed bars (K-38): faster or slower than before, over or under budget. Bars grow left and right of a zero line,
the sign is written in each label, and `below` and `above` name the 2 sides: the direction is the message."""

from components.chart_svg import (LABEL, NUMBER, UNIT, WIDTH, chart_schema, clip, entries, label_width, line, rect,
                                  scale, signed, svg_frame, text, text_width, too_many, unfinite)
from registry import register_component

ROW, BAR, GAP, HEAD = 24, 14, 6, 18
SIDE = {"type": "string", "minLength": 1, "maxLength": 30}
LEFT_ARROW, RIGHT_ARROW = "\u2190", "\u2192"


def check_signed_bars(props):
    return too_many(props, "items") + unfinite(props)


def render_signed_bars(props, children):
    items, unit = props["items"], props.get("unit")
    left = label_width(item["label"] for item in items)
    room = max(text_width(signed(item["value"], unit)) for item in items) + 2 * GAP
    zero = (left + room + WIDTH - room) / 2
    reach = max(abs(item["value"]) for item in items) or 1
    length = scale(0, reach, 0, zero - left - room)
    head = HEAD if props.get("below") or props.get("above") else 0
    height = head + len(items) * ROW + 4
    body = line(zero, 0, zero, height, tone="ink")
    if props.get("below"):
        body += text(zero - GAP, 12, f"{LEFT_ARROW} {props['below']}", tone="dim", anchor="end")
    if props.get("above"):
        body += text(zero + GAP, 12, f"{props['above']} {RIGHT_ARROW}", tone="dim")
    for k, item in enumerate(items):
        top, value = head + k * ROW, item["value"]
        size = length(abs(value))
        body += text(0, top + 16, clip(item["label"], left - 10))
        body += rect(zero - size if value < 0 else zero, top + 5, size, BAR, fill="neutral" if value < 0 else "mark")
        words = signed(value, unit)
        body += (text(zero - size - GAP, top + 16, words, tone="dim", anchor="end") if value < 0
                 else text(zero + size + GAP, top + 16, words, tone="dim"))
    return svg_frame("signed-bars", props["caption"], WIDTH, height, body, children)


register_component("signed-bars", chart_schema({
    "items": entries({"label": LABEL, "value": NUMBER}, ["label", "value"]), "unit": UNIT, "below": SIDE, "above": SIDE,
}, ["items"]), render_signed_bars, check=check_signed_bars)
