"""The six phase-1 components.

One function per component, each emitting the markup its row in
`LAVISH-KIT.md` describes. Nothing here decides content: the round JSON is the
content, and this module is the only thing that turns it into HTML.

Every answerable card carries exactly one element with `data-afk-input="choice"`
and exactly one with `data-afk-input="note"` — the attribute contract the inline
runtime composes the round response from. A card's first child is its one-line
heading, so the injected session rail can label it and collapse to it.
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


def _card(item, kind, heading, body, answer):
    """One card. The answer surface exists only inside the current round.

    A card carried over from an earlier round shows its state and nothing to
    mark: an unanswered item is re-asked as a fresh card in a later round, so
    an answer control outside the current section would collect a mark the one
    send never reads.
    """
    attrs = [_attr("data-afk-item", item["id"]), _attr("data-afk-state", item["state"])]
    if item.get("fresh"):
        attrs.append(" data-afk-fresh")
    answerable = item.get("answerable") and answer
    if answerable and schema.required_mark(item):
        attrs.append(' data-afk-required="1"')
    return ('<article class="afk-card afk-card--%s"%s><h3 class="afk-h">%s</h3>%s%s</article>'
            % (kind, "".join(attrs), esc(heading), body,
               '<div class="afk-answer">%s</div>' % answer if answerable else ""))


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


def _depends(scope):
    ids = scope.get("depends_on") or []
    return ", ".join(ids) if ids else "none"


def prose(text):
    """An author's own paragraphs, blank-line separated, escaped."""
    blocks = [b.strip() for b in str(text).split(chr(10) * 2) if b.strip()]
    return "".join('<p class="afk-context">%s</p>' % esc(b) for b in blocks)


# --------------------------------------------------------------------------
# round_header — "Where we are", "Before you read", "The fork", next strip
# --------------------------------------------------------------------------

def round_header(header):
    """The current round's opening block. Not a card: it answers nothing.

    The round number and the card count sit in the section heading — the rail's
    label — so this block says only what the heading cannot.
    """
    parts = []
    size_note = header.get("size_note")
    if size_note:
        parts.append('<p class="afk-where">On this round&#x27;s size: %s</p>'
                     % esc(size_note))

    settled = header.get("settled_last_round") or []
    parts.append('<p class="afk-settled-last">Settled last round: %s</p>'
                 % (esc(", ".join(settled)) if settled else "nothing yet"))

    touches = header.get("touches") or []
    if touches:
        parts.append("<h4>Before you read</h4>")
        parts.append(_bullets(
            touches,
            lambda t: "%s — <code>%s</code>" % (esc(t.get("name")), esc(t.get("anchor")))))
    links = header.get("links") or []
    if links:
        parts.append(_bullets(
            links,
            lambda l: '<a href="%s">%s</a>' % (esc(l.get("href")), esc(l.get("label")))))

    parts.append("<h4>The fork</h4><p>%s</p>" % esc(header["fork"]))

    # W-7 next strip: what this round unlocks, what stays parked.
    unlocks = header.get("unlocks") or []
    parked = header.get("parked") or []
    parts.append('<div class="afk-next"><h4>Next</h4>')
    parts.append("<p><b>Unlocks:</b> %s</p>"
                 % (esc(", ".join(unlocks)) if unlocks else "nothing further this round"))
    if parked:
        parts.append("<p><b>Parked:</b> %s</p>" % esc(", ".join(parked)))
    parts.append("</div>")
    return '<div class="afk-round-header">%s</div>' % "".join(parts)


# --------------------------------------------------------------------------
# decided_card — the agent decided; the human audits
# --------------------------------------------------------------------------

