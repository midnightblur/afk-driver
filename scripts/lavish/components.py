"""The six phase-1 components.

One function per component, each emitting the markup its row in
`LAVISH-KIT.md` describes. Nothing here decides content: the round JSON is the
content, and this module is the only thing that turns it into HTML.

Every answerable card carries exactly one element with `data-afk-input="choice"`
and exactly one with `data-afk-input="note"` — the attribute contract the inline
runtime composes the round response from. A card's first child is its one-line
heading, so the injected session rail can label it and collapse to it.

Three parts per card, in this order (`ROUND.md` navigability rule 3): the
heading, the **lede** — the recommendation and the one sentence behind it, plus
anything a scanning reader must not miss — and a `<details>` block holding the
rest. A reader who reads only headings and ledes knows every decision the round
holds. The answer surface stays outside the disclosure: a card can be marked
without being opened, so scanning and answering are one pass rather than two.
"""

from html import escape

from . import schema

# Written on the card and read by the runtime, so a hand-authored card composes
# identically to a rendered one.
CHOICE_ATTR = 'data-afk-input="choice"'
NOTE_ATTR = 'data-afk-input="note"'

WRITE_IN = "write-in"
WRITE_IN_LABEL = "Something else — put it in the note"


def esc(value):
    return escape("" if value is None else str(value), quote=True)


def _attr(name, value):
    return ' %s="%s"' % (name, esc(value))


def choice(item_id, options, legend):
    """One radio set: the card's single choice control.

    `options` is a list of `(token, label)` pairs in the order the human reads
    them. The attribute sits on the fieldset, not on each radio, so the card
    carries exactly one choice control however many values it offers.
    """
    rows = []
    for token, label in options:
        rows.append(
            '<label class="afk-opt"><input type="radio" name="afk-choice:%s" value="%s">'
            '<span>%s</span></label>' % (esc(item_id), esc(token), esc(label)))
    return ('<fieldset class="afk-choice" %s><legend>%s</legend>%s</fieldset>'
            % (CHOICE_ATTR, esc(legend), "".join(rows)))


def note(item_id, placeholder="Your words — always optional"):
    return ('<label class="afk-note"><span>Note</span>'
            '<textarea %s name="afk-note:%s" rows="2" placeholder="%s"></textarea></label>'
            % (NOTE_ATTR, esc(item_id), esc(placeholder)))


def anchor(item_id):
    """The element id a chip or a rail jumps to.

    Prefixed, because an item id is the author's word and `afk-send` is the
    page's: an unprefixed collision would point a chip at the send bar.
    """
    return "afk-i-%s" % item_id


def item_attrs(item, answerable):
    """The `data-afk-*` anatomy every item element carries, card or row.

    One home for it: the runtime walks `[data-afk-item]` and reads the state,
    the group and the required flag off whatever element carries them, so the
    two layouts of the same item must not spell the anatomy differently.
    """
    attrs = [_attr("id", anchor(item["id"])),
             _attr("data-afk-item", item["id"]),
             _attr("data-afk-state", item["state"])]
    if item.get("fresh"):
        attrs.append(" data-afk-fresh")
    if answerable and schema.required_mark(item):
        attrs.append(' data-afk-required="1"')
    return "".join(attrs)


def _card(item, kind, heading, lede, summary, detail, answer, level=3):
    """One card: heading, lede, disclosed detail, answer surface.

    The answer surface exists only inside the current round. A card carried
    over from an earlier round shows its state and nothing to mark: an
    unanswered item is re-asked as a fresh card in a later round, so an answer
    control outside the current section would collect a mark the one send never
    reads.
    """
    answerable = item.get("answerable") and answer
    attrs = [item_attrs(item, answerable)]

    parts = ['<h%d class="afk-h">%s</h%d>' % (level, esc(heading), level)]
    if lede:
        parts.append('<div class="afk-lede">%s</div>' % lede)
    if detail:
        # Open on demand, closed by default, and the summary says what is
        # behind it: a disclosure whose label does not name its contents is a
        # reason not to click, which turns rule 3 into hidden explanation.
        parts.append('<details class="afk-detail"><summary>%s</summary>'
                     '<div class="afk-detail-body">%s</div></details>'
                     % (esc(summary), detail))
    if answerable:
        parts.append('<div class="afk-answer">%s</div>' % answer)
    return ('<article class="afk-card afk-card--%s"%s>%s</article>'
            % (kind, "".join(attrs), "".join(parts)))


