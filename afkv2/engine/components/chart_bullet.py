"""Bullet graph (K-35): one measure with a goal and named bands. A bar for the value, a tick for the target and the
bands behind, each band one strength of one hue with its name written on it. The line under it writes the value,
the target and the band of the value."""

from components.chart_svg import (LABEL, NUMBER, UNIT, WIDTH, chart_schema, clip, entries, label_width, line,
                                  mix, number, rect, scale, svg_frame, text, too_many, unfinite)
from registry import register_component

HEIGHT, MAX_BANDS = 62, 5
STRENGTHS = [55, 38, 24, 15, 9]
BAND_TOP, BAND_HEIGHT, BAR_TOP, BAR_HEIGHT = 6, 30, 19, 10


def check_bullet(props):
    found = too_many(props, "bands", MAX_BANDS) + unfinite(props)
    start, bands = props.get("start", 0), props["bands"]
    edges = [start, *(band["upto"] for band in bands)]
    if any(a >= b for a, b in zip(edges, edges[1:])):
        found.append((("bands",), "each band must end above the band before it, and the first above start"))
        return found
    for field in ("value", "target"):
        if not start <= props[field] <= edges[-1]:
            found.append(((field,), f"must lie from start {number(start)} to the last band {number(edges[-1])}"))
    return found


def render_bullet(props, children):
    unit, start, bands = props.get("unit"), props.get("start", 0), props["bands"]
    left = label_width([props["label"]])
    place = scale(start, bands[-1]["upto"], left, WIDTH - 8)
    body = text(0, BAR_TOP + 9, clip(props["label"], left - 10), bold=True)
    edge = start
    for k, band in enumerate(bands):
        x, end = place(edge), place(band["upto"])
        body += rect(x, BAND_TOP, end - x, BAND_HEIGHT, fill=mix("neutral", STRENGTHS[k]))
        body += text(x + 4, BAND_TOP + 10, clip(band["label"], end - x - 6, 10), tone="dim", size=10)
        edge = band["upto"]
    body += rect(left, BAR_TOP, place(props["value"]) - left, BAR_HEIGHT, fill="ink")
    tick = place(props["target"])
    body += line(tick, BAND_TOP + 2, tick, BAND_TOP + BAND_HEIGHT - 2, tone="ink", width=3)
    where = next(band["label"] for band in bands if props["value"] <= band["upto"])
    summary = f"{number(props['value'], unit)} · target {number(props['target'], unit)} · {where}"
    body += text(left, HEIGHT - 6, summary, tone="dim")
    return svg_frame("bullet", props["caption"], WIDTH, HEIGHT, body, children)


register_component("bullet", chart_schema({
    "label": LABEL, "value": NUMBER, "target": NUMBER, "unit": UNIT, "start": NUMBER,
    "bands": entries({"upto": NUMBER, "label": {"type": "string", "minLength": 1, "maxLength": 30}}, ["upto", "label"]),
}, ["label", "value", "target", "bands"]), render_bullet, check=check_bullet)