def decided_card(item):
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

    body = ['<p class="afk-why-beat">Beat <b>%s</b>: %s</p>'
            % (esc(why["runner_up_id"]), esc(why["sentence"]))]
    # C-4 keeps the line under the heading — the six-field contract does not
    # move — so the prose body sits behind it and ahead of the audit trail.
    if item.get("context"):
        body.append(prose(item["context"]))
    body.append(_dl([
        ("Alternatives beaten", _bullets(alternatives, _alt_label)),
        ("Evidence (%s)" % esc(evidence["grade"]),
         "%s <code>%s</code>" % (esc(evidence["sentence"]), esc(evidence["cite"]))),
        ("Reverse", esc(item["reverse"])),
        ("Scope", "HL: %s · depends-on: %s"
         % (esc(scope.get("hl") or "none"), esc(_depends(scope)))),
        ("Provisional on", esc(item["provisional_on"]) if item.get("provisional_on") else None),
    ]))

    tokens = [("accept", "Accept — I audited it"), ("reopen", "Reopen — argue it next round")]
    for alt in alternatives:
        tokens.append(("reverse:%s" % alt.get("id"),
                       "Reverse to %s" % (alt.get("label") or alt.get("id"))))
    answer = choice(item["id"], tokens, "Your audit") + note(item["id"])
    return _card(item, "decided", item["decision"], "".join(body), answer)


# --------------------------------------------------------------------------
# debate_card — live alternatives, identical criteria rows per option
# --------------------------------------------------------------------------

def debate_card(item):
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

    body = []
    if item.get("context"):
        body.append(prose(item["context"]))
    body.append(grid)
    body.append("<p><b>Why the recommendation:</b> %s</p>" % esc(item["why"]))
    if item.get("third_paradigm"):
        body.append('<p class="afk-third">A deliberately different paradigm is on the '
                    'table: <b>%s</b></p>' % esc(item["third_paradigm"]))
    if item.get("depends_on"):
        body.append("<p><b>Depends on:</b> %s</p>" % esc(", ".join(item["depends_on"])))

    tokens = [(o.get("id"), o.get("label") or o.get("id")) for o in options]
    tokens.append((WRITE_IN, WRITE_IN_LABEL))
    answer = choice(item["id"], tokens, "Your call") + note(item["id"])
    return _card(item, "debate", item["question"], "".join(body), answer)


# --------------------------------------------------------------------------
# confirm_row — accept the recommendation, pick an alternative, or write in
# --------------------------------------------------------------------------

def confirm_row(item):
    """`context` carries the explanation; `why` argues for the recommendation."""
    body = []
    gaps = item.get("degraded_gaps")
    if gaps:
        body.append('<p class="afk-degraded">Proposed as a decision, shown as a question: '
                    'the card is missing %s, so it is not auditable as decided.</p>'
                    % esc(", ".join(gaps)))
    if item.get("context"):
        body.append(prose(item["context"]))
    body.append(_dl([
        ("Recommendation", esc(item["recommended"])),
        ("Why", esc(item["why"]) if item.get("why") else "not supplied"),
        ("Evidence", "<code>%s</code>" % esc(item["cite"]) if item.get("cite")
         else "not supplied"),
    ]))

    tokens = [("accept", "Accept the recommendation")]
    for alt in item.get("alternatives") or []:
        tokens.append((alt.get("id"), _alt_label(alt)))
    tokens.append((WRITE_IN, WRITE_IN_LABEL))
    answer = choice(item["id"], tokens, "Your call") + note(item["id"])
    return _card(item, "confirm", item["question"], "".join(body), answer)


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


def signoff_packet(item):
    body = ["<p><b>Aspect:</b> %s <span class=\"afk-hl\">%s</span></p>"
            % (esc(item["aspect"]), esc(item["hl_id"]))]
    body.extend(_table(t) for t in item["tables"] if isinstance(t, dict))
    body.append(_dl([
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
    return _card(item, "signoff", item["aspect"], "".join(body), answer)


# --------------------------------------------------------------------------
# settled_card — history, collapsed to one line
# --------------------------------------------------------------------------

def settled_card(item):
    evidence = item["evidence"]
    if isinstance(evidence, dict):
        grade = evidence.get("grade")
        cite = evidence.get("cite")
    else:
        grade, cite = None, evidence
    heading = "R-%s · %s — %s" % (item["round"], item["by"], item["decision"])
    body = _dl([
        ("Evidence", "%s<code>%s</code>"
         % ("%s: " % esc(grade) if grade else "", esc(cite))),
        ("Audit", esc(item["audit"]) if item.get("audit") else None),
    ])
    return _card(item, "settled", heading, body, "")


RENDERERS = {
    "decided_card": decided_card,
    "debate_card": debate_card,
    "confirm_row": confirm_row,
    "signoff_packet": signoff_packet,
    "settled_card": settled_card,
}


def render_item(item):
    return RENDERERS[item["component"]](item)
