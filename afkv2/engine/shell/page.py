"""Page assembly from a valid page document. Same document, same bytes.

Order: the current round banner, the notes on the whole session, maps, the points of the round with
the copy bar, the settled points, the earlier banners. A point shows once, as its newest card, with its
notes and replies under the heading and its earlier cards in a closed "History". The human sends marks
and lavish annotations with lavish's own Send; the copy bar is the fallback without lavish.
Each ticket, change and commit reference in the text links to the URL that `session.links` names.
The heading and the browser tab read `<ticket> · <short title> · <step>`, the same every round. A page with no
ticket drops it; a page with no short title (an upgraded format 0 page) shows its feature; a name that repeats the
ticket, or a step that repeats the start of an earlier part, shows once.
Under the heading, the notices of the page (engine notices): 1 git-state line and 1 line per secret hit.
A page with a code block or a diff inlines the copy of highlight.js and its 2 themes once, after the page script;
a page with neither holds none of them (ADR-0003 design).
"""

from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

import diagrams
from registry import aliases, lookup, page_context, render_component, walk
from schema.note_rules import round_target
from shell.points import grouped
from shell.references import link_cards, linkify

HERE = Path(__file__).resolve().parent
BASE_CSS, BASE_JS = "kit.css", "runtime.js"
TIPS_ASSETS = {"tips.css", "tips.js"}
NOTES_AND_REPLIES = "notes-and-replies"
CARD_NOTES = "card-notes"
GOLDEN_ANGLE = 137.5
NODE_CARDS_ID = "afkv2-node-cards"
HIGHLIGHT = HERE / "highlight"
HIGHLIGHTED = {"code", "diff"}
LIGHT_THEME = ':root[data-theme="light"]{{{}}}'
COMMENT = re.compile(r"/\*.*?\*/", re.S)

ELEMENT_ATTR, FRESH_ATTR = 'data-afkv2-element="{}"', ' data-afkv2-fresh="{}"'


def round_colour(round_: dict) -> str:
    """The round's own colour; a hue step keeps every round number apart from its neighbours."""
    return round_.get("colour") or f"hsl({(round_['n'] * GOLDEN_ANGLE) % 360:.1f}, 72%, 68%)"


def _assets(suffix: str, first: str) -> str:
    """The base asset, then each asset a later component module adds beside it."""
    names = sorted(p.name for p in HERE.glob(f"*{suffix}") if p.name != first and p.name not in TIPS_ASSETS)
    return "".join((HERE / name).read_text(encoding="utf-8") for name in [first, *names])


def _cards(doc: dict) -> dict:
    """Each card id with its newest card."""
    return {item["id"]: item for round_ in doc["rounds"] for item in round_["items"]}


def _changed_ids(round_: dict) -> list:
    """Each element the round's `changed` list names, then each one its answers' lists name, once."""
    lists = [round_.get("changed") or [], *((reply.get("changed") or []) for reply in round_.get("replies") or [])]
    return list(dict.fromkeys(element for found in lists for element in found))


def _from_format_0(doc: dict) -> bool:
    """The in-memory mark of a page read from a format 0 file (`engine.FromFormat0`)."""
    return getattr(doc, "from_format_0", False)


def _format_1_answer(reply: dict) -> bool:
    """An answer written in format 1: it has an id. A format 0 answer has none (page-v0.schema.json), and keeps
    having none after the page is written as format 1, so its `about` stays readable."""
    return "id" in reply


def _answers_read(doc: dict) -> dict:
    """The document as the notes tables read it: `about` is read on a format 0 answer only, so a format 1 answer
    goes on without it."""
    if _from_format_0(doc) or not any("about" in reply and _format_1_answer(reply)
                                      for r in doc["rounds"] for reply in r.get("replies") or []):
        return doc
    rounds = [{**r, "replies": [{k: v for k, v in reply.items() if k != "about" or not _format_1_answer(reply)}
                                for reply in r["replies"]]} if r.get("replies") else r for r in doc["rounds"]]
    return {**doc, "rounds": rounds}


