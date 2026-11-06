"""The page parts of a version 2 page (SDD §8 row "engine: page parts"): the sections, the questions for others,
the worked examples and their change lists. The page shell calls them; versions 0 and 1 never reach this file.

Every visible text of an element comes from `visible_label` (ADR-0003 design): a title or words, never a raw id,
and a round reads "round 3". An id stays in attributes only: the HTML id, `data-afkv2-element` and link targets.
A link carries its meaning as hover text (`data-afkv2-tip`). A change list shows open, newest first.
"""

from __future__ import annotations

import json
from html import escape

from registry import render_component
from shell.points import ASKING, SETTLED, lineages

STATES = {"not_reached": "not reached yet", "current": "current", "merged": "merged", "removed": "removed",
          "open": "open", "answered": "answered", "dropped": "dropped", "assumed": "assumed"}
CAUSES = {"note": "a note", "answer": "your answer", "answer_from": "an answer from",
          "finding": "a finding of the agent"}
KINDS = {"frequent": "frequent", "edge": "edge", "risky": "risky"}
ENTRY_LISTS = ("sections", "stories", "examples", "questions")
UNKNOWN = "another part of the page"
UNTITLED = "a question of {}"
TIPS = {"sections": "Opens this section", "examples": "Opens this worked example",
        "questions": "Opens this question for others", "stories": "A story of this topic",
        "cards": "Opens this card of {}", "options": "A choice of a question for others"}
MERGE_LIMIT = 64
EVERYONE = "everyone"


def _elements(doc: dict) -> dict:
    """Each element id with (its list, the element, the round of a card)."""
    found = {}
    for kind in ENTRY_LISTS:
        for entry in doc.get(kind) or []:
            found[entry["id"]] = (kind, entry, None)
    for question in doc.get("questions") or []:
        for option in (question.get("choices") or {}).get("options") or []:
            found.setdefault(option["id"], ("options", option, None))
    for round_ in doc["rounds"]:
        for item in round_["items"]:
            found[item["id"]] = ("cards", item, round_["n"])
    return found


def _element_label(doc: dict, element: str) -> str:
    kind, entry, n = _elements(doc).get(element, (None, None, None))
    if kind in ("sections", "examples"):
        return entry["title"]
    if kind == "questions":
        return entry["question"]
    if kind in ("stories", "options"):
        return entry["text"]
    if kind == "cards":
        return entry.get("title") or UNTITLED.format(visible_label(doc, "round", n))
    return UNKNOWN


def visible_label(doc: dict, kind: str, value) -> str:
    """The visible text of one thing on a version 2 page, never an id or a round code. `kind`:
    `round` (a round number: "round 3"), `element` (an element id: its title or words), `state` (a section or
    question state), `cause` (a change-line cause) or `kind` (a worked-example kind)."""
    if kind == "round":
        return f"round {int(value)}"
    if kind == "element":
        return _element_label(doc, value)
    words = {"state": STATES, "cause": CAUSES, "kind": KINDS}.get(kind)
    if words is None:
        raise ValueError(f"no label kind {kind!r}")
    return words[value]


def _tip(doc: dict, element: str) -> str:
    kind, _, n = _elements(doc).get(element, (None, None, None))
    tip = TIPS.get(kind, "Opens this part of the page")
    return tip.format(visible_label(doc, "round", n)) if n else tip


def _link(doc: dict, element: str) -> str:
    return (f'<a class="afkv2-v2-link" href="#{escape(element)}" data-afkv2-tip="{escape(_tip(doc, element))}">'
            f'{escape(visible_label(doc, "element", element))}</a>')


def _change_cause(doc: dict, line: dict) -> str:
    words = escape(visible_label(doc, "cause", line["cause"]))
    if line["cause"] == "answer" and line.get("card"):
        return f"{words} to {_link(doc, line['card'])}"
    if line["cause"] == "answer_from" and line.get("question"):
        question = _elements(doc).get(line["question"], (None, {}, None))[1]
        role = (question.get("answer") or {}).get("role") or "someone else"
        return f"{words} {escape(role)} to {_link(doc, line['question'])}"
    return words


def render_changes(doc: dict, changes: list) -> str:
    """The change list of an entry: open, newest first, 1 line per round naming its cause."""
    if not changes:
        return ""
    lines = "".join(
        f'<li class="afkv2-v2-change" data-afkv2-cause="{escape(line["cause"])}">'
        f'<span class="afkv2-v2-change-round">{escape(visible_label(doc, "round", line["round"]))}</span> · '
        f'<span class="afkv2-v2-change-cause">{_change_cause(doc, line)}</span>: {escape(line["text"])}</li>'
        for line in sorted(changes, key=lambda line: -line["round"]))
    return f'<ol class="afkv2-v2-changes">{lines}</ol>'