def _dl(pairs):
    """A term/definition block — the shape every card states its fields in."""
    rows = []
    for term, value in pairs:
        if value is None:
            continue
        rows.append("<dt>%s</dt><dd>%s</dd>" % (esc(term), value))
    return '<dl class="afk-fields">%s</dl>' % "".join(rows) if rows else ""


def _bullets(values, render=esc):
    return "<ul>%s</ul>" % "".join("<li>%s</li>" % render(v) for v in values)


def _alt_label(alt):
    label = alt.get("label") or alt.get("id")
    if alt.get("why"):
        return "%s — %s" % (label, alt["why"])
    return label


def depends_on(item):
    """The ids this card waits on, wherever its component keeps them."""
    if item["component"] == "decided_card":
        return (item.get("scope") or {}).get("depends_on") or []
    return item.get("depends_on") or []


def deps_strip(item, states=None):
    """Parent ids as chips, plus a `provisional` badge while one is unmarked.

    States come from the artifact, not from the card: a card cannot know
    whether its parent has been settled, and a dependent that claims to hold
    while its parent is still open is the one wrong statement this strip
    exists to prevent.
    """
    ids = depends_on(item)
    if not ids:
        return ""
    states = states or {}
    chips = []
    pending = []
    for parent in ids:
        state = states.get(parent, "open")
        if state != "settled":
            pending.append(parent)
        chips.append('<a class="afk-chip afk-chip--%s" href="#%s">%s</a>'
                     % (esc(state), esc(anchor(parent)), esc(parent)))
    badge = ""
    if pending:
        badge = ('<span class="afk-badge afk-badge--open">provisional</span>'
                 '<span class="afk-chip-note">holds while %s stands</span>'
                 % esc(", ".join(pending)))
    return ('<p class="afk-deps"><span class="afk-deps-label">Depends on</span>%s%s</p>'
            % ("".join(chips), badge))


def _depends(scope):
    ids = scope.get("depends_on") or []
    return ", ".join(ids) if ids else "none"


def prose(text):
    """An author's own paragraphs, blank-line separated, escaped."""
    blocks = [b.strip() for b in str(text).split(chr(10) * 2) if b.strip()]
    return "".join('<p class="afk-context">%s</p>' % esc(b) for b in blocks)


# --------------------------------------------------------------------------
# The two strips — where this session sits, and where this round sits in it
# --------------------------------------------------------------------------

def process_rail(stage):
    """The chain stages, this session's lit. Absent stage, absent rail.

    No links. A done stage's artifact path is a fact `skills/afk/to-prd/
    INDEX-FORMAT.md` already owns, and a second copy here would go stale
    against it — the rail answers where the session is, which needs no path.
    """
    if not stage:
        return ""
    now = schema.STAGES.index(stage)
    steps = []
    for index, name in enumerate(schema.STAGES):
        state = "done" if index < now else ("current" if index == now else "upcoming")
        steps.append('<li class="afk-step afk-step--%s"%s>%s</li>'
                     % (state,
                        ' aria-current="step"' if state == "current" else "",
                        esc(name)))
    return ('<nav class="afk-rail" aria-label="Where this session sits in the chain">'
            "<ol>%s</ol></nav>" % "".join(steps))