def _changed(doc: dict, round_: dict) -> dict:
    """After round 1, the banner's list of what changed: each changed element once, a card by its title. A page
    from format 0 holds no change data, so its banner has no such list."""
    if round_["n"] == 1 or _from_format_0(doc):
        return {}
    cards = _cards(doc)
    return {"changed": [{"id": element, "label": (cards.get(element) or {}).get("title") or element}
                        for element in _changed_ids(round_)]}


def _banner(doc: dict, round_: dict, current: bool) -> str:
    return render_component({"type": "round-banner", "id": round_target(round_["n"]), "props": {
        "n": round_["n"], "colour": round_colour(round_), "current": current, **round_["banner"],
        **_changed(doc, round_)}})


def _node_cards(doc: dict) -> str:
    """The card of each map box, for the box click and its hover: `{node: [newest card, round of its last
    change]}`. The last change is the card's round, or a later round that changed the card or the box."""
    trees = [*(doc.get("maps") or []), *(item["body"] for r in doc["rounds"] for item in r["items"])]
    boxes = {node["id"] for tree in trees for _, part in walk(tree) if part["type"] == "map"
             for node in part["props"]["nodes"]}
    found = {}
    for round_ in doc["rounds"]:
        for item in round_["items"]:
            if item.get("node") in boxes:
                found[item["node"]] = [item["id"], round_["n"]]
    for round_ in doc["rounds"]:
        for node, entry in found.items():
            if {node, entry[0]} & set(_changed_ids(round_)):
                entry[1] = max(entry[1], round_["n"])
    if not found:
        return ""
    data = json.dumps(found, sort_keys=True).replace("</", "<\\/")
    return f'<script type="application/json" id="{NODE_CARDS_ID}">{data}</script>'


def _round_marks(html: str, round_: dict) -> str:
    """A mark on each element that the current round or its answers changed; no other element has one."""
    for element in _changed_ids(round_):
        anchor = ELEMENT_ATTR.format(escape(element))
        html = html.replace(anchor, anchor + FRESH_ATTR.format(round_["n"]), 1)
    return html


def _exchange(doc: dict, item: dict) -> str:
    """The card's own notes and replies; the content comes from a registered component."""
    if lookup(CARD_NOTES) is None:
        return ""
    rows = render_component({"type": CARD_NOTES, "props": {"document": doc, "item": item["id"]}})
    return f'<div class="afkv2-nr-scroll">{rows}</div>' if rows else ""


def _card(doc: dict, item: dict, round_: dict, current: bool, **extra) -> str:
    return render_component({
        "type": "card",
        "props": {"item": item, "round": round_["n"], "colour": round_colour(round_), "current": current,
                  "exchange": _exchange(doc, item), **extra},
        "children": [item["body"]],
    })


def _history(doc: dict, point) -> str:
    """The earlier cards of a point, newest first, in a closed details element."""
    if not point.history:
        return ""
    names = ", ".join(f'R-{round_["n"]} {item["id"]}' for item, round_ in point.history)
    cards = "".join(_card(doc, item, round_, False) for item, round_ in point.history)
    return (f'<details class="afkv2-history" data-afkv2-fold="history-{escape(point.head["id"])}">'
            f'<summary>History ({escape(names)})</summary><div class="afkv2-cards">{cards}</div></details>')


def _point(doc: dict, point, current_n: int, settled: bool = False) -> str:
    """A settled point folds to its heading and settled line on the rail, an info card of an earlier round too."""
    extra = {"history": _history(doc, point), **({"rail": "settled"} if settled else {})}
    return _card(doc, point.head, point.round, point.round["n"] == current_n, **extra)


COPY_BAR = ('<div class="afkv2-copy" id="afkv2-copy" data-lavish-ui="afkv2-copy">'
            '<p class="afkv2-copy-hint">Pick a mark on each card. To add a note, annotate any part of the page. '
            'Then send marks and notes with Send to Agent in the lavish panel.</p>'
            '<button type="button" id="afkv2-copy-go">Copy the response</button>'
            '<output class="afkv2-copy-status" role="status" aria-live="polite"></output></div>')


def _answerable(item: dict) -> bool:
    return not item.get("state", "open").startswith("settled_")


