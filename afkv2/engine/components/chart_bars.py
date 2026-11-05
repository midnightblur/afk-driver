"""Bars (K-02): sizes or counts compared across items, as horizontal bars sorted largest first with the value at
the end. A share of a whole (`split`) is one split bar with a numbered key, never a pie. Under 20 items with exact
values, a table reads better; signed differences take signed bars (RF-02)."""

from components.chart_svg import (COUNT, LABEL, UNIT, WIDTH, chart_schema, clip, entries, label_width, number,
                                  rect, scale, set_colour, svg_frame, text, text_width, too_many, unfinite)
from registry import register_component

ROW, BAR, VALUE_ROOM, KEY_ROW, SPLIT_BAR = 24, 14, 84, 20, 24


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
    place = scale(0, max(items[0]["value"], 1e-9), left, WIDTH - VALUE_ROOM)
    body = ""
    for k, item in enumerate(items):
        top = k * ROW
        end = place(item["value"])
        body += text(0, top + 16, clip(item["label"], left - 10))
        body += rect(left, top + 5, end - left, BAR, fill="mark")
        body += text(end + 6, top + 16, number(item["value"], unit), tone="dim")
    return body, len(items) * ROW + 4


def _split(props):
    items, unit = _ranked(props), props.get("unit")
    total = sum(item["value"] for item in items)
    place = scale(0, total, 0, WIDTH)
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
        share = round(100 * item["value"] / total)
        body += text(18, top + 13, f"{k + 1}. {item['label']}: {number(item['value'], unit)}, {share}%")
    return body, SPLIT_BAR + 12 + len(items) * KEY_ROW


def render_bars(props, children):
    body, height = (_split if props.get("split") else _bars)(props)
    return svg_frame("bars", props["caption"], WIDTH, height, body, children)


register_component("bars", chart_schema({
    "items": entries({"label": LABEL, "value": COUNT}, ["label", "value"]), "unit": UNIT, "split": {"type": "boolean"},
}, ["items"]), render_bars, check=check_bars)
