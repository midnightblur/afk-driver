# LAVISH-KIT.md — the kit path

The one home for the deterministic page kit: the round document, the six
components, the skeleton, the two failure modes, the runtime contract and the
**round response grammar**. `LAVISH.md` owns everything else about lavish-axi
and states which pages take this path. This file names no caller skill.

> **Language:** read `LANGUAGE.md` (plugin root) before authoring a round — its
> §1 and §3 bind every string in the document, because every one of them is
> read by a human.

The agent supplies **data**; the script supplies **markup**. No model writes
HTML on this path.

```
python ${AFK_PLUGIN_ROOT}/scripts/lavish_render.py <round.json> [-o <artifact.html>]
python ${AFK_PLUGIN_ROOT}/scripts/lavish_render.py <round.json> --check
```

**A render must be followed by a `lavish-axi` render or poll before a human
looks at the page.** This script writes the artifact file directly, and the
tooltip dictionary and the forced-dark override are injected by hooks that fire
only on a `lavish-axi` command — so a direct write silently strips both, and
nothing in the page, the file, or the transcript says so. Both hooks are
idempotent, so running one when it was not needed costs nothing; skipping one
leaves the human on an un-tooltipped, possibly light page. Details:
`LAVISH.md` "The page runtime lives in the file".

The JSON is the durable state; the artifact is a build product. Append the new
round and patch item states — never rewrite an earlier round. Same document,
byte-identical HTML. Exit `0` rendered, `1` contract violation, `2` unreadable.
A non-zero exit licenses the markdown fallback (`LAVISH.md`), which loses no
work.

## The round document

| Field | Required | Content |
|---|---|---|
| `schema` | yes | `1` |
| `purpose` | yes | what the page is for — the first half of the tab title |
| `feature` | yes | spec-folder tail or ticket id — the second half |
| `rounds[]` | yes | every round so far, oldest first |
| `spec_dir` | no | repo-relative spec folder; emitted as the `afk-spec-dir` meta the tooltip layer reads |
| `stage` | no | which chain stage this session sits in — `requirements`, `design`, `verification`, `plan`, `execution`, `smoke`, `ship`. Lights the process rail; absent, there is no rail |

A round: `round` (positive integer), `state` (`current` or `settled`),
`items[]`, and `header` (a `round_header`, required on the current round).
Exactly one round is `current`.

Every item: `component`, `id` (unique across the artifact), `state`
(`open | blocked | settled`), `fresh` (bool), `group` (a group id, on a grouped
round). `state` and `fresh` default from
placement — items in the current round are `open` and fresh, items in an
earlier round are `settled` — so state them only to override. A settled item is
a `settled_card` and a `settled_card` is settled.

Only the current round's items are answerable. An item still open from an
earlier round shows its state and nothing to mark: a later round re-asks it as
a fresh card, and an answer control outside the current section would collect a
mark the one send never reads.

### Groups

A round groups its cards by the concern they settle. The current round's header
declares them; every answerable card names one:

```json
"groups": [
  {"id": "shape",  "title": "What the thing is"},
  {"id": "wiring", "title": "How it reaches the rest", "after": ["shape"]}
]
```

`layout` says how a group lays its members out: `cards` (the default, and what
an absent field means) or `table`. Any other value is a hard exit.

`after[]` names the groups a group waits for. **List order is render order and
must already be a dependency order** — a group listed before one it comes
`after` is a hard exit, so the renderer never reorders an author's round and the
author sees the cycle instead of a page that quietly fixed it.

Grouping is all-or-nothing per round: declare `groups` and every live card
names one, or declare none and no card carries the field. Half a round grouped
leaves cards in no section, which makes the header's group count stop
describing the page. Both halves are hard exits. A card that degrades keeps its
group — it is the same question in a weaker form.

The **shape line** at the top of the round is derived, never authored: card
count, group count, and which groups wait for nothing. A stale independence
claim would send the human into a group whose parent is still open, so no
author writes it.

