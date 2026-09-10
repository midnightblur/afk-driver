"""Page assembly — the fixed skeleton.

Skeleton order: head, the current round, its send bar, open items carried over
from earlier rounds, settled history. The design map is not part of it.

The current round is grouped when its header declares groups: one subsection
per group, in the declared order, which the schema has already checked is a
dependency order. Grouping is what makes a round with no cap navigable — the
human reads the shape line, then takes a group.

Order is by liveness, never chronology: the round in play at the top, open
items below it, settled decisions at the bottom, newest first — the human never
scrolls past decided history to reach the current question.

The state rail, the tooltip layer and the dark override are injected at render
time by the hooks from the `data-afk-*` anatomy this module emits; nothing here
draws navigation chrome.
"""

import os

from . import components as C
from . import schema

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def _asset(name):
    with open(os.path.join(ASSETS, name), encoding="utf-8") as handle:
        return handle.read()


def _settled_by_round(settled):
    """Settled history in round subsections, newest round first.

    The round strip needs somewhere to land, and a flat newest-first list has
    no per-round target. Grouping by round gives every notch an anchor and
    keeps the newest-first order the human reads history in.
    """
    if not settled:
        return ""
    order = []
    for number, _ in settled:
        if number not in order:
            order.append(number)
    blocks = []
    for number in sorted(order, reverse=True):
        cards = [item for round_number, item in settled if round_number == number]
        blocks.append('<section class="afk-round-past" id="afk-r-%d">'
                      '<h3>Round R-%d</h3><div class="afk-cards">%s</div></section>'
                      % (number, number, "".join(cards)))
    return ('<section class="afk-section" id="afk-settled"><h2>Settled</h2>%s</section>'
            % "".join(blocks))


def _section(section_id, heading, cards):
    if not cards:
        return ""
    return ('<section class="afk-section" id="%s"><h2>%s</h2>'
            '<div class="afk-cards">%s</div></section>'
            % (section_id, C.esc(heading), "".join(cards)))


def _grouped(live, header, states):
    """The current round's cards, in their groups or in one flat list.

    A group with no cards is still rendered, saying so: the shape line counted
    it, and a group that vanishes between the count and the page makes the
    human hunt for a group that was never there.

    A group declaring `layout: "table"` renders its members as one table, one
    row per item. The items are unchanged either way — a row carries the same
    anatomy as a card, so anchors, chips, persistence and the send read it
    identically.
    """
    groups = header.get("groups") or []
    if not groups:
        return ('<div class="afk-cards">%s</div>'
                % "".join(C.render_item(i, states) for i in live))
    out = []
    claimed = set()
    for group in groups:
        members = [i for i in live if i.get("group") == group["id"]]
        claimed.update(id(i) for i in members)
        after = group.get("after") or []
        waits = (' <span class="afk-chip-note">after %s</span>'
                 % C.esc(", ".join(after))) if after else ""
        if not members:
            cards = '<p class="afk-empty-group">Nothing left to answer here.</p>'
        elif schema.group_layout(group) == schema.TABLE_LAYOUT:
            # One table for the whole group, one row per item. The schema has
            # already refused any member a row cannot hold.
            cards = C.confirm_table(members, states)
        else:
            cards = "".join(C.render_item(i, states, level=4) for i in members)
        out.append('<section class="afk-group" id="afk-g-%s">'
                   '<h3 class="afk-group-h">%s <span class="afk-count">%d</span>%s</h3>'
                   '<div class="afk-cards">%s</div></section>'
                   % (C.esc(group["id"]), C.esc(group["title"]),
                      len(members), waits, cards))

    # Nothing may fall between the groups. The schema binds every live card to
    # a declared group, so reaching here means a later transform dropped the
    # field — and a card the human never sees is worse than a card in the
    # wrong section, because nothing on the page says it is missing.
    orphans = [i for i in live if id(i) not in claimed]
    if orphans:
        out.append('<section class="afk-group" id="afk-g-unplaced">'
                   '<h3 class="afk-group-h">In no group '
                   '<span class="afk-count">%d</span></h3>'
                   '<div class="afk-cards">%s</div></section>'
                   % (len(orphans),
                      "".join(C.render_item(i, states, level=4) for i in orphans)))
    return "".join(out)


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
    return current, [i for _, i in carried], settled


