"""Page assembly from a valid page document. Same document, same bytes.

Order: the current round banner, the notes on the whole session, maps, the points of the round with
the copy bar, the settled points, the earlier banners. A point shows once, as its newest card, with its
notes and replies under the heading and its earlier cards in a closed "History". The human sends marks
and lavish annotations with lavish's own Send; the copy bar is the fallback without lavish.
Each ticket, change and commit reference in the text links to the URL that `session.links` names.
The browser tab title is `<ticket> · <feature> · <skill> R-<n>`; the feature drops out when it is the ticket.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

from registry import aliases, lookup, render_component
from schema.note_rules import round_target
from shell.points import grouped
from shell.references import linkify

HERE = Path(__file__).resolve().parent
BASE_CSS, BASE_JS = "kit.css", "runtime.js"
TIPS_ASSETS = {"tips.css", "tips.js"}
NOTES_AND_REPLIES = "notes-and-replies"
CARD_NOTES = "card-notes"
GOLDEN_ANGLE = 137.5


def round_colour(round_: dict) -> str:
    """The round's own colour; a hue step keeps every round number apart from its neighbours."""
    return round_.get("colour") or f"hsl({(round_['n'] * GOLDEN_ANGLE) % 360:.1f}, 72%, 68%)"


def _assets(suffix: str, first: str) -> str:
    """The base asset, then each asset a later component module adds beside it."""
    names = sorted(p.name for p in HERE.glob(f"*{suffix}") if p.name != first and p.name not in TIPS_ASSETS)
    return "".join((HERE / name).read_text(encoding="utf-8") for name in [first, *names])


def _banner(round_: dict, current: bool) -> str:
    return render_component({"type": "round-banner", "id": round_target(round_["n"]), "props": {
        "n": round_["n"], "colour": round_colour(round_), "current": current, **round_["banner"]}})


def _exchange(doc: dict, item: dict) -> str:
    """The card's own notes and replies; the content comes from a registered component."""
    if lookup(CARD_NOTES) is None:
        return ""
    return render_component({"type": CARD_NOTES, "props": {"document": doc, "item": item["id"]}})


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
            f'<summary>Earlier banners ({len(past)})</summary>{"".join(_banner(r, False) for r in past)}</details>')


def _notes_and_replies(doc: dict) -> str:
    """The slot's content comes from a registered component; the page knows no more about it."""
    if lookup(NOTES_AND_REPLIES) is None:
        return ""
    return render_component({"type": NOTES_AND_REPLIES, "props": {"document": doc}})


def targets(doc: dict) -> dict:
    """Each HTML id the page draws that is no element id, with the element id an annotation on it stands for:
    the ids that the components of the maps and cards draw, and the ids of the notes and replies rows."""
    found = {}
    for tree in [*(doc.get("maps") or []), *(item["body"] for r in doc["rounds"] for item in r["items"])]:
        found.update(aliases(tree))
    kind = lookup(NOTES_AND_REPLIES)
    if kind and kind.targets:
        found.update(kind.targets({"document": doc}))
    return found


def _reference(ticket: str) -> str:
    """A ticket that is a number is a GitHub issue: `#` makes it a reference that links."""
    return f"#{ticket}" if ticket.isdigit() else ticket


def tab_title(doc: dict) -> str:
    session = doc["session"]
    n = next(r["n"] for r in doc["rounds"] if r["state"] == "current")
    ticket = _reference(session["ticket"])
    parts = [ticket] + ([session["feature"]] if session["feature"] not in (session["ticket"], ticket) else [])
    return " · ".join([*parts, f'{session["skill"]} R-{n}'])


def _btw_attrs(btw: tuple[int, str] | None) -> str:
    """The side-question listener address `(port, token)` that the btw? panel posts to."""
    if btw is None:
        return ""
    return f' data-afkv2-btw-port="{int(btw[0])}" data-afkv2-btw-token="{escape(btw[1])}"'


def _tip_source(doc: dict) -> str:
    """Page-owned catalogs survive replacement of the derived tooltip runtime."""
    if doc["schema"] != "afkv2.page/1":
        return ""
    tips = doc.get("tips", {})
    source = {kind: tips.get(kind, []) for kind in ("terms", "ids")}
    # Escaping '<' blocks script termination, HTML comments and injector markers.
    payload = json.dumps(source, ensure_ascii=True).replace("<", "\\u003c")
    return f'<script id="afkv2-page-tip-source" type="application/json">{payload}</script>\n'


def build(doc: dict, btw: tuple[int, str] | None = None) -> str:
    """The page; `btw` is the side-question listener address (`btw_listener.address`). With None the page
    has no btw? panel."""
    session = doc["session"]
    current = next(r for r in doc["rounds"] if r["state"] == "current")
    live, settled = grouped(doc)
    maps = "".join(render_component(m) for m in doc.get("maps") or [])
    body = (f'<h1 class="afkv2-title">{escape(session["feature"])}</h1>'
            f'<p class="afkv2-sub">{escape(session["skill"])} · {escape(_reference(session["ticket"]))}</p>'
            f'{_banner(current, True)}'
            f'<section class="afkv2-notes-replies" id="afkv2-notes-replies">{_notes_and_replies(doc)}</section>'
            f'<section class="afkv2-maps" id="afkv2-maps">{maps}</section>'
            f'{_current_section(doc, current, live)}'
            f'{_settled_section(doc, settled, current["n"])}'
            f'{_earlier_banners(doc)}')
    body = linkify(body, session.get("links"))
    title = escape(tab_title(doc))
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{title}</title>\n<style>\n{_assets(".css", BASE_CSS)}</style>\n</head>\n'
            f'<body>\n<div class="afkv2-page"{_btw_attrs(btw)}>{body}</div>\n'
            f'{_tip_source(doc)}'
            f'<script>\n{_assets(".js", BASE_JS)}</script>\n</body>\n</html>\n')