Small rounds skip groups. One group per card is grouping that carries no
information.

### Table groups

`layout: "table"` renders the group as one table, one `<tr>` per member. It is
the shape for a group of many questions each needing exactly one mark, where a
card stack buries the list.

**Only a `confirm_row` may sit in a table group** — every other component in
one is a hard exit naming the item and its component. A row holds one question
and one mark, which is the whole of a confirm card; a `decided_card` carries a
six-field contract and a narrative body, so a cell would either truncate the
record or make the row unreadable. A degraded decided card is a `confirm_row`
by the time it is placed, so it lands in the table as a row and carries its
banner there.

Items stay flat: nothing nests inside a container item, and a row carries the
same `data-afk-*` anatomy and the same `afk-i-{item id}` anchor as the card
would. A row has no heading — its Item cell is its label.

| Where | What it holds |
|---|---|
| the cells | Item (the id) · Question · Recommended · Your mark · Note |
| the row's disclosure, inside the Question cell | `why`, `cite`, `context`, each alternative's `why` |
| the row, outside the disclosure | the degrade banner and the dependency chips — both are warnings |

A row's answer grammar is a `confirm_row`'s, unchanged: the tokens are the ones
its line in "Round response grammar" below lists.

## The six components

| Component | Required | Optional | Renders |
|---|---|---|---|
| `round_header` | `round`, `settled_last_round[]`, `unlocks[]`, `fork`, `touches[]` `{name, anchor}` | `target`, `size_note`, `parked[]`, `links[]` `{label, href}`, `groups[]` `{id, title, after[], layout}`, `re_audit[]` | the shape line, the re-audit strip, where we are, what to read first, the fork, the next strip |
| `decided_card` | the six contract fields below | `context`, `provisional_on` | the decision, its audit trail, and the audit control |
| `debate_card` | `question`, `options[]` `{id, label, criteria{}}` (≥2), `criteria_order[]`, `recommended`, `why`, `undecided_because` | `context`, `depends_on[]`, `third_paradigm` | side-by-side options, identical criteria rows, recommendation flagged |
| `confirm_row` | `question`, `recommended`, `why`, `cite` | `context`, `alternatives[]` `{id, label, why}` | one row, accept or override |
| `signoff_packet` | `hl_id`, `aspect`, `tables[]` `{caption, columns[], rows[][]}`, `alternatives` (prose), `blast_radius[]`, `risks[]` | — | the packet only the human may sign |
| `settled_card` | `decision`, `round`, `by` (`human \| agent`), `evidence` | `audit` (`explicit \| silent`) | one heading line, always open |

`criteria_order[]` fixes the row order, and every option answers every
criterion — an option missing one renders `—` rather than a shorter column.

**`context` is the explanation.** Every answerable card the human reads cold
takes one — `decided_card`, `debate_card`, `confirm_row` — with the same shape
and the same reason. The other fields each have a different job: `question` or
`decision` is the heading, `why` argues for the recommendation, criteria cells
compare options against each other. None of them is where a reader learns what
is being decided and why it is hard, so explanation forced into them fights two
jobs at once. Put it in `context`: prose, blank lines separate paragraphs,
escaped like every other string.

**No inline formatting survives.** Every string in the document is escaped, so
backticks, asterisks and underscores render as those characters and markup
renders as visible text. A blank line is the only thing that changes the
rendering, and it starts a paragraph. Write plain sentences; a term that needs
setting apart gets said, not marked up.

**`why` argues both halves.** It says why the recommendation wins and why the
call is the human's rather than the agent's — the second half is what stops a
card reading as a decision already taken. There is no separate field: write both
in the one sentence pair.

`context` sits inside the card's disclosure, ahead of the comparison and the
audit trail. It is the paragraph a cold reader opens the card for — which is
what a disclosure is for — while the lede carries what a scanning reader must
not miss:

| Card | `context` sits |
|---|---|
| `debate_card` | first in the detail block, before the option grid |

`undecided_because` is required on every `debate_card`, and it names the
condition that stopped the agent deciding — the reason lives in
`skills/afk/grill-requirements/ROUND.md`. Required rather than optional
because a round's completion test is read off these lines: an indecision with
no named condition cannot be checked, and "in doubt" is not a condition. It
renders first, so the reader meets the tension before the options.
| `confirm_row` | first in the detail block, before the citation |
| `decided_card` | first in the detail block. C-4 and the evidence grade stay in the lede — the six-field contract does not move, so a two-line read still gives the decision, what it beat, and how hard the evidence is |

A decided card that degrades carries its `context` across: the explanation is
still true when the audit trail is not.

### What the reference fields do

| Field | Behaviour |
|---|---|
| `touches[].anchor` | rendered as code text, never a link — an anchor is `file#symbol`, which no browser resolves from the artifact. Write it for a human to read and search |
| `links[].href` | rendered as an `<a href>` verbatim; a relative path resolves against the artifact's own location. Unverified at render — a wrong path fails only when clicked |
| `depends_on[]` on any card but a decided one | **validated**: every id must name an item in the artifact, and a card may point forward at a later item or a later round. An id naming nothing is a hard exit |
| `scope.depends_on[]` — where a decided card carries its dependencies | **validated** the same way, but as part of C-6: a decided card pointing at nothing degrades rather than failing the render |
| `why_beat.runner_up_id` | validated against that card's own `alternatives[]`, not against the artifact |
| `settled_card.evidence` | free prose, no shape and no validation. It records **what settled the item** — quote the ruling in the words it was given, or name the fact that closed it. A citation is welcome and is not required; a verbatim quote of the human's own words is the strongest form |
| `settled_last_round[]`, `unlocks[]`, `parked[]` | **not validated** — they name what settled, what opens next and what is set aside, which may be outside the artifact entirely |

**A round is as large as what it decides.** Nothing caps the item count, the
word count or the round count, and the renderer truncates nothing and paginates
nothing at any size. `target`, when an author states one, is context on the
heading; `size_note` says why this round is the size it is. Neither is a bound,
and no check enforces either.

### The decided-card contract

Presentation is the guard: the agent may decide, and the price is a card a
non-author can audit in one read without opening the conversation. All six
fields, rendered in this order, `decision` as the heading and `why_beat`
directly under it.

| # | Field | Content |
|---|---|---|
| C-1 | `decision` | one sentence — the thing that is true from now on |
| C-2 | `alternatives[]` | every option weighed: `{id, label, why}`, at least one |
| C-3 | `evidence` | `{grade: repo \| spec \| pattern, cite, sentence}` — the cited fact and what it says |
| C-4 | `why_beat` | `{runner_up_id, sentence}` — one sentence, and the id names a listed alternative |
| C-5 | `reverse` | what to revert or rework if the human reverses later |
| C-6 | `scope` | `{hl, depends_on[]}` — `hl` is `none`, `depends_on` may be `[]` |

## Two failure modes

| Input | Outcome |
|---|---|
| a `decided_card` missing any of C-1…C-6 | **degrades** to a `confirm_row` carrying a banner that names the gaps |
| a `decided_card` with no `decision` | hard exit — nothing to render as anything |
| every other violation | hard exit |

A decided card the human cannot audit must never render as decided, and
dropping it would hide a decision that was taken anyway — so it becomes a
question. The degraded card needs only a non-empty `decision`, which becomes
the question it asks; `why` and `cite` carry across when present and read
"not supplied" when not.

**The document is closed.** Every key is known — on the document, on a round,
on the header, on a card — and an unknown one is a hard exit naming it. A field
the renderer does not read is a field the author believes they wrote: `contex`
would otherwise render a card with no explanation and no complaint, and the
author finds out in front of the human. The one tolerated redundancy is
`component: round_header` on a header, because this file calls it a component;
a header tagged as anything else is refused.