def re_audit_strip(header, items):
    """One line per decided card that came back from the last send unmarked.

    Ids are authored; the decision and the citation are read off the card the
    round already presents. Nothing else is listed here — one trigger, so the
    strip stays a fact about unanswered decisions rather than a second place
    to put warnings.
    """
    ids = header.get("re_audit") or []
    if not ids:
        return ""
    by_id = {i["id"]: i for i in items}
    lines = []
    for item_id in ids:
        item = by_id.get(item_id, {})
        decision = item.get("decision") or item.get("question") or item_id
        evidence = item.get("evidence")
        cite = evidence.get("cite") if isinstance(evidence, dict) else (
            item.get("cite") or "")
        lines.append('<li><a href="#%s"><code>%s</code></a> %s%s</li>'
                     % (esc(anchor(item_id)), esc(item_id), esc(decision),
                        " <code>%s</code>" % esc(cite) if cite else ""))
    return ('<div class="afk-reaudit" role="note"><b>Sent unmarked, so not applied:</b>'
            "<ul>%s</ul>"
            "<p>These stay listed until they carry a mark. Silence is not agreement.</p>"
            "</div>" % "".join(lines))


def decision_ledger(settled):
    """Every settled decision as one row, at the bottom, closed.

    A row links to its own settled card instead of expanding a copy of it. The
    card is the record; a ledger that restated the evidence would be a second
    home for it, and the two would drift.
    """
    if not settled:
        return ""
    rows = []
    for number, item in settled:
        evidence = item.get("evidence")
        grade = evidence.get("grade") if isinstance(evidence, dict) else None
        rows.append("<tr><td><a href=\"#%s\"><code>%s</code></a></td><td>R-%s</td>"
                    "<td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (esc(anchor(item["id"])), esc(item["id"]), esc(number),
                       esc(item.get("by") or "—"),
                       esc(item.get("audit") or "—"),
                       esc(grade or "—")))
    return ('<details class="afk-ledger" id="afk-ledger"><summary>'
            "The decision ledger — %d settled, by whom, on what evidence</summary>"
            '<div class="afk-grid-wrap"><table class="afk-grid"><thead><tr>'
            "<th>Item</th><th>Round</th><th>Decided by</th><th>Audit</th>"
            "<th>Evidence</th></tr></thead><tbody>%s</tbody></table></div>"
            "</details>" % (len(settled), "".join(rows)))


def round_strip(doc):
    """One notch per round, carrying what the round holds.

    The notch labels are counts, not a progress bar: there is no target round
    count to be a fraction of. A session with one round still gets a strip —
    it says the session has one round, which is a fact about the shape.
    """
    rounds = doc["rounds"]
    notches = []
    for rnd in rounds:
        live = [i for i in rnd["items"] if i["state"] != "settled"]
        done = [i for i in rnd["items"] if i["state"] == "settled"]
        groups = (rnd.get("header") or {}).get("groups") or []
        counts = ["%d card%s" % (len(rnd["items"]),
                                 "" if len(rnd["items"]) == 1 else "s")]
        if groups:
            counts.append("%d group%s" % (len(groups), "" if len(groups) == 1 else "s"))
        if rnd["state"] == "current" and live:
            counts.append("%d to answer" % len(live))
        elif done:
            counts.append("%d settled" % len(done))
        notches.append(
            '<li class="afk-notch afk-notch--%s"><a href="#afk-r-%d">'
            '<b>R-%d</b><span>%s</span></a></li>'
            % (rnd["state"], rnd["round"], rnd["round"], esc(" · ".join(counts))))
    return ('<nav class="afk-strip" aria-label="The rounds so far">'
            "<ol>%s</ol></nav>" % "".join(notches))


# --------------------------------------------------------------------------
# round_header — "Where we are", "Before you read", "The fork", next strip
# --------------------------------------------------------------------------

