"""Span waterfall (K-49): one request crosses several services and is slow. One bar per step on a shared time axis,
each step indented under its parent, its duration at the end. The slowest path is strong: from the root that ends
last, each step's child that ends last. A strong step carries the ◆ mark, so the path never rests on colour alone."""

from components.chart_svg import (COUNT, LABEL, UNIT, WIDTH, chart_schema, clip, entries, label_width, line, mix,
                                  number, rect, scale, svg_frame, text, text_width, too_many, unfinite)
from registry import register_component

ROW, BAR, GAP, HEAD, AXIS, INDENT, MAX_SPANS = 22, 12, 8, 18, 18, 12, 200
STRONG = "\u25c6"
KEY = f"{STRONG} the slowest path"
SPAN_ID = {"type": "string", "minLength": 1}


def check_waterfall(props):
    found = too_many(props, "spans", MAX_SPANS) + unfinite(props)
    seen = set()
    for k, span in enumerate(props["spans"]):
        if span["id"] in seen:
            found.append((("spans", k, "id"), f"id {span['id']!r} is used twice in this waterfall"))
        if span.get("parent") is not None and span["parent"] not in seen:
            found.append((("spans", k, "parent"), f"{span['parent']!r} names no earlier span of this waterfall"))
        seen.add(span["id"])
    return found


def _end(span):
    return span["start"] + span["duration"]


def slowest_path(spans):
    """The ids of the slowest path: the root that ends last, then each time the child that ends last."""
    path, parent = set(), None
    while True:
        below = [span for span in spans if span.get("parent") == parent]
        if not below:
            return path
        parent = max(below, key=_end)["id"]
        path.add(parent)


def _depths(spans):
    depth = {}
    for span in spans:
        depth[span["id"]] = depth[span["parent"]] + 1 if span.get("parent") is not None else 0
    return depth


def render_waterfall(props, children):
    spans, unit = props["spans"], props.get("unit")
    strong, depth = slowest_path(spans), _depths(spans)
    names = {span["id"]: f"{STRONG} {span['label']}" if span["id"] in strong else span["label"] for span in spans}
    left = label_width((" " * 2 * depth[span["id"]] + names[span["id"]] for span in spans), cap=220)
    durations = [number(span["duration"], unit) for span in spans]
    right = WIDTH - max(text_width(words) for words in durations) - 2 * GAP
    finish = max(_end(span) for span in spans)
    place = scale(0, finish or 1, left, right)
    body = text(0, 12, KEY, tone="dim")
    for k, span in enumerate(spans):
        top, bold = HEAD + k * ROW, span["id"] in strong
        indent = depth[span["id"]] * INDENT
        body += text(indent, top + 15, clip(names[span["id"]], left - indent - 10), bold=bold)
        x, end = place(span["start"]), place(_end(span))
        body += rect(x, top + 5, max(end - x, 1), BAR, fill="mark" if bold else mix("mark", 35))
        body += text(max(end, x + 1) + GAP, top + 15, durations[k], tone="dim")
    axis = HEAD + len(spans) * ROW + 2
    body += line(left, axis, right, axis)
    body += text(left, axis + AXIS - 4, "0", tone="dim")
    body += text(right, axis + AXIS - 4, number(finish, unit), tone="dim", anchor="end")
    return svg_frame("waterfall", props["caption"], WIDTH, axis + AXIS, body, children)


register_component("waterfall", chart_schema({
    "spans": entries({"id": SPAN_ID, "label": LABEL, "start": COUNT, "duration": COUNT, "parent": SPAN_ID},
                     ["id", "label", "start", "duration"]),
    "unit": UNIT,
}, ["spans"]), render_waterfall, check=check_waterfall)
