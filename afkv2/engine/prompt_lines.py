"""Turn the prompts of one host poll into one raw response in the ingest grammar (`ingest.py`).

A prompt is `{uid, prompt, selector, tag, text}`. The page queues a mark as a prompt with the tag
`afkv2-mark` and a side question with the tag `afkv2-btw`; every other prompt is a native lavish
annotation or message. An annotation names its
element by the nearest ancestor HTML id in `selector`, and every page element id is an HTML id.
"""

from __future__ import annotations

import re

from ingest import NO_CHOICE, NOTE_SEPARATOR

MARK_TAG = "afkv2-mark"
BTW_TAG = "afkv2-btw"
CONTEXT_DATA = "\n\nContext data:\n"
OLD_FORM = "[round R-"
SELECTION_TAG = "text"
NO_EXCERPT_TAGS = {"whiteboard"}
EXCERPT_LIMIT = 120
ID_SEGMENT = re.compile(r"#((?:\\[0-9A-Fa-f]{1,6} ?|\\.|[^\s\\>#.:\[\]~+()])+)")
CSS_ESCAPE = re.compile(r"\\([0-9A-Fa-f]{1,6}) ?|\\(.)", re.S)


def css_unescape(text: str) -> str:
    return CSS_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)) if m.group(1) else m.group(2), text)


def selector_target(selector: str, ids: dict, aliases: dict | None = None) -> str | None:
    """The first `#id` segment of a selector that is an element id of the document, or an HTML id that
    `aliases` maps to an element id."""
    aliases = aliases or {}
    for match in ID_SEGMENT.finditer(selector or ""):
        identifier = css_unescape(match.group(1))
        if identifier in ids:
            return identifier
        if aliases.get(identifier) in ids:
            return aliases[identifier]
    return None


def _excerpt(text: str) -> str:
    words = " ".join(text.split())
    return words if len(words) <= EXCERPT_LIMIT else words[:EXCERPT_LIMIT - 1] + "…"


def fallback_target(doc: dict, ids: dict) -> str | None:
    """Where a prompt with no element goes: the first map, as a steer, else the first card of the round."""
    for chart in doc.get("maps") or []:
        if chart.get("id") in ids:
            return chart["id"]
    current = next((r for r in doc["rounds"] if r["state"] == "current"), {"items": []})
    items = [*current["items"], *(item for r in reversed(doc["rounds"]) for item in r["items"])]
    return items[0]["id"] if items else next(iter(ids), None)


def split_side_questions(prompts: list[dict]) -> tuple[list[dict], list[str]]:
    """(the round's prompts, the side questions). A side question is a prompt tagged `afkv2-btw`: it never
    enters the round's raw response. The bridge appends `options.data` to the text; that tail is cut."""
    round_prompts, questions = [], []
    for prompt in prompts:
        if str(prompt.get("tag") or "") != BTW_TAG:
            round_prompts.append(prompt)
            continue
        question = str(prompt.get("prompt") or "").replace("\r\n", "\n").split(CONTEXT_DATA, 1)[0].strip()
        if question:
            questions.append(question)
    return round_prompts, questions


def raw_from_prompts(doc: dict, prompts: list[dict], ids: dict, aliases: dict | None = None) -> str:
    """First line `[round R-n]` of the current round; then one line per element, in first-seen order.

    `aliases` maps an HTML id that is no element id, such as a row of the notes table, to its element.

    A mark and the notes on one element merge into one line; several notes join with a blank line.
    A selection, and an annotation on no known element, keeps an excerpt of the text it was on. No
    prompt with words is dropped: a prompt with no known element lands on `fallback_target`.
    """
    n = next(r for r in doc["rounds"] if r["state"] == "current")["n"]
    order: list[tuple[str, str]] = []
    marks: dict[str, str] = {}
    notes: dict[str, list[str]] = {}

    def entry(target: str) -> None:
        if target not in notes:
            order.append(("id", target))
            notes[target] = []

    for prompt in prompts:
        text = str(prompt.get("prompt") or "").replace("\r\n", "\n")
        tag = str(prompt.get("tag") or "")
        if tag == BTW_TAG:
            continue
        if text.startswith(OLD_FORM):
            order.extend(("line", line) for line in text.split("\n")[1:])
            continue
        if tag == MARK_TAG:
            line = text.split("\n", 1)[0].strip()
            target, _, token = line.rpartition(" ")
            if target and token:
                entry(target)
                marks[target] = token
            else:
                order.append(("line", line))
            continue
        selector = str(prompt.get("selector") or "")
        seen = str(prompt.get("text") or "")
        target = selector_target(selector, ids, aliases)
        note = text.strip()
        if seen.strip() and (tag == SELECTION_TAG or (target is None and selector and tag not in NO_EXCERPT_TAGS)):
            note = f'{note} (on: "{_excerpt(seen)}")'.strip()
        if not note:
            continue
        target = target or fallback_target(doc, ids)
        if target is None:
            order.append(("line", note))
            continue
        entry(target)
        notes[target].append(note)

    lines = [f"[round R-{n}]"]
    for kind, value in order:
        if kind == "line":
            lines.append(value)
            continue
        line = f"{value} {marks.get(value, NO_CHOICE)}"
        if notes[value]:
            line += NOTE_SEPARATOR + "\n\n".join(notes[value])
        lines.append(line)
    return "\n".join(lines)