def shape_line(header, cards):
    """Rule 1: what the round holds, before a word of its content.

    Card count, group count, and which groups wait for nothing — the last one
    derived, never authored, because a stale independence claim sends the human
    into a group whose parent is still open.
    """
    groups = header.get("groups") or []
    if not groups:
        return "%d card%s, ungrouped." % (cards, "" if cards == 1 else "s")
    free = schema.independent_groups(groups)
    titles = {g["id"]: g["title"] for g in groups}
    sentence = "%d card%s in %d group%s." % (cards, "" if cards == 1 else "s",
                                             len(groups), "" if len(groups) == 1 else "s")
    if len(free) == len(groups):
        return sentence + " Every group is independent — take them in any order."
    if len(free) > 1:
        sentence += (" Independent of each other, so in any order: %s."
                     % ", ".join(titles[g] for g in free))
    elif len(free) == 1:
        sentence += " Start with %s." % titles[free[0]]
    waiting = [g for g in groups if (g.get("after") or [])]
    if waiting:
        sentence += (" Then %s."
                     % "; ".join("%s, after %s"
                                 % (g["title"], ", ".join(titles[a] for a in g["after"]))
                                 for g in waiting))
    return sentence


def round_header(header, cards=0):
    """The current round's opening block. Not a card: it answers nothing.

    The round number and the card count sit in the section heading — the rail's
    label — so this block says only what the heading cannot.
    """
    parts = ['<p class="afk-shape">%s</p>' % esc(shape_line(header, cards))]
    size_note = header.get("size_note")
    if size_note:
        parts.append('<p class="afk-where">On this round&#x27;s size: %s</p>'
                     % esc(size_note))

    settled = header.get("settled_last_round") or []
    parts.append('<p class="afk-settled-last">Settled last round: %s</p>'
                 % (esc(", ".join(settled)) if settled else "nothing yet"))

    touches = header.get("touches") or []
    if touches:
        parts.append("<h3>Before you read</h3>")
        parts.append(_bullets(
            touches,
            lambda t: "%s — <code>%s</code>" % (esc(t.get("name")), esc(t.get("anchor")))))
    links = header.get("links") or []
    if links:
        parts.append(_bullets(
            links,
            lambda l: '<a href="%s">%s</a>' % (esc(l.get("href")), esc(l.get("label")))))

    parts.append("<h3>The fork</h3><p>%s</p>" % esc(header["fork"]))

    # W-7 next strip: what this round unlocks, what stays parked.
    unlocks = header.get("unlocks") or []
    parked = header.get("parked") or []
    parts.append('<div class="afk-next"><h3>Next</h3>')
    parts.append("<p><b>Unlocks:</b> %s</p>"
                 % (esc(", ".join(unlocks)) if unlocks else "nothing further this round"))
    if parked:
        parts.append("<p><b>Parked:</b> %s</p>" % esc(", ".join(parked)))
    parts.append("</div>")
    return '<div class="afk-round-header">%s</div>' % "".join(parts)


# --------------------------------------------------------------------------
# decided_card — the agent decided; the human audits
# --------------------------------------------------------------------------

