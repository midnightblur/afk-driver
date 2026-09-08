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

A round: `round` (positive integer), `state` (`current` or `settled`),
`items[]`, and `header` (a `round_header`, required on the current round).
Exactly one round is `current`.

Every item: `component`, `id` (unique across the artifact), `state`
(`open | blocked | settled`), `fresh` (bool). `state` and `fresh` default from
placement — items in the current round are `open` and fresh, items in an
earlier round are `settled` — so state them only to override. A settled item is
a `settled_card` and a `settled_card` is settled.

Only the current round's items are answerable. An item still open from an
earlier round shows its state and nothing to mark: a later round re-asks it as
a fresh card, and an answer control outside the current section would collect a
mark the one send never reads.

## The six components

| Component | Required | Optional | Renders |
|---|---|---|---|
| `round_header` | `round`, `settled_last_round[]`, `unlocks[]`, `fork`, `touches[]` `{name, anchor}` | `target`, `size_note`, `parked[]`, `links[]` `{label, href}` | where we are, what to read first, the fork, the next strip |
| `decided_card` | the six contract fields below | `context`, `provisional_on` | the decision, its audit trail, and the audit control |
| `debate_card` | `question`, `options[]` `{id, label, criteria{}}` (≥2), `criteria_order[]`, `recommended`, `why` | `context`, `depends_on[]`, `third_paradigm` | side-by-side options, identical criteria rows, recommendation flagged |
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

Placement is early, ahead of the comparison and the audit trail:

| Card | `context` sits |
|---|---|
| `debate_card` | under the heading, before the options |
| `confirm_row` | under the heading, before the recommendation |
| `decided_card` | under C-4, which keeps its own line directly under the heading — the six-field contract does not move, so a two-line read still gives the decision and why it beat the runner-up |

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
| C-3 | `evidence` | `{grade: repo \| spec, cite, sentence}` — the cited fact and what it says |
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
id naming no item in the artifact.

Every hard exit guards auditability or identity. None guards size.

## Skeleton

Fixed order: head (title, `afk-spec-dir` meta, inline tokens and CSS) · the
current round · items still open from earlier rounds · settled history, newest
first · the sticky send bar · the inline runtime.

The current round is one element in `data-afk-state="current"` carrying the
round id, with the round's cards nested inside it. Every other card sits
outside it in its own state. That keeps `LAVISH.md`'s page anatomy true — one
current element, the answer surface inside it — while a round asks several
questions at once.

**Nothing collapses.** Every card renders open, at any round size and on any
screen, and no control folds one away. A settled card is short because it is
written short — one heading line — not because anything hid the rest of it. So
a long round is long, and the send bar's jump control is the whole of the
navigation.

Phase-1 widgets: the **state rail**, injected by the hooks from this anatomy,
and the **next strip**, which is `unlocks[]` plus `parked[]` on the round
header. The renderer draws no navigation chrome of its own.

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
| R-2 | one send per round — a single `queuePrompt` plus `sendQueuedPrompts`, never one per item |
| R-3 | marks and notes persist per item id in `localStorage`, surviving reload and session end |
| R-4 | the response grammar below, verbatim |

The attribute sits on the radio set's `fieldset`, so a card offers many values
through exactly one choice control. A write-in is a choice value whose text the
human types in that card's note field.

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