def _open_counts(doc: dict) -> dict:
    """Each section id with the count of its asking points that are not settled (decision D-11)."""
    counts: dict[str, int] = {}
    for point in lineages(doc):
        head = point.head
        if head.get("section") and head["kind"] in ASKING and head.get("state", "open") not in SETTLED:
            counts[head["section"]] = counts.get(head["section"], 0) + 1
    return counts


def _current_target(sections: dict, element: str) -> str:
    """A link to a merged section goes on to the section it merged into (SDD §4 relation section → section)."""
    for _ in range(MERGE_LIMIT):
        section = sections.get(element)
        if not section or section["state"] != "merged" or not section.get("merged_into"):
            break
        element = section["merged_into"]
    return element


def _chip(count: int) -> str:
    if not count:
        return ""
    words = f"{count} open question{'' if count == 1 else 's'}"
    return f'<span class="afkv2-chip afkv2-v2-open-count">{words}</span>'


def _article(entry: dict, css: str, inner: str, raw: str = "", **attrs) -> str:
    extra = "".join(f' data-afkv2-{name}="{escape(str(value))}"' for name, value in attrs.items())
    return (f'<article id="{escape(entry["id"])}" class="{css}" data-afkv2-element="{escape(entry["id"])}"'
            f'{extra}{raw}>{inner}</article>')


def _section(doc: dict, section: dict, sections: dict, counts: dict) -> str:
    title, state = escape(section["title"]), section["state"]
    if state == "merged":
        line = f"{title}: {STATES['merged']} into {_link(doc, _current_target(sections, section['merged_into']))}."
        return _article(section, "afkv2-v2-section afkv2-v2-gone", f'<p class="afkv2-v2-gone-line">{line}</p>', state=state)
    if state == "removed":
        line = f"{title}: {STATES['removed']}. {escape(section.get('reason') or '')}"
        return _article(section, "afkv2-v2-section afkv2-v2-gone", f'<p class="afkv2-v2-gone-line">{line}</p>', state=state)
    targets = [_current_target(sections, other) for other in section.get("links") or []]
    targets = [other for other in dict.fromkeys(targets) if other != section["id"]]
    links = (f'<div class="afkv2-v2-links">Depends on: {", ".join(_link(doc, other) for other in targets)}</div>'
             if targets else "")
    reached = (f'<span class="afkv2-chip afkv2-v2-state">{escape(STATES[state])}</span>'
               if state == "not_reached" else "")
    head = f'<h3 class="afkv2-v2-h">{title}</h3>{reached}{_chip(counts.get(section["id"], 0))}'
    inner = f'{head}{render_component(section["body"])}{links}{render_changes(doc, section["changes"])}'
    return _article(section, "afkv2-v2-section", inner, state=state)


def render_sections(doc: dict) -> str:
    """The sections block, in page order; a page with no section gets none."""
    entries = doc.get("sections") or []
    if not entries:
        return ""
    sections, counts = {entry["id"]: entry for entry in entries}, _open_counts(doc)
    body = "".join(_section(doc, section, sections, counts) for section in entries)
    return (f'<section class="afkv2-v2-sections" id="afkv2-sections"><h2 class="afkv2-section-h">Sections</h2>'
            f'{body}</section>')


def _roles(question: dict) -> list[str]:
    """The role words of a question in lower case, once each: roles compare without case (SDD §4 who)."""
    return list(dict.fromkeys(role.lower() for role in question["who"]))


def _who_attr(question: dict) -> str:
    """The roles as a JSON list in a single-quoted attribute: a free role word may hold any sign (decision D-12)."""
    data = escape(json.dumps(_roles(question), ensure_ascii=False), quote=False).replace("'", "&#x27;")
    return f" data-afkv2-who='{data}'"


def _markdown(text: str) -> str:
    return render_component({"type": "text", "props": {"text": text, "markdown": True}})


def _part(heading: str, inner: str) -> str:
    return f'<div class="afkv2-v2-part"><p class="afkv2-v2-part-h">{heading}</p>{inner}</div>'


def _ticks(question: dict) -> str:
    """The tick group of an open or assumed question with choices: radios, or checkboxes when several may be
    ticked. Each input value is an option id, for the tick line `<question id> tick <option id> ...`."""
    choices = question.get("choices")
    if not choices or question["state"] not in ("open", "assumed"):
        return ""
    several = choices["several"]
    kind, hint = ("checkbox", "Tick each that applies.") if several else ("radio", "Tick one.")
    name = escape(f"afkv2-tick-{question['id']}")
    inputs = "".join(f'<label class="afkv2-v2-tick"><input type="{kind}" name="{name}" value="{escape(option["id"])}"> '
                     f'{escape(option["text"])}</label>' for option in choices["options"])
    return (f'<fieldset class="afkv2-v2-ticks" data-afkv2-input="tick" data-afkv2-question="{escape(question["id"])}" '
            f'data-afkv2-several="{"true" if several else "false"}"><legend>{hint}</legend>{inputs}'
            '<p class="afkv2-v2-hint">Something else: write a note on this question.</p></fieldset>')