def decided_card(item, states=None, level=3):
    """The six contract fields in order, C-4 directly under the heading.

    A reader who reads two lines gets the decision and the why; a reader who
    reads the card can audit it without opening the conversation. `context`
    explains the decision; C-4 still has to say why it beat the named
    runner-up.
    """
    evidence = item["evidence"]
    why = item["why_beat"]
    alternatives = item["alternatives"]
    scope = item["scope"]

    # C-4 and the evidence grade stay in the lede: they are what an audit
    # decides on, so a reader who only scans still sees what the agent leaned
    # on and how hard. The trail behind them is what the disclosure holds.
    lede = ['<p class="afk-why-beat">Beat <b>%s</b>: %s</p>'
            % (esc(why["runner_up_id"]), esc(why["sentence"])),
            '<p class="afk-evidence-line"><b>Evidence (%s):</b> %s <code>%s</code></p>'
            % (esc(evidence["grade"]), esc(evidence["sentence"]), esc(evidence["cite"]))]
    if item.get("provisional_on"):
        lede.append('<p class="afk-prov">Provisional on: %s</p>'
                    % esc(item["provisional_on"]))
    lede.append(deps_strip(item, states))

    detail = []
    if item.get("context"):
        detail.append(prose(item["context"]))
    detail.append(_dl([
        ("Alternatives beaten", _bullets(alternatives, _alt_label)),
        ("Reverse", esc(item["reverse"])),
        ("Scope", "HL: %s · depends-on: %s"
         % (esc(scope.get("hl") or "none"), esc(_depends(scope)))),
    ]))

    tokens = [("accept", "Accept — I audited it"), ("reopen", "Reopen — argue it next round")]
    for alt in alternatives:
        tokens.append(("reverse:%s" % alt.get("id"),
                       "Reverse to %s" % (alt.get("label") or alt.get("id"))))
    answer = choice(item["id"], tokens, "Your audit") + note(item["id"])
    return _card(item, "decided", item["decision"], "".join(lede),
                 "What it beat, how to reverse it, what it touches",
                 "".join(detail), answer, level)


# --------------------------------------------------------------------------
# debate_card — live alternatives, identical criteria rows per option
# --------------------------------------------------------------------------

def debate_card(item, states=None, level=3):
    """Explanation first, then the options.

    `context` is where a cold reader meets the question: the criteria grid
    compares options, which is a different job from explaining what is being
    decided and why it is hard.
    """
    options = item["options"]
    order = item["criteria_order"]
    head = "".join('<th scope="col">%s%s</th>'
                   % (esc(o.get("label") or o.get("id")),
                      ' <span class="afk-rec">recommended</span>'
                      if o.get("id") == item["recommended"] else "")
                   for o in options)
    rows = []
    for criterion in order:
        cells = "".join("<td>%s</td>" % esc((o.get("criteria") or {}).get(criterion, "—"))
                        for o in options)
        rows.append('<tr><th scope="row">%s</th>%s</tr>' % (esc(criterion), cells))
    grid = ('<div class="afk-grid-wrap"><table class="afk-grid">'
            '<thead><tr><th scope="col">Criterion</th>%s</tr></thead>'
            '<tbody>%s</tbody></table></div>' % (head, "".join(rows)))

    # Two sentences carry the whole card for a scanning reader: which option
    # is recommended and why, and why the call is the human's at all. Neither
    # goes behind the disclosure — the second one is the reason they are being
    # asked, and a card that hides it reads as busywork.
    recommended = next((o for o in options if o.get("id") == item["recommended"]), None)
    lede = ['<p class="afk-rec-line"><b>Recommended:</b> %s — %s</p>'
            % (esc((recommended or {}).get("label") or item["recommended"]),
               esc(item["why"])),
            '<p class="afk-undecided"><b>Undecided because:</b> %s</p>'
            % esc(item["undecided_because"]),
            deps_strip(item, states)]

    detail = []
    if item.get("context"):
        detail.append(prose(item["context"]))
    detail.append(grid)
    if item.get("third_paradigm"):
        detail.append('<p class="afk-third">A deliberately different paradigm is on the '
                      'table: <b>%s</b></p>' % esc(item["third_paradigm"]))

    tokens = [(o.get("id"), o.get("label") or o.get("id")) for o in options]
    tokens.append((WRITE_IN, WRITE_IN_LABEL))
    answer = choice(item["id"], tokens, "Your call") + note(item["id"])
    return _card(item, "debate", item["question"], "".join(lede),
                 "The options side by side, on %d criteria" % len(order),
                 "".join(detail), answer, level)


# --------------------------------------------------------------------------
# confirm_row — accept the recommendation, pick an alternative, or write in
# --------------------------------------------------------------------------

