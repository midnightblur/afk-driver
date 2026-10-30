"""Sequence diagram (CMP-7): actors and ordered messages, drawn on a grid with one column per actor."""

from registry import register_component
from shell.diagram_parts import LABEL, TEXT, TITLE, figure, held_in, label_html, repeated_ids, unknown_ends


def nested_labels(props):
    return held_in(props["actors"], "actors") + held_in(props["messages"], "messages", "text")


def check_sequence(props):
    yield from repeated_ids(props["actors"], "actors")
    yield from unknown_ends(props["messages"], "messages", {actor["id"] for actor in props["actors"]}, "actor")


def _message(n, message, columns):
    start, end = columns[message["from"]], columns[message["to"]]
    low, high = sorted((start, end))
    span = high - low + 1
    way = "self" if start == end else "right" if start < end else "left"
    margin = "" if start == end else f";margin-inline:calc(100% / {2 * span})"
    return (f'<div class="afkv2-seq-msg afkv2-seq-msg--{way}" style="grid-column:{low} / {high + 1};grid-row:{n + 1}{margin}">'
            f'<div class="afkv2-seq-text"><span class="afkv2-seq-n">{n}.</span> '
            f'{label_html(message["text"], "afkv2-seq-words")}</div><div class="afkv2-seq-line"></div></div>')


def _actor(column, actor):
    return (f'<div class="afkv2-seq-actor" style="grid-column:{column};grid-row:1">'
            f'{label_html(actor["label"], "afkv2-seq-words")}</div>')


def render_sequence(props, children):
    actors, messages = props["actors"], props["messages"]
    columns = {actor["id"]: i for i, actor in enumerate(actors, 1)}
    heads = "".join(_actor(i, actor) for i, actor in enumerate(actors, 1))
    lives = "".join(f'<div class="afkv2-seq-life" style="grid-column:{i};grid-row:2 / {len(messages) + 2}"></div>'
                    for i in range(1, len(actors) + 1))
    drawn = "".join(_message(n, message, columns) for n, message in enumerate(messages, 1))
    grid = (f'<div class="afkv2-diagram-scroll"><div class="afkv2-seq" '
            f'style="grid-template-columns:repeat({len(actors)}, minmax(9rem, 1fr))">{heads}{lives}{drawn}</div></div>')
    return figure(props, grid, children)


register_component("sequence", {
    "type": "object", "additionalProperties": False, "required": ["actors", "messages"],
    "properties": {
        "title": TITLE,
        "actors": {"type": "array", "minItems": 1, "items": {
            "type": "object", "additionalProperties": False, "required": ["id", "label"],
            "properties": {"id": TEXT, "label": LABEL}}},
        "messages": {"type": "array", "minItems": 1, "items": {
            "type": "object", "additionalProperties": False, "required": ["from", "to", "text"],
            "properties": {"from": TEXT, "to": TEXT, "text": LABEL}}},
    },
}, render_sequence, nested=nested_labels, check=check_sequence)