def _outcome(doc: dict, question: dict) -> str:
    """The answer, the drop reason and the assumption of a question, each as words."""
    lines = []
    answer = question.get("answer")
    if answer:
        ticked = ", ".join(visible_label(doc, "element", choice) for choice in answer.get("choices") or [])
        words = f"{STATES['answered']} by {answer['role']} on {answer['date']}: {answer['text']}"
        lines.append(words + (f" Ticked: {ticked}." if ticked else ""))
    if question.get("dropped"):
        lines.append(f"{STATES['dropped']}: {question['dropped']['reason']}")
    if question.get("assumption"):
        lines.append(f"{STATES['assumed']}: {question['assumption']['text']}")
    return "".join(f'<p class="afkv2-v2-outcome">{escape(line)}</p>' for line in lines)


def _question(doc: dict, question: dict, sections: dict) -> str:
    parts = [f'<h3 class="afkv2-v2-h">{escape(question["question"])}</h3>'
             f'<span class="afkv2-chip afkv2-v2-state">{escape(visible_label(doc, "state", question["state"]))}</span>',
             f'<p class="afkv2-v2-who">Who to ask: {escape(", ".join(question["who"]))}</p>',
             _part("Context", _markdown(question["context"])), _part("Why it matters", _markdown(question["why"]))]
    if question.get("ways"):
        parts.append(_part("Ways to find out",
                           "<ul>" + "".join(f"<li>{escape(way)}</li>" for way in question["ways"]) + "</ul>"))
    if question.get("example"):
        parts.append(_part("Example", render_component(question["example"])))
    targets = list(dict.fromkeys(_current_target(sections, section) for section in question.get("links") or []))
    if targets:
        parts.append(f'<div class="afkv2-v2-links">Linked sections: {", ".join(_link(doc, t) for t in targets)}</div>')
    if question.get("waits_on"):
        parts.append(f'<div class="afkv2-v2-links">Waits on: {_link(doc, question["waits_on"])}</div>')
    parts += [_outcome(doc, question), _ticks(question), render_changes(doc, question["changes"])]
    return _article(question, "afkv2-v2-question", "".join(parts), raw=_who_attr(question),
                    question=question["id"], state=question["state"])


def _filter(questions: list) -> str:
    """The native role filter: every role once, in first-asked order, by its first spelling; everyone is no
    choice, since everyone's questions show under each role (PRD AC-033). The page script binds it."""
    roles: dict[str, str] = {}
    for question in questions:
        for role in question["who"]:
            if role.lower() != EVERYONE:
                roles.setdefault(role.lower(), role)
    options = "".join(f'<option value="{escape(key)}">{escape(label)}</option>' for key, label in roles.items())
    return (f'<label class="afkv2-v2-filter">Show the questions for: <select id="afkv2-who-filter" '
            f'class="afkv2-who-filter"><option value="">Every role</option>{options}</select></label>')


def render_questions(doc: dict) -> str:
    """The questions-for-others block, in list order, with its role filter; a page with none gets no block."""
    questions = doc.get("questions") or []
    if not questions:
        return ""
    sections = {entry["id"]: entry for entry in doc.get("sections") or []}
    body = "".join(_question(doc, question, sections) for question in questions)
    return (f'<section class="afkv2-v2-questions" id="afkv2-questions">'
            f'<h2 class="afkv2-section-h">Questions for others</h2>{_filter(questions)}{body}</section>')


def _example(doc: dict, example: dict) -> str:
    stories = "".join(f"<li>{escape(visible_label(doc, 'element', story))}</li>" for story in example["stories"])
    kind = escape(visible_label(doc, "kind", example["kind"]))
    inner = (f'<h3 class="afkv2-v2-h">{escape(example["title"])}</h3>'
             f'<span class="afkv2-chip afkv2-v2-kind">{kind}</span>{render_component(example["body"])}'
             f'{_part("Stories it covers", f"<ul>{stories}</ul>")}{render_changes(doc, example["changes"])}')
    return _article(example, "afkv2-v2-example", inner, kind=example["kind"])


def render_examples(doc: dict) -> str:
    """The worked-examples block, each marked frequent, edge or risky; a page with none gets no block."""
    examples = doc.get("examples") or []
    if not examples:
        return ""
    body = "".join(_example(doc, example) for example in examples)
    return (f'<section class="afkv2-v2-examples" id="afkv2-examples">'
            f'<h2 class="afkv2-section-h">Worked examples</h2>{body}</section>')