def confirm_choice(item):
    """The confirm answer grammar as its one choice control.

    `accept`, one value per `alternatives[]` entry, `write-in` — the tokens
    `LAVISH-KIT.md` "Round response grammar" lists for a `confirm_row`. Both
    layouts of the item call this, so a card and a row offer the same values
    and the composed response cannot depend on which frame drew the question.
    """
    tokens = [("accept", "Accept the recommendation")]
    for alt in item.get("alternatives") or []:
        tokens.append((alt.get("id"), _alt_label(alt)))
    tokens.append((WRITE_IN, WRITE_IN_LABEL))
    return choice(item["id"], tokens, "Your call")


def _degrade_banner(item):
    """The warning a degraded card carries, in either layout.

    Never behind a disclosure: the human is being asked a question the agent
    meant to have decided, and the reason has to reach a reader who opens
    nothing.
    """
    gaps = item.get("degraded_gaps")
    if not gaps:
        return ""
    return ('<p class="afk-degraded">Proposed as a decision, shown as a question: '
            "the card is missing %s, so it is not auditable as decided.</p>"
            % esc(", ".join(gaps)))


def confirm_row(item, states=None, level=3):
    """`context` carries the explanation; `why` argues for the recommendation."""
    lede = []
    banner = _degrade_banner(item)
    if banner:
        lede.append(banner)
    lede.append('<p class="afk-rec-line"><b>Recommended:</b> %s — %s</p>'
                % (esc(item["recommended"]),
                   esc(item["why"]) if item.get("why") else "no reason supplied"))
    lede.append(deps_strip(item, states))

    detail = []
    if item.get("context"):
        detail.append(prose(item["context"]))
    detail.append(_dl([
        ("Evidence", "<code>%s</code>" % esc(item["cite"]) if item.get("cite")
         else "not supplied"),
    ]))

    answer = confirm_choice(item) + note(item["id"])
    return _card(item, "confirm", item["question"], "".join(lede),
                 "Context and the citation behind it", "".join(detail), answer, level)


# --------------------------------------------------------------------------
# confirm_row, laid out as table rows — the same items, one row each
# --------------------------------------------------------------------------

TABLE_COLUMNS = ("Item", "Question", "Recommended", "Your mark", "Note")

TABLE_SUMMARY = "Why this one, the citation behind it, and the alternatives"


def confirm_table(items, states=None):
    """A table group's members, one `<tr>` per item.

    The items stay flat: same objects, same ids, same anchors, same answer
    grammar as the card layout — only the frame changes. A row is the readable
    shape for a group of dozens of one-mark questions, where a card stack
    buries the list.

    Cells carry the scannable facts. `why`, `cite`, `context` and each
    alternative's reason go in a disclosure inside the Question cell, so the
    group stays one row per item at any count and any width. The degrade
    banner and the dependency chips sit in that cell outside the disclosure —
    both are warnings.

    A row carries no heading, so the Item cell is its label. Every other
    `data-afk-*` attribute is the card's, from `item_attrs`.
    """
    head = "".join('<th scope="col">%s</th>' % esc(c) for c in TABLE_COLUMNS)
    rows = []
    for item in items:
        detail = []
        if item.get("context"):
            detail.append(prose(item["context"]))
        detail.append(_dl([
            ("Why this", esc(item["why"]) if item.get("why") else "no reason supplied"),
            ("Evidence", "<code>%s</code>" % esc(item["cite"]) if item.get("cite")
             else "not supplied"),
            ("Alternatives", _bullets(item["alternatives"], _alt_label)
             if item.get("alternatives") else None),
        ]))
        question = ['<p class="afk-row-q">%s</p>' % esc(item["question"]),
                    _degrade_banner(item),
                    deps_strip(item, states),
                    '<details class="afk-detail"><summary>%s</summary>'
                    '<div class="afk-detail-body">%s</div></details>'
                    % (esc(TABLE_SUMMARY), "".join(detail))]
        rows.append(
            '<tr class="afk-row"%s>'
            '<td class="afk-row-id"><code>%s</code></td>'
            "<td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (item_attrs(item, item.get("answerable")), esc(item["id"]),
               "".join(question), esc(item["recommended"]),
               confirm_choice(item), note(item["id"])))
    return ('<div class="afk-grid-wrap"><table class="afk-grid afk-rows">'
            "<thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>"
            % (head, "".join(rows)))


