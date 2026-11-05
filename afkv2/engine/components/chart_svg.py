"""What every chart component shares (ADR-0005 design): the SVG frame with its 1-line caption (PR-13), the theme
tokens, the number words and the props rules a schema cannot state. Registers no type.

A chart draws inline SVG from its props. It paints only theme tokens, so it follows the light and the dark theme,
and it writes each number it shows as text, so no meaning rests on colour alone (PR-07). The page gets no script.
"""

from __future__ import annotations

import math
from html import escape
from typing import Iterable

CAPTION = {"type": "string", "minLength": 1, "maxLength": 160}
LABEL = {"type": "string", "minLength": 1, "maxLength": 60}
UNIT = {"type": "string", "minLength": 1, "maxLength": 12}
NUMBER = {"type": "number"}
COUNT = {"type": "number", "minimum": 0}
MAX_ENTRIES = 40

# The theme tokens of kit.css that a chart paints with; both themes define each one.
TOKENS = {"ink": "var(--fg)", "dim": "var(--fg-dim)", "rule": "var(--line)", "mark": "var(--accent)",
          "warn": "var(--open)", "neutral": "var(--neutral)", "ground": "var(--surface)", "back": "var(--bg)"}
SET_TOKEN = "var(--afkv2-set-{})"
SET_SIZE = 8

FRAME_CLASS = "afkv2-chart afkv2-chart--{}"
FIGURE_STYLE = "margin:0 0 .5rem;max-width:{}px"
SVG_STYLE = "display:block;width:100%;height:auto;font:{}px ui-sans-serif,system-ui,sans-serif"
CAPTION_STYLE = "margin:.2rem 0 0;color:var(--fg-dim);font-size:.85rem"
NOTE_LINE = '<p style="margin:.25rem 0 0;font-size:.85rem;color:var(--fg-dim)">{}</p>'
FONT = 12
CHAR = 0.6
WIDTH = 560
MINUS = "−"


def chart_schema(properties: dict, required: Iterable[str], defs: dict | None = None) -> dict:
    """The props schema of a chart: its own fields and the caption every chart needs."""
    schema = {"type": "object", "additionalProperties": False, "required": ["caption", *required],
              "properties": {"caption": CAPTION, **properties}}
    if defs:
        schema["$defs"] = defs
    return schema


def entries(fields: dict, required: Iterable[str]) -> dict:
    """The schema of a non-empty list of objects with these fields."""
    return {"type": "array", "minItems": 1,
            "items": {"type": "object", "additionalProperties": False, "required": list(required), "properties": fields}}


def too_many(props: dict, field: str, cap: int = MAX_ENTRIES) -> list[tuple]:
    count = len(props.get(field) or [])
    return [((field,), f"holds {count} entries; a chart takes {cap} at most")] if count > cap else []


def unfinite(value, path: tuple = ()) -> list[tuple]:
    """A JSON reader takes NaN and Infinity as numbers; a chart cannot place them."""
    if isinstance(value, float) and not math.isfinite(value):
        return [(path, "must be a finite number")]
    if isinstance(value, dict):
        return [hit for key, sub in value.items() for hit in unfinite(sub, (*path, key))]
    if isinstance(value, list):
        return [hit for k, sub in enumerate(value) for hit in unfinite(sub, (*path, k))]
    return []


def number(value, unit: str | None = None) -> str:
    """The words of a number: thousands grouped, at most 2 decimals, a true minus sign, then the unit."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    words = f"{value:,}" if isinstance(value, int) else f"{value:,.2f}".rstrip("0").rstrip(".")
    words = words.replace("-", MINUS)
    if not unit:
        return words
    return f"{words}{unit}" if unit == "%" else f"{words} {unit}"


def signed(value, unit: str | None = None) -> str:
    """A number with its sign always written: +12 ms, −8 ms, 0 ms."""
    return ("+" if value > 0 else "") + number(value, unit)


def text_width(words: str, size: float = FONT) -> float:
    return len(words) * size * CHAR


def clip(words: str, width: float, size: float = FONT) -> str:
    """The words cut with an ellipsis to fit `width`."""
    room = int(width / (size * CHAR) + 1e-6)
    if len(words) <= room:
        return words
    return words[:max(room - 1, 0)] + "…" if room > 1 else ""


def scale(low: float, high: float, start: float, end: float):
    """A function that maps a value of [low, high] to a position of [start, end]."""
    span = (high - low) or 1
    return lambda value: start + (value - low) * (end - start) / span


def label_width(labels: Iterable[str], cap: float = 200) -> float:
    return min(max((text_width(label) for label in labels), default=0) + 10, cap)


def paint(tone: str) -> str:
    return TOKENS.get(tone, tone)


def set_colour(k: int) -> str:
    return SET_TOKEN.format(k % SET_SIZE + 1)


def text(x: float, y: float, words: str, *, tone: str = "ink", anchor: str = "start", size: float = FONT,
         bold: bool = False) -> str:
    weight = ";font-weight:700" if bold else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
            f'style="fill:{paint(tone)};font-size:{size}px{weight}">{escape(words)}</text>')


def rect(x: float, y: float, width: float, height: float, *, fill: str, stroke: str | None = None,
         title: str | None = None) -> str:
    edge = f";stroke:{paint(stroke)}" if stroke else ""
    hover = f"<title>{escape(title)}</title>" if title else ""
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(width, 0):.1f}" height="{height:.1f}" '
            f'style="fill:{paint(fill)}{edge}">{hover}</rect>')


def line(x1: float, y1: float, x2: float, y2: float, *, tone: str = "rule", width: float = 1,
         dash: bool = False) -> str:
    dashes = ";stroke-dasharray:4 3" if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'style="stroke:{paint(tone)};stroke-width:{width}{dashes}"/>')


def dot(x: float, y: float, r: float, tone: str = "ink") -> str:
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" style="fill:{paint(tone)}"/>'


def polyline(points: list[tuple[float, float]], tone: str = "mark", width: float = 2) -> str:
    joined = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return (f'<polyline points="{joined}" '
            f'style="fill:none;stroke:{paint(tone)};stroke-width:{width};stroke-linejoin:round"/>')


def mix(tone: str, strength: int) -> str:
    """A token at `strength` percent over the card surface: one hue, weaker or stronger."""
    return f"color-mix(in srgb, {paint(tone)} {strength}%, var(--surface))"


def note_line(html: str) -> str:
    """An HTML line under the SVG for words that may wrap, such as a source or what a range means."""
    return NOTE_LINE.format(html)


def svg_frame(kind: str, caption: str, width: float, height: float, body: str, children: Iterable[str] = (),
              after: str = "") -> str:
    """The figure of one chart: the inline SVG, any HTML line `after` it, then the 1-line caption; the
    children follow the figure."""
    label = escape(caption)
    return (f'<figure class="{FRAME_CLASS.format(kind)}" style="{FIGURE_STYLE.format(round(width))}">'
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" role="img" '
            f'aria-label="{label}" style="{SVG_STYLE.format(FONT)}">{body}</svg>{after}'
            f'<figcaption style="{CAPTION_STYLE}">{label}</figcaption></figure>' + "".join(children))
