"""Turn the prompts of one host poll into one raw response, in the grammar of the page's format. This module
is the one home of both grammars; ingest (`ingest.py`) is their one parser.

Format 0: first line `[round R-n]`, then `<id> <token>` or `<id> <token> | <note>`, an em dash for no
choice; the mark of an element shares the line of its first note; a selection keeps `(on: "<excerpt>")`
inside the note.

Format 1 (SDD §3): first line `[round R-n]`. A mark is `<element id> <mark>`. Each note is its own entry:
a line `<element id> note <k>`, k = 1, 2, 3 per element in the send, then an optional line
`  on: "<noted text>"`, then the note's words on the following lines, each indented 2 spaces. An edit is
`<note id> edit` with the new words indented the same way; a delete is `<note id> delete`.

A prompt is `{uid, prompt, selector, tag, text}`. The page queues a mark as a prompt with the tag
`afkv2-mark`. A prompt with the tag `afkv2-btw` is a side question: the btw? panel posts its questions
to the side-question listener (`btw_listener.py`), and only a page rendered before that queues one.
Every other prompt is a native lavish annotation or message. An annotation names its
element by the nearest ancestor HTML id in `selector`, and every page element id is an HTML id.
"""

from __future__ import annotations

import re

from schema.note_rules import round_target

FORMAT_0 = "afkv2.page/0"
NO_CHOICE = "—"
NOTE_SEPARATOR = " | "
NOTE_WORD = "note"
QUOTE_LINE = '  on: "'
INDENT = "  "
QUOTE_LIMIT = 300
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


def _excerpt(text: str, limit: int = EXCERPT_LIMIT) -> str:
    words = " ".join(text.split())
    return words if len(words) <= limit else words[:limit - 1] + "…"


def fallback_target(doc: dict, ids: dict) -> str | None:
    """Where a prompt with no element goes, as a steer: the first map, else the banner of the current round."""
    for chart in doc.get("maps") or []:
        if chart.get("id") in ids:
            return chart["id"]
    current = next((r for r in doc["rounds"] if r["state"] == "current"), None)
    target = current and round_target(current["n"])
    return target if target in ids else next(iter(ids), None)


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


def raw_from_prompts(doc: dict, prompts: list[dict], ids: dict, aliases: dict | None = None,
                     page_format: str | None = None) -> str:
    """First line `[round R-n]` of the current round; then the lines of each element, in first-seen order.

    `aliases` maps an HTML id that is no element id, such as a row of the notes table, to its element.
    `page_format` is the schema value of the page file, by default the document's own: a format 0 page
    keeps its format 0 grammar.

    Each annotation is one note. A selection, and an annotation on no known element, keeps the text it was
    on: format 0 as an excerpt inside the note, format 1 in the note's `on:` line. No prompt with words is
    dropped: a prompt with no known element lands on `fallback_target`.
    """
    old_grammar = (page_format or doc.get("schema")) == FORMAT_0
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
        quote = None
        if seen.strip() and (tag == SELECTION_TAG or (target is None and selector and tag not in NO_EXCERPT_TAGS)):
            quote = _excerpt(seen, EXCERPT_LIMIT if old_grammar else QUOTE_LIMIT)
        if old_grammar and quote:
            note, quote = f'{note} (on: "{quote}")'.strip(), None
        if not note and not quote:
            continue
        target = target or fallback_target(doc, ids)
        if target is None:
            order.append(("line", note))
            continue
        entry(target)
        notes[target].append((note, quote))

    lines = [f"[round R-{n}]"]
    for kind, value in order:
        if kind == "line":
            lines.append(value)
        elif old_grammar:
            first, *more = [note for note, _ in notes[value]] or [None]
            lines.append(f"{value} {marks.get(value, NO_CHOICE)}" + (NOTE_SEPARATOR + first if first else ""))
            lines += [f"{value} {NO_CHOICE}{NOTE_SEPARATOR}{note}" for note in more]
        else:
            lines += [f"{value} {marks[value]}"] if value in marks else []
            lines += note_entry(value, notes[value])
    return "\n".join(lines)


def note_entry(target: str, notes: list[tuple[str, str | None]]) -> list[str]:
    """The format 1 lines of the notes on one element: `(words, noted text or None)` each, in send order."""
    lines = []
    for k, (words, quote) in enumerate(notes, start=1):
        lines.append(f"{target} {NOTE_WORD} {k}")
        if quote:
            lines.append(f'{QUOTE_LINE}{quote}"')
        lines += [INDENT + line for line in words.split("\n")] if words else []
    return lines
