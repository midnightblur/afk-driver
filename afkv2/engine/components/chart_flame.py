"""Flame graph (K-47): where a slow run spends its time. Each box is a function, its width its share of the root's
time, callers below their callees, so the widest boxes are where to look. Each box writes its name when it fits and
shows its time and share on hover."""

from components.chart_svg import (UNIT, WIDTH, COUNT, chart_schema, clip, mix, number, rect, svg_frame, text,
                                  unfinite)
from registry import register_component

ROW, BOX, MAX_DEPTH, MAX_FRAMES = 20, 18, 16, 500
STRENGTHS = (40, 25)
FRAME = {"type": "object", "additionalProperties": False, "required": ["name", "value"],
         "properties": {"name": {"type": "string", "minLength": 1, "maxLength": 80}, "value": COUNT,
                        "children": {"type": "array", "items": {"$ref": "#/$defs/frame"}}}}


def _frames(frame, path=("root",), depth=0):
    """`(path, depth, frame)` for the frame and every frame it calls, callers first."""
    yield path, depth, frame
    for k, child in enumerate(frame.get("children") or []):
        yield from _frames(child, (*path, "children", k), depth + 1)


def check_flame(props):
    found = unfinite(props)
    frames = list(_frames(props["root"]))
    if len(frames) > MAX_FRAMES:
        return found + [(("root",), f"holds {len(frames)} frames; a flame graph takes {MAX_FRAMES} at most")]
    if max(depth for _, depth, _ in frames) >= MAX_DEPTH:
        found.append((("root",), f"is deeper than {MAX_DEPTH} levels"))
    for path, _, frame in frames:
        if not frame["value"] > 0:
            found.append(((*path, "value"), "must be above 0"))
        elif sum(child["value"] for child in frame.get("children") or []) > frame["value"]:
            found.append(((*path, "children"), "the callees take more time than their caller"))
    return found


def render_flame(props, children):
    root, unit = props["root"], props.get("unit")
    depth = max(level for _, level, _ in _frames(root)) + 1
    share = WIDTH / root["value"]
    body = []

    def draw(frame, x, level):
        width, top = frame["value"] * share, (depth - 1 - level) * ROW
        part = round(100 * frame["value"] / root["value"])
        hover = f"{frame['name']}: {number(frame['value'], unit)}, {part}% of the total"
        body.append(rect(x, top, width, BOX, fill=mix("warn", STRENGTHS[level % 2]), stroke="ground", title=hover))
        name = clip(frame["name"], width - 8)
        if name:
            body.append(text(x + 4, top + 13, name))
        for child in frame.get("children") or []:
            draw(child, x, level + 1)
            x += child["value"] * share

    draw(root, 0.0, 0)
    return svg_frame("flame", props["caption"], WIDTH, depth * ROW, "".join(body), children)


register_component("flame", chart_schema({"root": {"$ref": "#/$defs/frame"}, "unit": UNIT}, ["root"],
                                         defs={"frame": FRAME}), render_flame, check=check_flame)
