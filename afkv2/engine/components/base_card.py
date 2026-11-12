"""Card (CMP-4): one point the human reads or answers, with the controls of its kind.

The page passes the card's notes and replies (`exchange`) and its earlier cards (`history`) as HTML.
`rail` sets the state that the page rail reads: `settled` folds the card to its heading and settled line.
`label`, given on a version 2 page, is the visible name of the card. Its presence switches the heading: with a
label, the heading shows the label, no raw card id, and its round as "Round 3"; without one, the heading shows the
card's title, if any, its id, and its round as "R-3". The id stays in the attributes either way. A label is never empty.
`age`, given by the page, is the count of rounds since the card's round: its chip fades with age (`fade`).
`mark`, given by the page, is HTML that shows right after the title: the changed-this-round mark (PRD AC-047).
"""

import re
from html import escape

from registry import register_component, walk

KIND_WORDS = {"decided": "Decided", "confirm": "Confirm", "debate": "Debate", "signoff": "Sign-off",
              "info": "For your information"}
STATE_WORDS = {"open": "open", "blocked": "blocked", "needs_reading": "needs reading",
               "settled_by_mark": "settled by mark", "settled_by_note": "settled by note"}
RAIL_STATES = {"blocked": "blocked", "settled_by_mark": "settled", "settled_by_note": "settled"}
WRITE_IN = "write-in"
FADE_STEP, FADE_FLOOR = 0.2, 0.4
FIXED_CONTROLS = {
    "decided": [("accept", "Accept"), ("reopen", "Reopen")],
    "confirm": [("accept", "Accept"), (WRITE_IN, "Correct it: annotate the card")],
    "signoff": [("sign", "Sign"), ("changes", "Ask for changes")],
}


def _column_titles(body):
    titles = {}
    for _, component in walk(body):
        if component["type"] == "table":
            props = component["props"]
            for row in props["rows"]:
                for column, cell in zip(props["columns"], row):
                    if isinstance(cell, dict) and cell.get("id"):
                        titles[cell["id"]] = column
    return titles


def debate_options(item):
    """Tokens and labels of a debate card: a component with id `<item id>-opt-<letter>` is an option."""
    pattern = re.compile(re.escape(item["id"]) + "-opt-([a-z])")
    titles = _column_titles(item["body"])
    options = []
    for _, component in walk(item["body"]):
        match = pattern.fullmatch(component.get("id") or "")
        if match:
            options.append((match.group(1), titles.get(component["id"], f"Option {match.group(1).upper()}")))
    return [*options, (WRITE_IN, "Something else: annotate the card")]


def _choice(item_id, options):
    """`data-lavish-question` makes lavish keep the picked radio in its tab store and set it again after a
    reload, beside the queued mark, which lavish keeps in the same store."""
    rows = "".join(
        f'<label class="afkv2-opt"><input type="radio" name="choice:{escape(item_id)}" value="{escape(token)}">'
        f"<span>{escape(label)}</span></label>" for token, label in options)
    return (f'<fieldset class="afkv2-choice" data-afkv2-input="choice" data-lavish-question="{escape(item_id)}">'
            f'<legend>Your mark</legend>{rows}</fieldset>')


def _answer(item, state):
    """The mark radios of an open asking card. A note is a native lavish annotation, so no card holds a note field."""
    if state != "open" or item["kind"] == "info":
        return ""
    options = debate_options(item) if item["kind"] == "debate" else FIXED_CONTROLS[item["kind"]]
    return f'<div class="afkv2-answer">{_choice(item["id"], options)}</div>'


def _settled_line(item):
    settled = item.get("settled")
    if not settled:
        return ""
    reading = f': {escape(settled["reading"])}' if settled.get("reading") else ""
    return (f'<p class="afkv2-settled afkv2-settled--{settled["by"]}">Settled by {settled["by"]} '
            f'in round {settled["round"]} ({escape(settled["signal"])}){reading}</p>')


def fade(age):
    """The inline style of a round chip `age` rounds old (PRD AC-048): the current round is fully strong, each older
    round fades by FADE_STEP down to FADE_FLOOR, so an old chip stays readable."""
    if not age:
        return ""
    return f' style="opacity: {max(FADE_FLOOR, 1 - FADE_STEP * age):.1f}"'


def _chip(props, needs_human):
    """The round chip of the card's round: solid when the card needs the human now, muted otherwise; it fades with
    the age of its round."""
    muted = "" if needs_human else " afkv2-round-chip--past"
    words = f'Round {props["round"]}' if "label" in props else f'R-{props["round"]}'
    return (f'<span class="afkv2-round-chip{muted}"{fade(props.get("age", 0))} title="Round {props["round"]}">'
            f'{words}</span> ')


def render_card(props, children):
    item, current = props["item"], props["current"]
    state = item.get("state", "open")
    settled = state.startswith("settled_")
    chip = _chip(props, current and item["kind"] != "info" and state in ("open", "blocked"))
    required = ' data-afkv2-required="1"' if current and state == "open" and item["kind"] != "info" else ""
    answer = _answer(item, state) if current and not settled else ""
    item_id = escape(item["id"])
    quiet = item["kind"] == "info" and state == "open"
    state_word = "" if quiet else f'<span class="afkv2-state afkv2-state--{state}">{STATE_WORDS[state]}</span>'
    mark = props.get("mark", "")
    if "label" in props:
        heading = (f'<h4 class="afkv2-h">{chip}<span class="afkv2-card-title">{escape(props["label"])}</span>{mark} '
                   f'<span class="afkv2-kind">{KIND_WORDS[item["kind"]]}</span> {state_word}</h4>')
    elif item.get("title"):
        heading = (f'<h4 class="afkv2-h">{chip}<span class="afkv2-card-title">{escape(item["title"])}</span>{mark} '
                   f'<span class="afkv2-kind">{KIND_WORDS[item["kind"]]}</span> {state_word} '
                   f'<span class="afkv2-card-id">{item_id}</span></h4>')
    else:
        heading = f'<h4 class="afkv2-h">{chip}{KIND_WORDS[item["kind"]]}: {item_id}{mark} {state_word}</h4>'
    rail = props.get("rail") or RAIL_STATES.get(state, "open")
    return (f'<article class="afkv2-card afkv2-card--{item["kind"]}" id="{item_id}" '
            f'data-afkv2-item="{item_id}" data-afkv2-element="{item_id}" '
            f'data-afkv2-state="{rail}" data-afkv2-point="{state}"{required} '
            f'style="--afkv2-round: {escape(props["colour"])}">{heading}{_settled_line(item)}'
            f'{props.get("exchange", "")}<div class="afkv2-body">{"".join(children)}</div>{answer}'
            f'{props.get("history", "")}</article>')


register_component("card", {
    "type": "object", "additionalProperties": False, "required": ["item", "round", "colour", "current"],
    "properties": {"item": {"type": "object", "required": ["id", "kind", "body"]},
                   "round": {"type": "integer", "minimum": 1}, "colour": {"type": "string"},
                   "current": {"type": "boolean"}, "exchange": {"type": "string"}, "history": {"type": "string"},
                   "rail": {"enum": ["open", "blocked", "settled"]}, "mark": {"type": "string"},
                   "age": {"type": "integer", "minimum": 0},
                   "label": {"description": "Present: the version 2 heading (module docstring).", "type": "string",
                             "minLength": 1}},
}, render_card)