Hard exits: an unknown key at any level, an unknown component, duplicate item
id, no current round or two, a missing or empty required field on any other
component, a `recommended` naming no option, a settled state on a card that is
not a `settled_card`, a `target` that is not a positive integer, a `depends_on`
id naming no item in the artifact, an unknown group `layout`, a component other
than `confirm_row` in a `table` group.

Every hard exit guards auditability or identity. None guards size.

## Skeleton

Fixed order: head (title, `afk-spec-dir` meta, inline tokens and CSS) · **the
process rail** · title · **the round strip** · one answer form containing the
current round and its **sticky send bar** · items still open from earlier
rounds · settled history in round sections, newest round first · the inline
runtime. A round with no answerable item has no answer form.

The **re-audit strip** opens the round when `re_audit[]` names any ids: one
line per decided card that came back from the last send unmarked, because an
unmarked decision is not applied and that is the first thing the round has to
say. Only ids are authored — the decision and the citation are read off the
card the round already presents. Each id must name a live card in the current
round: one naming a settled card would contradict the record, and one naming
nothing would ask for a re-audit of a card the human cannot reach. Both are
hard exits. Nothing else is listed there — one trigger, so the strip stays a
fact about unanswered decisions rather than a second place to put warnings.

The **decision ledger** closes the page: one row per settled decision — item,
round, decided by, audit mark, evidence grade — inside a closed `<details>`.
A row links to its own settled card rather than expanding a copy of it. The
card is the record; a ledger restating the evidence would be a second home for
it, and the two would drift. No settled decision, no ledger.

Both strips sit above the round: the map reads before the detail, and neither
needs opening. The **process rail** is the chain stages with `stage` lit, and
`done` / `upcoming` come from that stage's position in the fixed order — no
author states them, so none can state them wrongly. It carries no links: a
done stage's artifact path is a fact `skills/afk/to-prd/INDEX-FORMAT.md`
already owns, and a second copy would go stale against it. The **round strip**
is one notch per round carrying its card count, its group count and how many
of its cards are still open — counts, not a progress bar, because there is no
target round count for a round to be a fraction of. Every notch lands on a
round section that exists: `afk-r-{n}`, which is why settled history is
sectioned by round rather than flat.

The bar sits in the flow directly under the round it sends, and is `sticky`,
never `fixed`. Two ways a document-end bar disappears: settled history outgrows
the current round, so the bar lands below every settled card; and a host that
sizes its frame to the content height gives `position: fixed` a viewport as
tall as the document, which strands it in the same place. The human then has a
marked card and no way to send it - the one failure that costs the round.

The current round is one element in `data-afk-state="current"` carrying the
round id, with the round's cards nested inside it. Every other card sits
outside it in its own state. That keeps `LAVISH.md`'s page anatomy true — one
current element, the answer surface inside it — while a round asks several
questions at once.

**Three parts per card** (`ROUND.md` navigability rule 3): the heading, the
**lede**, and a `<details>` block holding the rest. What stays in the lede is
what a reader who opens nothing must still see:

| Card | Lede carries |
|---|---|
| `decided_card` | C-4 (`why_beat`) and the evidence grade with its citation — an audit decides on those |
| `debate_card` | the recommendation with `why`, and `undecided_because` — the reason the call is theirs |
| `confirm_row` | the recommendation with `why`, and any degrade banner |
| `signoff_packet` | the aspect, its `hl_id`, and that the agent may not decide it |
| `settled_card` | the heading line is the record; the evidence opens on demand |

Two rules hold the disclosure honest. **The answer surface is a sibling of the
details block, never inside it** — a closed card stays markable, so scanning
and answering are one pass rather than two. And **every summary names what is
behind it**: a disclosure labelled with nothing is a reason not to click, which
turns rule 3 into hidden explanation. A degrade banner and a `provisional`
badge are warnings and never disclose.

