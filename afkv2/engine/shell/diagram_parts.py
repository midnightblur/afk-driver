"""What every diagram shares: a label that is text or a component, the figure, and the id rules."""

from __future__ import annotations

from html import escape
from typing import Iterable

from registry import render_component

TEXT = {"type": "string", "minLength": 1}
LABEL = {"anyOf": [TEXT, {"type": "object", "required": ["type"]}]}
TITLE = {"type": "string"}


def label_html(label, css: str) -> str:
    inner = escape(label) if isinstance(label, str) else render_component(label)
    return f'<span class="{css}">{inner}</span>'


def held_in(entries: list[dict], field: str, key: str = "label") -> list[tuple]:
    """`(path below props, component)` for each label of `entries` that holds a component."""
    return [((field, i, key), entry[key]) for i, entry in enumerate(entries) if isinstance(entry[key], dict)]


def figure(props: dict, inner: str, children: list[str]) -> str:
    title = props.get("title")
    caption = f'<figcaption class="afkv2-diagram-title">{escape(title)}</figcaption>' if title else ""
    return f'<figure class="afkv2-diagram">{caption}{inner}</figure>' + "".join(children)


def repeated_ids(entries: list[dict], field: str) -> Iterable[tuple]:
    seen = set()
    for i, entry in enumerate(entries):
        if entry["id"] in seen:
            yield (field, i, "id"), f"id {entry['id']!r} is used twice in this {field[:-1]} list"
        seen.add(entry["id"])


def unknown_ends(entries: list[dict], field: str, known: set[str], noun: str) -> Iterable[tuple]:
    for i, entry in enumerate(entries):
        for end in ("from", "to"):
            if entry[end] not in known:
                yield (field, i, end), f"{entry[end]!r} names no {noun} of this diagram"
