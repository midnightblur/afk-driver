"""Page assembly from a valid page document. Same document, same bytes.

Order: round banner, notes and replies, maps, cards. The cards section is the current round
with its copy bar, then each settled round, newest first, with every item it ever held. The human
sends marks and lavish annotations with lavish's own Send; the copy bar is the fallback without lavish.
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


COPY_BAR = ('<div class="afkv2-copy" id="afkv2-copy" data-lavish-ui="afkv2-copy">'
            '<p class="afkv2-copy-hint">Pick a mark on each card. To add a note, annotate any part of the page. '
            'Then send marks and notes with Send to Agent in the lavish panel.</p>'
            '<button type="button" id="afkv2-copy-go">Copy the response</button>'
            '<output class="afkv2-copy-status" role="status" aria-live="polite"></output></div>')


def _answerable(item: dict) -> bool:
    return not item.get("state", "open").startswith("settled_")


def _current_section(round_: dict, session_id: str) -> str:
    """The mark runtime reads the session and the round here: they key each queued mark."""
    n = round_["n"]
    cards = "".join(_card(item, round_, True) for item in round_["items"])
    live = any(_answerable(item) for item in round_["items"])
    return (f'<section class="afkv2-round" id="afkv2-r-{n}" data-afkv2-item="R-{n}" data-afkv2-state="current" '
            f'data-afkv2-round="{n}" data-afkv2-session="{escape(session_id)}" '
            f'style="--afkv2-round: {escape(round_colour(round_))}">'
            f'<h2 class="afkv2-h">Round {n}: your answers</h2><div class="afkv2-cards">{cards}</div>'
            f'{COPY_BAR if live else ""}</section>')


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


def slot_targets(doc: dict) -> dict:
    """The HTML ids the slot's component draws, each with the element id an annotation on it stands for."""
    kind = lookup(NOTES_AND_REPLIES)
    return kind.targets({"document": doc}) if kind and kind.targets else {}


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
