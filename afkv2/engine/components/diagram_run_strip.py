"""Simulated-run strip (CMP-8): the steps of a run in time order, current and proposed."""

from html import escape

from registry import register_component
from shell.diagram_parts import LABEL, TITLE, figure, held_in, label_html

LANES = (("current", "Current"), ("proposed", "Proposed"))
STEPS = {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["label"],
    "properties": {"label": LABEL, "detail": {"type": "string"},
                   "tone": {"enum": ["kept", "removed", "new", "proposed"]}}}}


def nested_labels(props):
    return [held for key, _ in LANES for held in held_in(props.get(key) or [], key)]


def check_lanes(props):
    if not any(props.get(key) for key, _ in LANES):
        yield ("current",), "give at least one step in current or proposed"


def _step(step):
    tone = step.get("tone")
    css = f"afkv2-run-step afkv2-tone--{tone}" if tone else "afkv2-run-step"
    detail = f'<span class="afkv2-run-detail">{escape(step["detail"])}</span>' if step.get("detail") else ""
    word = f'<span class="afkv2-run-tone">{tone}</span>' if tone else ""
    return f'<li class="{css}">{label_html(step["label"], "afkv2-run-label")}{detail}{word}</li>'


def _lane(heading, steps):
    drawn = "".join(map(_step, steps))
    return (f'<div class="afkv2-run-lane"><h5 class="afkv2-run-head">{heading}</h5>'
            f'<ol class="afkv2-run-steps">{drawn}</ol></div>')


def render_run_strip(props, children):
    lanes = "".join(_lane(heading, props[key]) for key, heading in LANES if props.get(key))
    return figure(props, lanes, children)


register_component("run-strip", {
    "type": "object", "additionalProperties": False,
    "properties": {"title": TITLE, "current": STEPS, "proposed": STEPS},
}, render_run_strip, nested=nested_labels, check=check_lanes)
