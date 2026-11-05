"""Tile (K-01): one key number, large, with a short label, its range when it is an estimate, and how it is known:
a certainty chip and the source. Against a target, a bullet graph is the better form (RF-01)."""

from html import escape

from components.chart_svg import LABEL, NUMBER, UNIT, chart_schema, note_line, number, svg_frame, text, unfinite
from registry import register_component, render_component

GRADES = ["measured", "inferred", "estimated", "unverified"]
WIDTH, HEIGHT, RANGED = 300, 78, 98


def check_tile(props):
    found = list(unfinite(props))
    if ("low" in props) != ("high" in props):
        found.append((("high" if "low" in props else "low",), "a range takes both low and high"))
    elif "low" in props and not props["low"] <= props["value"] <= props["high"]:
        found.append((("low",), "the range must run from low to high and hold the value"))
    return found


def render_tile(props, children):
    unit = props.get("unit")
    body = text(16, 46, number(props["value"], unit), size=36, bold=True)
    body += text(16, 68, props["label"], tone="dim", size=13)
    ranged = "low" in props
    if ranged:
        body += text(16, 88, f"range {number(props['low'])} to {number(props['high'], unit)}", tone="dim")
    grade = render_component({"type": "chip", "props": {"text": props["grade"], "tone": props["grade"]}})
    return svg_frame("tile", props["caption"], WIDTH, RANGED if ranged else HEIGHT, body, children,
                     after=note_line(f'{grade} {escape(props["source"])}'))


register_component("tile", chart_schema({
    "value": NUMBER, "unit": UNIT, "low": NUMBER, "high": NUMBER, "label": LABEL, "grade": {"enum": GRADES},
    "source": {"type": "string", "minLength": 1, "maxLength": 160},
}, ["value", "label", "grade", "source"]), render_tile, check=check_tile)
