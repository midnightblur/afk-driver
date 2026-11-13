"""Card (CMP-4): one point the human reads or answers, with the controls of its kind.

The page passes the card's notes and replies (`exchange`) and its earlier cards (`history`) as HTML.
`rail` sets the state that the page rail reads: `settled` folds the card to its heading and settled line.
`label`, given on a version 2 page, is the visible name of the card. Its presence switches the heading: with a
label, the heading shows the label, no raw card id, and its round as "Round 3"; without one, the heading shows the
card's title, if any, its id, and its round as "R-3". The id stays in the attributes either way. A label is never empty.
`age`, given by the page, is the count of rounds since the card's round: its chip fades with age (`fade`).
The card body comes first and starts with the heading, then the settled line, the notes and replies and the
content (PRD AC-046): a note on the card body shows what it noted. The mark radios and the history follow it.
`changed`, given by the page, shows the changed-this-round mark right after the title (PRD AC-047).
"""

import re
from html import escape

from registry import register_component, walk
from shell.parts_v2 import CHANGED_MARK
from shell.rounds import round_chip

KIND_WORDS = {"decided": "Decided", "confirm": "Confirm", "debate": "Debate", "signoff": "Sign-off",
              "info": "For your information"}
STATE_WORDS = {"open": "open", "blocked": "blocked", "needs_reading": "needs reading",
               "settled_by_mark": "settled by mark", "settled_by_note": "settled by note"}
RAIL_STATES = {"blocked": "blocked", "settled_by_mark": "settled", "settled_by_note": "settled"}
WRITE_IN = "write-in"
PAST_CHIP = "afkv2-round-chip--past"
WORDS_HINT = "Type your answer. A write-in with no words is not sent."
FADE_STEP, FADE_FLOOR = 0.2, 0.4
FIXED_CONTROLS = {
    "decided": [("accept", "Accept"), ("reopen", "Reopen")],
    "confirm": [("accept", "Accept"), (WRITE_IN, "Correct it: type your correction")],
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
    return [*options, (WRITE_IN, "Something else: type your answer")]


def _words(item_id):
    """The write-in box: shown while the write-in radio is picked. The page sends a write-in only with its words."""
    return (f'<label class="afkv2-writein"><span>Your words</span><textarea name="words:{escape(item_id)}" '
            f'data-afkv2-input="{WRITE_IN}" rows="3" placeholder="{WORDS_HINT}"></textarea></label>')


def _choice(item_id, options):
    """`data-lavish-question` makes lavish keep the picked radio and the typed write-in words in its tab store and
    set them again after a reload, beside the queued mark, which lavish keeps in the same store."""
    rows = "".join(
        f'<label class="afkv2-opt"><input type="radio" name="choice:{escape(item_id)}" value="{escape(token)}">'
        f"<span>{escape(label)}</span></label>" for token, label in options)
    words = _words(item_id) if any(token == WRITE_IN for token, _ in options) else ""
    return (f'<fieldset class="afkv2-choice" data-afkv2-input="choice" data-lavish-question="{escape(item_id)}">'
            f'<legend>Your mark</legend>{rows}{words}</fieldset>')


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
    """The CSS declaration of a round chip `age` rounds old (PRD AC-048): the current round is fully strong, each
    older round fades by FADE_STEP down to FADE_FLOOR, so an old chip stays readable."""
    if not age:
        return ""
    return f"opacity: {max(FADE_FLOOR, 1 - FADE_STEP * age):.1f}"


def _chip(props, needs_human):
    """The round chip of the card's round, in its round's colour: bold when the card needs the human now, regular
    otherwise; it fades with the age of its round."""
    n = props["round"]
    words = f"Round {n}" if "label" in props else f"R-{n}"
    return round_chip(n, words, "" if needs_human else PAST_CHIP, fade(props.get("age", 0)),
                      f' title="Round {n}"', props["colour"]) + " "


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
    mark = CHANGED_MARK if props.get("changed") else ""
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
            f'style="--afkv2-round: {escape(props["colour"])}"><div class="afkv2-card-body">{heading}{_settled_line(item)}'
            f'{props.get("exchange", "")}<div class="afkv2-body">{"".join(children)}</div></div>{answer}'
            f'{props.get("history", "")}</article>')


register_component("card", {
    "type": "object", "additionalProperties": False, "required": ["item", "round", "colour", "current"],
    "properties": {"item": {"type": "object", "required": ["id", "kind", "body"]},
                   "round": {"type": "integer", "minimum": 1}, "colour": {"type": "string"},
                   "current": {"type": "boolean"}, "exchange": {"type": "string"}, "history": {"type": "string"},
                   "rail": {"enum": ["open", "blocked", "settled"]}, "changed": {"type": "boolean"},
                   "age": {"type": "integer", "minimum": 0},
                   "label": {"description": "Present: the version 2 heading (module docstring).", "type": "string",
                             "minLength": 1}},
}, render_card)
