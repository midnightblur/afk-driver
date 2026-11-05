"""Box plots (K-36): several spreads of request times, sizes or durations, where an average hides the tail. One box
per item on a shared scale: whiskers from min to max, the box from the first to the third quartile, a line at the
median, and the median and the spread written at the end. One spread alone reads better as a histogram."""

from components.chart_svg import (LABEL, NUMBER, UNIT, WIDTH, chart_schema, clip, entries, label_width, line, mix,
                                  number, rect, scale, svg_frame, text, text_width, too_many, unfinite)
from registry import register_component

ROW, BOX, GAP, AXIS, MAX_BOXES = 30, 16, 8, 18, 20
ORDER = ["min", "q1", "median", "q3", "max"]


def check_box_plot(props):
    found = too_many(props, "items", MAX_BOXES) + unfinite(props)
    found += [(("items", k), "must run min, q1, median, q3, max, each at most the next")
              for k, item in enumerate(props["items"])
              if any(item[a] > item[b] for a, b in zip(ORDER, ORDER[1:]))]
    return found


def _numbers(item, unit):
    return f"median {number(item['median'], unit)} ({number(item['min'])} to {number(item['max'])})"


def render_box_plot(props, children):
    items, unit = props["items"], props.get("unit")
    left = label_width(item["label"] for item in items)
    room = max(text_width(_numbers(item, unit)) for item in items) + 2 * GAP
    low, high = min(item["min"] for item in items), max(item["max"] for item in items)
    place = scale(low, high, left, WIDTH - room)
    body = ""
    for k, item in enumerate(items):
        top, middle = k * ROW, k * ROW + ROW / 2
        x = {field: place(item[field]) for field in ORDER}
        body += text(0, middle + 4, clip(item["label"], left - 10))
        body += line(x["min"], middle, x["max"], middle, tone="neutral")
        body += line(x["min"], middle - 5, x["min"], middle + 5, tone="neutral")
        body += line(x["max"], middle - 5, x["max"], middle + 5, tone="neutral")
        body += rect(x["q1"], top + (ROW - BOX) / 2, x["q3"] - x["q1"], BOX, fill=mix("mark", 35), stroke="mark")
        body += line(x["median"], top + (ROW - BOX) / 2, x["median"], top + (ROW + BOX) / 2, tone="ink", width=2)
        body += text(WIDTH - room + GAP, middle + 4, _numbers(item, unit), tone="dim")
    axis = len(items) * ROW
    body += line(left, axis, WIDTH - room, axis)
    body += text(left, axis + AXIS - 4, number(low), tone="dim")
    body += text(WIDTH - room, axis + AXIS - 4, number(high), tone="dim", anchor="end")
    return svg_frame("box-plot", props["caption"], WIDTH, axis + AXIS, body, children)


FIELDS = {"label": LABEL, **{field: NUMBER for field in ORDER}}
register_component("box-plot", chart_schema({"items": entries(FIELDS, list(FIELDS)), "unit": UNIT}, ["items"]),
                   render_box_plot, check=check_box_plot)