Paper has no click. The renderer cannot force a `<details>` open from CSS, so a
printed page keeps the summaries as headings and the markdown fallback is the
record of what they held.

Widgets the renderer draws: the **shape line** (rule 1), the **group sections**
(rule 2), the **disclosure** (rule 3), the **dependency chips** — parent ids as
links plus a `provisional` badge while a parent is unmarked, states read off the
artifact rather than off the card — and the **next strip**, which is `unlocks[]`
plus `parked[]` on the round header. The **state rail** is injected by the hooks
from this anatomy. Chips jump to `afk-i-{item id}`; the prefix is there because
an item id is the author's word and `afk-send` is the page's.

The stylesheet is dark-first and switches on `data-theme="light"`. It does not
follow `prefers-color-scheme`: every render and every poll injects a forced-dark
override that inverts any page it measures as light (`hooks/lavish-dark.sh`), so
a light page on a light-preference machine would be inverted. All CSS and JS are
inlined; the page fetches nothing.

## Runtime contract

The renderer emits the send runtime, so the attribute contract holds by
construction. A hand-authored card carrying the same attributes composes
identically, and gets no kit guarantees.

| # | Guarantee |
|---|---|
| R-1 | one `data-afk-input="choice"` and one `data-afk-input="note"` per `data-afk-item` card inside the current section, both native form controls |
| R-2 | one answer-form submit per round — `queuePrompt(summary, {tag: "choice", data: {round, answers}})` then `sendQueuedPrompts`, never one send per item |
| R-3 | marks and notes persist by session path and item id in `localStorage`; a page revision never changes the key |
| R-4 | the response grammar below, verbatim |

The attribute sits on the radio set's `fieldset`, so a card offers many values
through exactly one choice control. A write-in is a choice value whose text the
human types in that card's note field.

The sticky bar shows a live compact summary and one **Send my answers** submit
button. A successful send shows a visible confirmation. If the lavish bridge
is absent, the same submit copies the response and tells the human to paste it.
The separate copy button uses the same response. Native form controls carry no
`data-lavish-action` attribute.

### Silence

**No card is ever accepted by silence.** Every answerable card carries
`data-afk-required="1"`, whatever it asks and whatever grade of evidence stands
behind it: an item the human never marked is an item they never agreed to, and
a page that reads an unmarked card as a yes manufactures agreement nobody gave.
Explicitness costs a click, not a turn — a round may carry as many cards as it
needs, and one send answers them all.

The runtime names every unmarked card before it sends, and sends on the second
press. It also offers a control that moves the human to the first unmarked card:
with no cap on round size, navigation is what keeps a long round readable, so
the bar names them **and** walks to them — it never shortens the list.

`evidence.grade` stays required on a decided card. It gates nothing now; it is
what lets a reader judge the decision, which is the whole reason a card the
agent decided is allowed to exist at all.

### Round response grammar

**This file is the permanent home of the grammar.** It lives beside its
emitter: the runtime the renderer writes is the only thing that produces it.
Another file may add round semantics around it and points here for the shape.

```
[round R-{n}]
{item-id} {choice-token}                 # marked, no note
{item-id} {choice-token} | {note}        # marked, with a note
{item-id} — | {note}                     # note without a choice
{item-id} —                              # presented, not marked
page — | {note}                          # a note pinned to nothing
[btw] …                                  # side-question, leaves the round
```

One line per answerable card, page order, `—` for no choice; the note follows
` | ` only when it is non-empty. The same grammar serves the markdown fallback,
typed by the human.

| Component | Choice tokens |
|---|---|
| `decided_card` | `accept`, `reopen`, `reverse:{alternative-id}` |
| `debate_card` | each `{option-id}`, `write-in` |
| `confirm_row` | `accept`, each `{alternative-id}`, `write-in` |
| `signoff_packet` | `sign`, `changes` — the note is the human's own words, so it is the signature quote |