def _current_section(doc: dict, round_: dict, points: list) -> str:
    """The mark runtime reads the session and the round here: they key each queued mark."""
    n = round_["n"]
    cards = "".join(_point(doc, point, n) for point in points)
    live = any(_answerable(item) for item in round_["items"])
    return (f'<section class="afkv2-round" id="afkv2-r-{n}" data-afkv2-item="R-{n}" data-afkv2-state="current" '
            f'data-afkv2-round="{n}" data-afkv2-session="{escape(doc["session"]["id"])}" '
            f'style="--afkv2-round: {escape(round_colour(round_))}">'
            f'<h2 class="afkv2-h">Round {n}: the points</h2><div class="afkv2-cards">{cards}</div>'
            f'{COPY_BAR if live else ""}</section>')


def _settled_section(doc: dict, points: list, current_n: int) -> str:
    if not points:
        return ""
    cards = "".join(_point(doc, point, current_n, settled=True) for point in points)
    return (f'<section class="afkv2-settled-points" id="afkv2-settled">'
            f'<h2 class="afkv2-section-h">Settled by earlier rounds ({len(points)})</h2>'
            '<p class="afkv2-nr-intro">Each point shows how it settled. Open one to read the card, its notes and '
            f'its history. A note on a settled card opens it again.</p><div class="afkv2-cards">{cards}</div></section>')


def _earlier_banners(doc: dict) -> str:
    past = sorted((r for r in doc["rounds"] if r["state"] != "current"), key=lambda r: -r["n"])
    if not past:
        return ""
    return (f'<details class="afkv2-earlier-banners" id="afkv2-earlier-banners" data-afkv2-fold="banners">'
            f'<summary>Earlier banners ({len(past)})</summary>{"".join(_banner(doc, r, False) for r in past)}</details>')


def _notes_and_replies(doc: dict) -> str:
    """The slot's content comes from a registered component; the page knows no more about it."""
    if lookup(NOTES_AND_REPLIES) is None:
        return ""
    return render_component({"type": NOTES_AND_REPLIES, "props": {"document": doc}})


def targets(doc: dict) -> dict:
    """Each HTML id the page draws that is no element id, with the element id an annotation on it stands for:
    the ids that the components of the maps and cards draw, and the ids of the notes and replies rows."""
    found, doc = {}, _answers_read(doc)
    for tree in [*(doc.get("maps") or []), *(item["body"] for r in doc["rounds"] for item in r["items"])]:
        found.update(aliases(tree))
    kind = lookup(NOTES_AND_REPLIES)
    if kind and kind.targets:
        found.update(kind.targets({"document": doc}))
    return found


def _read_highlight(name: str, bare: bool = False) -> str:
    """A highlighter file; `bare` drops its comments, which keeps the page under its weight cap. The library keeps
    its banner, which holds its licence."""
    text = (HIGHLIGHT / name).read_text(encoding="utf-8")
    return COMMENT.sub("", text).strip() if bare else text


def _highlighter(doc: dict) -> tuple[str, str]:
    """(the 2 themes, the library and its run script) on a page with a code block or a diff; else nothing. The page
    is dark first: the dark theme applies, and the light theme applies under `data-theme="light"`."""
    trees = [*(doc.get("maps") or []), *(item["body"] for r in doc["rounds"] for item in r["items"])]
    if not any(part["type"] in HIGHLIGHTED for tree in trees for _, part in walk(tree)):
        return "", ""
    themes = _read_highlight("github-dark.min.css", True) + LIGHT_THEME.format(_read_highlight("github.min.css", True))
    return (f"<style>{themes}</style>\n",
            f"<script>{_read_highlight('highlight.min.js')}\n{_read_highlight('run.js', True)}</script>\n")


def _reference(ticket: str) -> str:
    """A ticket that is a number is a GitHub issue: `#` makes it a reference that links."""
    return f"#{ticket}" if ticket.isdigit() else ticket


def stable_title(doc: dict) -> str:
    """`<ticket> · <short title> · <step>`: no round in it, so it stays the same every round."""
    session = doc["session"]
    ticket = session.get("ticket")
    parts = [_reference(ticket)] if ticket else []
    name = session.get("short_title") or session["feature"]
    if name not in (ticket, *parts):
        parts.append(name)
    step = session.get("step")
    repeats = step and any(part.startswith(step) for part in parts)
    return " · ".join([*parts, *([step] if step and not repeats else [])])


