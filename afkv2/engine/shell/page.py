"""Page assembly from a valid page document. Same document, same bytes.

Order: round banner, notes and replies, maps, cards. The cards section is the current round
with its send bar, then each settled round, newest first, with every item it ever held.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from registry import lookup, render_component

HERE = Path(__file__).resolve().parent
BASE_CSS, BASE_JS = "kit.css", "runtime.js"
TIPS_ASSETS = {"tips.css", "tips.js"}
NOTES_AND_REPLIES = "notes-and-replies"
GOLDEN_ANGLE = 137.5


def round_colour(round_: dict) -> str:
    """The round's own colour; a hue step keeps every round number apart from its neighbours."""
    return round_.get("colour") or f"hsl({(round_['n'] * GOLDEN_ANGLE) % 360:.1f}, 72%, 68%)"


def _assets(suffix: str, first: str) -> str:
    """The base asset, then each asset a later component module adds beside it."""
    names = sorted(p.name for p in HERE.glob(f"*{suffix}") if p.name != first and p.name not in TIPS_ASSETS)
    return "".join((HERE / name).read_text(encoding="utf-8") for name in [first, *names])


def _banner(round_: dict, current: bool) -> str:
    return render_component({"type": "round-banner", "props": {
        "n": round_["n"], "colour": round_colour(round_), "current": current, **round_["banner"]}})


def _card(item: dict, round_: dict, current: bool) -> str:
    return render_component({
        "type": "card",
        "props": {"item": item, "round": round_["n"], "colour": round_colour(round_), "current": current},
        "children": [item["body"]],
    })


def _send_bar(round_: dict, session_id: str) -> str:
    return (f'<div class="afkv2-send" id="afkv2-send" data-afkv2-round="{round_["n"]}" '
            f'data-afkv2-session="{escape(session_id)}" data-lavish-ui="afkv2-send">'
            '<button type="submit" id="afkv2-send-go" class="afkv2-primary">Send my answers</button>'
            '<button type="button" id="afkv2-send-copy">Copy the response</button>'
            '<button type="button" id="afkv2-send-jump" hidden>Go to first unmarked</button>'
            '<output id="afkv2-send-summary" class="afkv2-send-summary" aria-live="polite"></output>'
            '<output class="afkv2-send-status" role="status" aria-live="polite"></output></div>')


def _answerable(item: dict) -> bool:
    return not item.get("state", "open").startswith("settled_")


def _current_section(round_: dict, session_id: str) -> str:
    n = round_["n"]
    cards = "".join(_card(item, round_, True) for item in round_["items"])
    live = any(_answerable(item) for item in round_["items"])
    section = (f'<section class="afkv2-round" id="afkv2-r-{n}" data-afkv2-item="R-{n}" data-afkv2-state="current" '
               f'style="--afkv2-round: {escape(round_colour(round_))}">'
               f'<h2 class="afkv2-h">Round {n}: your answers</h2><div class="afkv2-cards">{cards}</div>'
               f'{_send_bar(round_, session_id) if live else ""}</section>')
    if not live:
        return section
    return (f'<form id="afkv2-answer-form" data-afkv2-answer-form="1" data-afkv2-round="{n}" '
            f'data-lavish-question="round:R-{n}">{section}</form>')


def _past_section(round_: dict) -> str:
    n = round_["n"]
    cards = "".join(_card(item, round_, False) for item in round_["items"])
    return (f'<section class="afkv2-round-past" id="afkv2-r-{n}" style="--afkv2-round: {escape(round_colour(round_))}">'
            f'{_banner(round_, False)}<div class="afkv2-cards">{cards}</div></section>')


def _notes_and_replies(doc: dict) -> str:
    """The slot's content comes from a registered component; the page knows no more about it."""
    if lookup(NOTES_AND_REPLIES) is None:
        return ""
    return render_component({"type": NOTES_AND_REPLIES, "props": {"document": doc}})


def build(doc: dict) -> str:
    session = doc["session"]
    current = next(r for r in doc["rounds"] if r["state"] == "current")
    past = sorted((r for r in doc["rounds"] if r["state"] != "current"), key=lambda r: -r["n"])
    maps = "".join(render_component(m) for m in doc.get("maps") or [])
    body = (f'<h1 class="afkv2-title">{escape(session["feature"])}</h1>'
            f'<p class="afkv2-sub">{escape(session["skill"])} · {escape(session["ticket"])}</p>'
            f'{_banner(current, True)}'
            f'<section class="afkv2-notes-replies" id="afkv2-notes-replies">{_notes_and_replies(doc)}</section>'
            f'<section class="afkv2-maps" id="afkv2-maps">{maps}</section>'
            f'{_current_section(current, session["id"])}'
            f'{"".join(_past_section(r) for r in past)}')
    title = f'{escape(session["feature"])}: round {current["n"]}'
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{title}</title>\n<style>\n{_assets(".css", BASE_CSS)}</style>\n</head>\n'
            f'<body>\n<div class="afkv2-page">{body}</div>\n'
            f'<script>\n{_assets(".js", BASE_JS)}</script>\n</body>\n</html>\n')
