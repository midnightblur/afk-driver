"""Bars (K-02): sizes or counts compared across items, as horizontal bars sorted largest first with the value at
the end. A share of a whole (`split`) is one split bar with a numbered key, never a pie. Under 20 items with exact
values, a table reads better; signed differences take signed bars (RF-02)."""

from components.chart_svg import (COUNT, LABEL, UNIT, WIDTH, chart_schema, clip, entries, label_width, number,
                                  rect, scale, set_colour, svg_frame, text, text_width, too_many, unfinite)
from registry import register_component

ROW, BAR, GAP, MIN_PLOT, KEY_ROW, SPLIT_BAR, SWATCH, MIN_LABEL = 24, 14, 6, 120, 20, 24, 18, 60


def check_bars(props):
    found = too_many(props, "items") + unfinite(props)
    if props.get("split") and not sum(item["value"] for item in props["items"]) > 0:
        found.append((("items",), "a split bar needs a total above 0"))
    return found


def _ranked(props):
    return sorted(props["items"], key=lambda item: -item["value"])


def _bars(props):
    items, unit = _ranked(props), props.get("unit")
    left = label_width(item["label"] for item in items)
    room = max(text_width(number(item["value"], unit)) for item in items) + 2 * GAP
    width = max(WIDTH, left + MIN_PLOT + room)
    place = scale(0, max(items[0]["value"], 1e-9), left, width - room)
    body = ""
    for k, item in enumerate(items):
        top = k * ROW
        end = place(item["value"])
        body += text(0, top + 16, clip(item["label"], left - 10))
        body += rect(left, top + 5, end - left, BAR, fill="mark")
        body += text(end + GAP, top + 16, number(item["value"], unit), tone="dim")
    return body, len(items) * ROW + 4, width


def _split(props):
    items, unit = _ranked(props), props.get("unit")
    total = sum(item["value"] for item in items)
    keys = [(f"{k + 1}. ", f": {number(item['value'], unit)}, {round(100 * item['value'] / total)}%")
            for k, item in enumerate(items)]
    width = max(WIDTH, max(SWATCH + text_width(head + tail) for head, tail in keys) + MIN_LABEL)
    place = scale(0, total, 0, width)
    body, start = "", 0.0
    for k, item in enumerate(items):
        x, end = place(start), place(start + item["value"])
        body += rect(x, 0, end - x, SPLIT_BAR, fill=set_colour(k), stroke="ground")
        if end - x >= text_width(str(k + 1)) + 6:
            body += text((x + end) / 2, 16, str(k + 1), tone="back", anchor="middle", bold=True)
        start += item["value"]
    for k, item in enumerate(items):
        top = SPLIT_BAR + 8 + k * KEY_ROW
        body += rect(0, top + 3, 12, 12, fill=set_colour(k))
        head, tail = keys[k]
        label = clip(item["label"], width - SWATCH - text_width(head + tail))
        body += text(SWATCH, top + 13, head + label + tail)
    return body, SPLIT_BAR + 12 + len(items) * KEY_ROW, width


def render_bars(props, children):
    body, height, width = (_split if props.get("split") else _bars)(props)
    return svg_frame("bars", props["caption"], width, height, body, children)


register_component("bars", chart_schema({
    "items": entries({"label": LABEL, "value": COUNT}, ["label", "value"]), "unit": UNIT, "split": {"type": "boolean"},
}, ["items"]), render_bars, check=check_bars)
