"""Tile (K-01): one key number, large, with a short label, its range when it is an estimate, and how it is known:
a certainty chip and the source. Against a target, a bullet graph is the better form (RF-01)."""

from html import escape

from components.chart_svg import (LABEL, NUMBER, UNIT, chart_schema, note_line, number, svg_frame, text, text_width,
                                  unfinite)
from registry import register_component, render_component

GRADES = ["measured", "inferred", "estimated", "unverified"]
WIDTH, HEIGHT, RANGED, PAD, VALUE_SIZE, LABEL_SIZE = 300, 78, 98, 16, 36, 13


def check_tile(props):
    found = list(unfinite(props))
    if ("low" in props) != ("high" in props):
        found.append((("high" if "low" in props else "low",), "a range takes both low and high"))
    elif "low" in props and not props["low"] <= props["value"] <= props["high"]:
        found.append((("low",), "the range must run from low to high and hold the value"))
    return found


def render_tile(props, children):
    unit, ranged = props.get("unit"), "low" in props
    value = number(props["value"], unit)
    span = f"range {number(props['low'])} to {number(props['high'], unit)}" if ranged else ""
    width = max(WIDTH, 2 * PAD + max(text_width(value, VALUE_SIZE), text_width(props["label"], LABEL_SIZE),
                                     text_width(span)))
    body = text(PAD, 46, value, size=VALUE_SIZE, bold=True)
    body += text(PAD, 68, props["label"], tone="dim", size=LABEL_SIZE)
    if ranged:
        body += text(PAD, 88, span, tone="dim")
    grade = render_component({"type": "chip", "props": {"text": props["grade"], "tone": props["grade"]}})
    return svg_frame("tile", props["caption"], width, RANGED if ranged else HEIGHT, body, children,
                     after=note_line(f'{grade} {escape(props["source"])}'))


register_component("tile", chart_schema({
    "value": NUMBER, "unit": UNIT, "low": NUMBER, "high": NUMBER, "label": LABEL, "grade": {"enum": GRADES},
    "source": {"type": "string", "minLength": 1, "maxLength": 160},
}, ["value", "label", "grade", "source"]), render_tile, check=check_tile)
