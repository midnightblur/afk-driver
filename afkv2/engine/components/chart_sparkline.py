"""Sparklines (K-48): several measures over time, side by side. One row per measure: its label, a tiny line on the
row's own scale, and the latest value beside it. Many trends in little space."""

from components.chart_svg import (LABEL, NUMBER, UNIT, chart_schema, clip, dot, entries, label_width, number,
                                  polyline, scale, svg_frame, text, text_width, too_many, unfinite)
from registry import register_component

ROW, LINE, GAP, PAD, MAX_VALUES = 22, 140, 8, 4, 400


def check_sparkline(props):
    found = too_many(props, "rows") + unfinite(props)
    for k, row in enumerate(props["rows"]):
        if not 2 <= len(row["values"]) <= MAX_VALUES:
            found.append((("rows", k, "values"), f"a sparkline takes 2 to {MAX_VALUES} values"))
    return found


def render_sparkline(props, children):
    rows = props["rows"]
    left = label_width(row["label"] for row in rows)
    latest = [number(row["values"][-1], row.get("unit")) for row in rows]
    width = left + LINE + 2 * GAP + max(text_width(words) for words in latest)
    body = ""
    for k, row in enumerate(rows):
        top, values = k * ROW, row["values"]
        across = scale(0, len(values) - 1, left, left + LINE)
        up = scale(min(values), max(values), top + ROW - PAD, top + PAD)
        placed = [(across(n), up(value)) for n, value in enumerate(values)]
        body += text(0, top + 15, clip(row["label"], left - 10))
        body += polyline(placed, width=1.5) + dot(*placed[-1], 2)
        body += text(left + LINE + GAP, top + 15, latest[k], bold=True)
    return svg_frame("sparkline", props["caption"], width, len(rows) * ROW + 2, body, children)


register_component("sparkline", chart_schema({
    "rows": entries({"label": LABEL, "values": {"type": "array", "items": NUMBER}, "unit": UNIT}, ["label", "values"]),
}, ["rows"]), render_sparkline, check=check_sparkline)
