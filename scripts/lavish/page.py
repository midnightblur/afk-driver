"""Page assembly — the fixed skeleton.

Phase-1 skeleton, in order: head, the current round, open items carried over
from earlier rounds, settled history, the send bar. The process rail, the round
strip and the design map are not part of it.

Order is by liveness, never chronology: the round in play at the top, open
items below it, settled decisions at the bottom, newest first — the human never
scrolls past decided history to reach the current question.

The state rail, the tooltip layer and the dark override are injected at render
time by the hooks from the `data-afk-*` anatomy this module emits; nothing here
draws navigation chrome.
"""

import os

from . import components as C

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def _asset(name):
    with open(os.path.join(ASSETS, name), encoding="utf-8") as handle:
        return handle.read()


def _section(section_id, heading, cards):
    if not cards:
        return ""
    return ('<section class="afk-section" id="%s"><h2>%s</h2>'
            '<div class="afk-cards">%s</div></section>'
            % (section_id, C.esc(heading), "".join(cards)))


def _split(doc):
    """Current round, carried-over open items, settled history."""
    current = None
    carried = []
    settled = []
    for rnd in doc["rounds"]:
        for item in rnd["items"]:
            # Only the current round's live items are answerable: the one send
            # reads the current section, and everything else is history or a
            # question a later round re-asks.
            item["answerable"] = rnd["state"] == "current" and item["state"] != "settled"
            if item["state"] == "settled":
                settled.append((rnd["round"], item))
            elif rnd["state"] != "current":
                carried.append((rnd["round"], item))
        if rnd["state"] == "current":
            current = rnd
    carried.sort(key=lambda pair: pair[0])
    settled.sort(key=lambda pair: -pair[0])
    return current, [i for _, i in carried], [i for _, i in settled]


def build(doc):
    """Return the whole page as one HTML string. Same document, same bytes."""
    current, carried, settled = _split(doc)
    live = [i for i in current["items"] if i["state"] != "settled"]
    header = current["header"]

    # No cap and no target: a round is as large as what it decides. `target`,
    # when the author states one, is context on the heading, never a bound.
    target = header.get("target")
    of_target = " of %d" % target if target else ""
    round_heading = "Round R-%d%s — %d to answer" % (
        header["round"], of_target, len(live))
    round_section = (
        '<section class="afk-round" data-afk-item="%s" data-afk-state="current">'
        '<h2 class="afk-h">%s</h2>%s<div class="afk-cards">%s</div></section>'
        % (C.esc(current["id"]), C.esc(round_heading),
           C.round_header(header),
           "".join(C.render_item(i) for i in live)))

    body = [
        '<h1 class="afk-title">%s</h1>' % C.esc(doc["purpose"]),
        '<p class="afk-sub">%s</p>' % C.esc(doc["feature"]),
        round_section,
        _section("afk-open", "Still open from earlier rounds",
                 [C.render_item(i) for i in carried]),
        _section("afk-settled", "Settled", [C.render_item(i) for i in settled]),
    ]

    send_bar = (
        '<div class="afk-send" id="afk-send" data-afk-round="%d" '
        'data-lavish-ui="afk-send" data-lavish-action="afk-send">'
        '<button type="button" id="afk-send-go" class="afk-primary" '
        'data-lavish-action="afk-send">Send this round</button>'
        '<button type="button" id="afk-send-copy" '
        'data-lavish-action="afk-send">Copy the response</button>'
        # With no cap on round size, navigation is what keeps a long round
        # readable — so the bar names every unmarked card AND moves the human
        # to the first one. Hidden while nothing is unmarked.
        '<button type="button" id="afk-send-jump" hidden '
        'data-lavish-action="afk-send">Go to first unmarked</button>'
        '<span class="afk-send-status"></span></div>' % header["round"])

    spec_dir = doc.get("spec_dir")
    meta = ('<meta name="afk-spec-dir" content="%s">' % C.esc(spec_dir)) if spec_dir else ""

    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>%s — %s</title>\n%s\n<style>\n%s</style>\n</head>\n"
        '<body>\n<div class="afk-page">%s</div>\n%s\n<script>\n%s</script>\n'
        "</body>\n</html>\n"
        % (C.esc(doc["purpose"]), C.esc(doc["feature"]), meta, _asset("kit.css"),
           "".join(body), send_bar, _asset("runtime.js")))
