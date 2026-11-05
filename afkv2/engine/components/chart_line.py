"""Line chart (K-03): a number over days, runs or versions. Dated points joined by a line, the latest value
labelled, and a dashed, labelled target line when one exists. 2 or 3 points read better as a slope chart, many
lines as small charts side by side (RF-03)."""

from components.chart_svg import (NUMBER, UNIT, WIDTH, chart_schema, dot, entries, line, number, polyline, scale,
                                  svg_frame, text, text_width, too_many, unfinite)
from registry import register_component

HEIGHT, TOP, BOTTOM, GAP = 200, 14, 28, 8
MAX_POINTS, DOTTED = 400, 60
AT = {"type": "string", "minLength": 1, "maxLength": 30}


def check_line(props):
    found = too_many(props, "points", MAX_POINTS) + unfinite(props)
    if len(props["points"]) < 2:
        found.append((("points",), "a line needs at least 2 points"))
    return found


def render_line(props, children):
    points, unit, target = props["points"], props.get("unit"), props.get("target")
    values = [point["value"] for point in points] + ([target] if target is not None else [])
    low, high = min(values), max(values)
    left = max(text_width(number(low)), text_width(number(high))) + GAP
    latest = f"latest {number(points[-1]['value'], unit)}"
    right = WIDTH - text_width(latest) - 2 * GAP
    across = scale(0, len(points) - 1, left, right)
    up = scale(low, high, HEIGHT - BOTTOM, TOP)
    body = line(left, TOP, right, TOP) + line(left, HEIGHT - BOTTOM, right, HEIGHT - BOTTOM)
    body += text(left - GAP, TOP + 4, number(high), tone="dim", anchor="end")
    body += text(left - GAP, HEIGHT - BOTTOM + 4, number(low), tone="dim", anchor="end")
    if target is not None:
        body += line(left, up(target), right, up(target), tone="warn", width=1.5, dash=True)
        body += text(right, up(target) - 5, f"target {number(target, unit)}", tone="warn", anchor="end")
    placed = [(across(k), up(point["value"])) for k, point in enumerate(points)]
    body += polyline(placed)
    if len(points) <= DOTTED:
        body += "".join(dot(x, y, 2.5, "mark") for x, y in placed[:-1])
    x, y = placed[-1]
    body += dot(x, y, 4) + text(x + GAP, y + 4, latest, bold=True)
    body += text(left, HEIGHT - GAP, points[0]["at"], tone="dim")
    body += text(right, HEIGHT - GAP, points[-1]["at"], tone="dim", anchor="end")
    return svg_frame("line", props["caption"], WIDTH, HEIGHT, body, children)


register_component("line", chart_schema({
    "points": entries({"at": AT, "value": NUMBER}, ["at", "value"]), "unit": UNIT, "target": NUMBER,
}, ["points"]), render_line, check=check_line)
