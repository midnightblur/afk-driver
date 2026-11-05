"""Range bars (K-37): estimates of time, cost or size. One bar per item on a shared scale, low to high, a dot at the
likely value, the numbers at the end, and 1 line on what the range means: a single number reads as more exact than
it is."""

from html import escape

from components.chart_svg import (LABEL, NUMBER, UNIT, WIDTH, chart_schema, clip, dot, entries, label_width, mix,
                                  note_line, number, rect, scale, svg_frame, text, text_width, too_many, unfinite)
from registry import register_component

ROW, BAR, GAP = 24, 8, 8
MEANS = {"type": "string", "minLength": 1, "maxLength": 160}


def check_range(props):
    found = too_many(props, "items") + unfinite(props)
    found += [(("items", k), "must run low, likely, high, each at most the next")
              for k, item in enumerate(props["items"]) if not item["low"] <= item["likely"] <= item["high"]]
    return found


def _numbers(item, unit):
    return f"{number(item['low'])} to {number(item['high'], unit)}, likely {number(item['likely'])}"


def render_range(props, children):
    items, unit = props["items"], props.get("unit")
    left = label_width(item["label"] for item in items)
    room = max(text_width(_numbers(item, unit)) for item in items) + 2 * GAP
    place = scale(min(item["low"] for item in items), max(item["high"] for item in items), left, WIDTH - room)
    body = ""
    for k, item in enumerate(items):
        top = k * ROW
        low, high = place(item["low"]), place(item["high"])
        body += text(0, top + 16, clip(item["label"], left - 10))
        body += rect(low, top + 8, high - low, BAR, fill=mix("mark", 45), stroke="mark")
        body += dot(place(item["likely"]), top + 12, 5)
        body += text(high + GAP, top + 16, _numbers(item, unit), tone="dim")
    return svg_frame("range", props["caption"], WIDTH, len(items) * ROW + 4, body, children,
                     after=note_line(f"The range: {escape(props['means'])}"))


register_component("range", chart_schema({
    "items": entries({"label": LABEL, "low": NUMBER, "likely": NUMBER, "high": NUMBER},
                     ["label", "low", "likely", "high"]),
    "unit": UNIT, "means": MEANS,
}, ["items", "means"]), render_range, check=check_range)