GIT_LINES = {
    "committed": "Git: this page is committed.",
    "untracked": "Git: this page is in the repository but not committed yet.",
    "ignored": "Git: git ignores this page, so it is not committed.",
    "outside": "Git: this page is outside the repository, so it is not committed.",
    "unknown": "Git: the git state of this page is unknown ({why}), so no secret scan ran.",
}


def _notices(found: dict | None) -> str:
    """The git-state line and one warning per secret hit: file, line and shape, never the value."""
    if not found:
        return ""
    line = GIT_LINES.get(found.get("git_state"), GIT_LINES["unknown"]).format(why=found.get("git_reason") or "no answer")
    lines = [f'<p class="afkv2-notice">{escape(line)}</p>']
    lines += [f'<p class="afkv2-notice afkv2-notice--secret">Secret warning: {escape(str(hit["file"]))}, line '
              f'{int(hit["line"])}, holds a value of the shape {escape(str(hit["shape"]))}. Take it out before a commit.</p>'
              for hit in found.get("secrets") or []]
    if found.get("secrets_more"):
        lines.append(f'<p class="afkv2-notice afkv2-notice--secret">And {int(found["secrets_more"])} more secret '
                     'warnings; the present answer counts them.</p>')
    return f'<div class="afkv2-notices" role="status">{"".join(lines)}</div>'


def _btw_attrs(btw: tuple[int, str] | None) -> str:
    """The side-question listener address `(port, token)` that the btw? panel posts to."""
    if btw is None:
        return ""
    return f' data-afkv2-btw-port="{int(btw[0])}" data-afkv2-btw-token="{escape(btw[1])}"'


def _tip_source(doc: dict) -> str:
    """Page-owned catalogs survive replacement of the derived tooltip runtime. A page read from a format 0
    file has none: it keeps its legacy sidecar tips, which the injector reads only without this block."""
    if doc["schema"] != "afkv2.page/1" or _from_format_0(doc):
        return ""
    tips = doc.get("tips", {})
    source = {kind: tips.get(kind, []) for kind in ("terms", "ids")}
    # Escaping '<' blocks script termination, HTML comments and injector markers.
    payload = json.dumps(source, ensure_ascii=True).replace("<", "\\u003c")
    return f'<script id="afkv2-page-tip-source" type="application/json">{payload}</script>\n'


def build(doc: dict, btw: tuple[int, str] | None = None, notices: dict | None = None) -> str:
    """The page; `btw` is the side-question listener address (`btw_listener.address`). With None the page
    has no btw? panel. `notices` is `{git_state, git_reason, secrets}`; with None the page has no notices.
    Each component renders in the context of the document's named value sets, in one diagram run: the SVG ids of
    the page's diagrams start afresh, so the same document builds the same bytes."""
    with page_context(doc.get("value_sets")), diagrams.page_run():
        return _build(_answers_read(doc), btw, notices)


def _build(doc: dict, btw: tuple[int, str] | None, notices: dict | None) -> str:
    session = doc["session"]
    current = next(r for r in doc["rounds"] if r["state"] == "current")
    live, settled = grouped(doc)
    maps = "".join(render_component(m) for m in doc.get("maps") or [])
    title = escape(stable_title(doc))
    body = (f'<h1 class="afkv2-title">{title}</h1>{_notices(notices)}'
            f'{_banner(doc, current, True)}'
            f'<section class="afkv2-notes-replies" id="afkv2-notes-replies">{_notes_and_replies(doc)}</section>'
            f'<section class="afkv2-maps" id="afkv2-maps">{maps}</section>'
            f'{_current_section(doc, current, live)}'
            f'{_settled_section(doc, settled, current["n"])}'
            f'{_earlier_banners(doc)}{_node_cards(doc)}')
    body = link_cards(linkify(_round_marks(body, current), session.get("links")), _cards(doc))
    themes, highlighter = _highlighter(doc)
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{title}</title>\n<style>\n{_assets(".css", BASE_CSS)}</style>\n{themes}</head>\n'
            f'<body>\n<div class="afkv2-page"{_btw_attrs(btw)}>{body}</div>\n'
            f'{_tip_source(doc)}'
            f'<script>\n{_assets(".js", BASE_JS)}</script>\n{highlighter}</body>\n</html>\n')