def build(doc):
    """Return the whole page as one HTML string. Same document, same bytes."""
    current, carried, settled = _split(doc)
    live = [i for i in current["items"] if i["state"] != "settled"]
    header = current["header"]
    states = C.item_states(doc)

    # No cap and no target: a round is as large as what it decides. `target`,
    # when the author states one, is context on the heading, never a bound.
    target = header.get("target")
    of_target = " of %d" % target if target else ""
    round_heading = "Round R-%d%s — %d to answer" % (
        header["round"], of_target, len(live))
    # The re-audit strip opens the round, ahead of the header: an unmarked
    # decision from the last send is the first thing the round has to say.
    round_section = (
        '<section class="afk-round" id="afk-r-%d" data-afk-item="%s" '
        'data-afk-state="current">'
        '<h2 class="afk-h">%s</h2>%s%s%s</section>'
        % (header["round"], C.esc(current["id"]), C.esc(round_heading),
           C.re_audit_strip(header, current["items"]),
           C.round_header(header, len(live)),
           _grouped(live, header, states)))

    send_bar = (
        '<div class="afk-send" id="afk-send" data-afk-round="%d" '
        'data-lavish-ui="afk-send" data-lavish-action="afk-send">'
        '<button type="button" id="afk-send-go" class="afk-primary" '
        'data-lavish-action="afk-send">Send this round to the agent</button>'
        '<button type="button" id="afk-send-copy" '
        'data-lavish-action="afk-send">Copy the response</button>'
        # With no cap on round size, navigation is what keeps a long round
        # readable — so the bar names every unmarked card AND moves the human
        # to the first one. Hidden while nothing is unmarked.
        '<button type="button" id="afk-send-jump" hidden '
        'data-lavish-action="afk-send">Go to first unmarked</button>'
        '<span class="afk-send-status"></span></div>' % header["round"])

    # A round with nothing answerable is a record, not a question: no bar, so
    # there is no control offering to send an empty response.
    if not live:
        send_bar = ""

    # The bar sits in the flow directly under the round it sends, never at the
    # end of the document. A page whose settled history is longer than its
    # current round strands a document-end bar below every settled card, and a
    # host that sizes its frame to content height defeats `position: fixed` as
    # well — so the only placement that holds is next to the cards it sends.
    # The two strips sit above the round: the map reads before the detail, and
    # both are static data the human never has to open anything to see.
    body = [
        C.process_rail(doc.get("stage")),
        '<h1 class="afk-title">%s</h1>' % C.esc(doc["purpose"]),
        '<p class="afk-sub">%s</p>' % C.esc(doc["feature"]),
        C.round_strip(doc),
        round_section,
        send_bar,
        _section("afk-open", "Still open from earlier rounds",
                 [C.render_item(i, states) for i in carried]),
        _settled_by_round([(number, C.render_item(item, states))
                           for number, item in settled]),
        C.decision_ledger(settled),
    ]

    spec_dir = doc.get("spec_dir")
    meta = ('<meta name="afk-spec-dir" content="%s">' % C.esc(spec_dir)) if spec_dir else ""

    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>%s — %s</title>\n%s\n<style>\n%s</style>\n</head>\n"
        '<body>\n<div class="afk-page">%s</div>\n<script>\n%s</script>\n'
        "</body>\n</html>\n"
        % (C.esc(doc["purpose"]), C.esc(doc["feature"]), meta, _asset("kit.css"),
           "".join(body), _asset("runtime.js")))