# --------------------------------------------------------------------------
# signoff_packet — the human-locked aspect only they may sign
# --------------------------------------------------------------------------

def _table(table):
    caption = ("<caption>%s</caption>" % esc(table["caption"])
               if table.get("caption") else "")
    head = "".join('<th scope="col">%s</th>' % esc(c) for c in table.get("columns") or [])
    head = "<thead><tr>%s</tr></thead>" % head if head else ""
    rows = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % esc(c) for c in row)
                   for row in table.get("rows") or [])
    return ('<div class="afk-grid-wrap"><table class="afk-grid">%s%s<tbody>%s</tbody>'
            "</table></div>" % (caption, head, rows))


def signoff_packet(item, states=None, level=3):
    """The one card whose detail a signature depends on having been read.

    So its disclosure says what a signature is being given over — the table
    count and the risk count — rather than inviting a signature on a closed
    packet. Nothing here can force the reading; naming the weight is what the
    page can do.
    """
    lede = ['<p><b>Aspect:</b> %s <span class="afk-hl">%s</span></p>'
            % (esc(item["aspect"]), esc(item["hl_id"])),
            '<p class="afk-locked">Yours to sign — the agent may not decide this one.</p>',
            deps_strip(item, states)]

    detail = [_table(t) for t in item["tables"] if isinstance(t, dict)]
    detail.append(_dl([
        ("Alternatives", esc(item["alternatives"])
         if isinstance(item["alternatives"], str) else _bullets(item["alternatives"],
                                                                _alt_label)),
        ("Blast radius", _bullets(item["blast_radius"])),
        ("Risks", _bullets(item["risks"])),
    ]))
    answer = choice(item["id"],
                    [("sign", "Sign it — say so in your own words below"),
                     ("changes", "Changes needed — name them below")],
                    "Your signature") \
        + note(item["id"], "Your own words — this is the signature quote")
    summary = ("The packet — %d table(s), %d risk(s), blast radius"
               % (len([t for t in item["tables"] if isinstance(t, dict)]),
                  len(item["risks"])))
    return _card(item, "signoff", item["aspect"], "".join(lede), summary,
                 "".join(detail), answer, level)


# --------------------------------------------------------------------------
# settled_card — history, collapsed to one line
# --------------------------------------------------------------------------

def settled_card(item, states=None, level=3):
    """History: the heading is the record, the evidence opens on demand."""
    evidence = item["evidence"]
    if isinstance(evidence, dict):
        grade = evidence.get("grade")
        cite = evidence.get("cite")
    else:
        grade, cite = None, evidence
    heading = "R-%s · %s — %s" % (item["round"], item["by"], item["decision"])
    detail = _dl([
        ("Evidence", "%s<code>%s</code>"
         % ("%s: " % esc(grade) if grade else "", esc(cite))),
        ("Audit", esc(item["audit"]) if item.get("audit") else None),
    ])
    return _card(item, "settled", heading, "", "What settled it", detail, "", level)


RENDERERS = {
    "decided_card": decided_card,
    "debate_card": debate_card,
    "confirm_row": confirm_row,
    "signoff_packet": signoff_packet,
    "settled_card": settled_card,
}


def item_states(doc):
    """`{item id: state}` across the whole artifact, for the dependency chips."""
    return {i["id"]: i["state"] for r in doc["rounds"] for i in r["items"]}


def render_item(item, states=None, level=3):
    return RENDERERS[item["component"]](item, states, level)
