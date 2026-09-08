# ROUND.md — the round dossier

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word a
> round puts in front of the human.

The one home for how a grill presents its work: the team works first, then
presents one complete round. Grill skills point here; this file names no
caller.

## The model

A leader does not answer questions from the team one at a time. The team works
independently, decides what it can, records what it cannot and why, and
presents all of it at once. The leader sees the whole picture, approves or
steers, and goes back to their own work.

Three consequences bind everything below.

1. **The work moves to the agent.** Before anything is shown: ground every
   premise, weigh every alternative, decide what the rule below allows, and
   record what could not be decided and why. A question answerable from the
   repository or the specs is a defect, not a courtesy.
2. **One complete presentation per round.** A round is complete when the team
   has taken every decision it legitimately can — not when a page is full and
   not when a count is reached. Round count is an outcome of the dependency
   graph, never a target.
3. **Nothing passes unseen.** Every decision the agent took is accepted
   explicitly, one card at a time, and all of them may sit in the same round —
   so explicitness costs clicks, not turns. Autonomy is bounded by grounding,
   weighed alternatives, and an auditable explanation.

## Item classes

Extends the two classes in [TRIAGE.md](TRIAGE.md), which keeps owning `confirm`
and `debate`.

| Class | Meaning | Human action | Dossier section |
|---|---|---|---|
| `decided` | the agent decided; passes every condition of "The decide rule" and carries the decided-card contract | accept / reopen / reverse | Decided for you |
| `confirm` | TRIAGE.md, unchanged | accept / pick alternative / write-in | Your calls |
| `debate` | the agent's recorded **indecision**: two or more live alternatives, a tie, a one-way door, or an unverifiable premise | pick + note | Your calls, first |
| `locked` | a human-locked aspect packet (`../grill-solution/HUMAN-SIGNOFF.md`) | sign by id, own words | Sign-off, one packet per card |

Misclassification bias is TRIAGE's: in doubt, `debate`. A `debate` card states
**which** condition failed — "in doubt" with no named condition is not a
reason, and a reviewer reads those lines to check the completion test below.

## Before a round — the team works first

Spawn in background, overlapping the conversation, per `DELEGATION.md` (plugin
root):

1. ground every premise the group's questions rest on
   (`../grill-solution/GROUNDING-RULE.md`);
2. pre-fill evidence for every candidate item — TRIAGE.md "Evidence pre-fill",
   widened from `confirm` to every class;
3. build the alternatives set per item, `decided` items included, since the
   human audits the alternatives beaten;
4. take the decision, or decline it and name the failed condition;
5. write the context digest the dossier's "Before you read" section needs.

Assemble the round only when every item in the group carries a taken or
declined decision with its evidence grade. An item whose digest has not
returned waits for the next round — a blank rationale is never presented.

**Completion test.** No item in the round could have been decided by the agent
from evidence it had. Checkable from the page alone: every `debate` card's
`undecided_because` names a condition of the decide rule that genuinely fails.
The failure that hides is a reason technically true but cheap to resolve — a
premise one grep would verify, two alternatives one citation would kill, a
dependency on a `confirm` the agent could have folded in. So the reason also
says what resolving it would have cost and why that cost was not paid.

## Dossier sections

One round is one page section carrying the round's cards, plus one human
response. Ordered content:

1. **Where we are** — the round id, its shape in one line, what settled last
   round, what this round unlocks, and any settled item a steer reopened.
2. **Before you read** — the components this round touches, each with a
   click-through anchor, plus a link to the target repository's own learning
   artifact or design catalog for that area when one exists. The dev reads the
   existing thing before the proposal. Vocabulary rides the tooltip layer
   (`LAVISH.md`), never prose the tooltips already carry.
3. **The fork** — why this round is not obvious: the tension, plainly, as long
   as it needs and no longer.
4. **Decided for you** — one card per `decided` item, every field of the
   decided-card contract plus the audit control.
5. **Your calls** — `debate` first, then `confirm`; options side by side,
   recommendation flagged.
6. **Sign-off** — the `locked` packets whose layer this round closes, verbatim
   tables per `../grill-solution/HUMAN-SIGNOFF.md`, one signature per packet.
7. **What this changes downstream** — which later items depend on this round's
   answers, and what a reversal costs.

The markdown fallback mirrors the same seven as headings, so page and terminal
carry one narrative.

**Narrative order, every round and every card:** context → tension → options →
decision → consequence. No beat skipped; a skipped beat reads as empty rather
than as omitted.

| Beat | Round-level | Card-level |
|---|---|---|
| context | Before you read | "Touches: {components}, called by {callers}" |
| tension | The fork | "Not obvious because: {clause}" / "Undecided because: {condition}" |
| options | the option grid | identical criteria rows per option |
| decision | Decided for you / Your calls | recommendation flagged + evidence grade |
| consequence | What this changes downstream | "If reversed later: {cost clause}" |

## Round shape

Rounds follow the dependency order the grill already imposes. The groups below
are cut points, not quotas: a complex feature takes as many rounds as its graph
has layers, a simple one collapses several groups into one round.

| Grill stage | Natural round groups, in dependency order |
|---|---|
| requirements | pain + actors + scope + candidate terms → stories + access and validation policy + staples + validity walks → devil's-advocate findings + repair paths → residual |
| solution | L1–L2 → L3–L4 → L5–L6 → L7–L8 → L9 seam verdicts; a sign-off packet rides the round that closes its layer, and descent past a layer still waits for its signatures |
| verification | aspects + journeys → API scenarios |

**No caps.** A round holds every item the dependency graph makes answerable
now. An item moves to a later round only because it depends on an answer not
yet given. The aim the grouping tunes for is one sitting; resumability is the
safety net, not the plan.

**Dependencies inside a round.** Each item carries `depends-on: {ids}`. A
`decided` or `confirm` item depending on an open `debate` item in the same
round is marked `provisional` on its card ("holds if Q-2 = A"). When the answer
to the parent differs, re-derive the dependents and present them next round as
`decided` or `confirm` again. This is what replaces waiting for feedback per
question: the wait moves from per node to per round.

## Navigability contract

Removing the caps removes the mechanism that stopped the human drowning, not
the risk. Structure the human can see without reading is the replacement, and
it binds every round.

1. **Shape before content.** The header states how many cards, how many groups,
   and which groups are independent of each other.
2. **Groups in dependency order**, parents before dependents; a dependent names
   its parent and reads `provisional` until the parent is marked. Independent
   groups say so, so the human may take them in any order.
3. **Heading and recommendation visible, detail on demand.** A reader who reads
   only headings knows every decision the round holds.
4. **Marks persist; answer in any order.** A large round survives several
   sittings, and the send refuses while a required mark is missing and names
   the missing cards.
5. **The rail is the map** — current, open, blocked, settled, and a jump to the
   first unmarked card.
6. **Report, never trim.** Say a round is large and why. Deferral is by
   dependency only; an answerable item is never dropped to make a round look
   smaller.

Proportionality is the doctrine, not a number: spend what the case requires —
`../fix/SKILL.md` Phase 2 states it, and this file adds nothing to it.

## Auditing a decided card

One control, three values, plus the note field every card carries:

- `accept` — the explicit audit mark. Required on every decided card, in every
  grill, at every evidence grade.
- `reopen` — becomes `debate` next round; the analysis is kept and extended,
  not redone.
- `reverse:{alternative-id}` — the human takes a listed alternative; apply it
  and re-derive the dependents.

Silence is never agreement. An unmarked decided card is **unanswered**: never
applied, and listed again next round. Explicitness costs clicks, not turns —
every decided card of the group sits in the same round, and marks persist
across sittings. No grade earns a silent pass and no grill is exempt.

**Re-audit strip, one trigger.** The next round opens with a line per decided
card from the sent round that carries no mark: id, decision, citation. Lines
stay until marked. Nothing else is listed there.

A decided item stays visible in the settled history with its audit mark, so a
later round can reopen it by id.

## Steering, and one escape

Two instruments, separate jobs, never merged. A steer changes **what** the
agent decides; the escape changes **whether** it decides.

**Steering** is the normal instrument: guidance ("prefer the async path in this
service"), instructions ("do not touch the billing seam"), references ("read
`docs/x.md` first"). A steer arrives as a note — on a card, or pinned to the
page.

1. A steer on a card binds that card and every dependent: re-derive them under
   the steer and present them next round, `decided` where the steer plus the
   evidence now yield a clear winner, `debate` otherwise.
2. A page-level steer binds the rest of the session for that grill: recorded in
   the grill log's `Open:` row as a `steer:` line so a resumed session honours
   it, and cited as `spec`-grade evidence by every later decision it applies
   to — the human's words are a spec passage.
3. A steer never lowers autonomy by itself. Keep deciding what the new
   constraint allows. A steer that makes a settled item wrong reopens that item
   and says so in the next round's "Where we are".

**The escape** is for the session where steering has stopped working and the
human no longer trusts the agent's decisions. The human writes `take over` as a
line of its own in a round response.

- **Per session.** Nothing is saved, no configuration key, nothing team-wide. A
  new session starts with the agent deciding again.
- **Without disruption.** Settled items stay settled, marks and notes are kept,
  and the round in flight is not discarded. An escape that costs the session
  its state is a restart, not an escape.
- **It hands the whole instrument back.** For the rest of the session the agent
  stops deciding, stops recommending, and the round machinery stands down:
  questions come one at a time, full treatment, per TRIAGE.md. The agent still
  does the work — grounding, alternatives, evidence — it only stops calling the
  result and stops choosing the order.
- **It leaves the locked set alone**, which was never the agent's.

While the escape holds: no card carries a recommendation, so no card needs an
accept and the re-audit strip lists nothing new; the completion test is
suspended, every item being a hand-back by definition; and the grill log's
`Settled:` rows carry no agent-decided tail. Record the escape in the `Open:`
row as `escape: taken R-{n}` so a resumed session honours it.

The escape hands back the very cost the round dossier exists to remove. That is
the right shape for an escape: it is not a mode to sit in, and a session that
needs it often is evidence about the agent, not about the escape.

## A contradicting note

A note that contradicts its own mark — `accept` plus "not sure this holds for
X" — means **nothing wins**. Neither the mark nor the note is applied, and the
item is re-asked next round, differently. The contradiction is evidence the
explanation failed, so the duty is on the agent:

- the re-asked card carries **new** material: evidence the first card did not
  show, or the same argument through a different lens — a before-and-after pair
  instead of prose, a worked path through the code instead of a citation, the
  consequence stated first instead of the decision;
- the note's concern is answered by name on the card ("You asked whether this
  holds for X: …"), so the human sees their words were read;
- a second contradiction on the same item makes it `debate` with the human's
  note as the opening argument, and the agent stops recommending: options side
  by side, and a question.

The same card rendered twice is the failure this rule exists to stop.

## The decide rule

`DECISIONS.md` (plugin root) owns the test. This file adds the grill-time
conditions and the evidence grade, never a second protocol. An item is
`decided` when **all** hold:

1. `DECISIONS.md` condition 1 — reversible on the branch.
2. `DECISIONS.md` condition 2 — one cited sentence beats each alternative. The
   citation's grade is recorded for the auditor; no grade is excluded by rule.
   An item with no citation at all fails this condition.
3. `DECISIONS.md` condition 3 — no human-locked aspect, voids no signature,
   reshapes no plan structure, crosses no caller boundary.
4. Every premise it rests on is `verified` in the claim ledger
   (`../grill-solution/GROUNDING-RULE.md`).
5. It does not depend on an open `debate` item — or it is presented
   `provisional`, still `decided`, re-derived if the parent moves.
6. It contradicts no standing steer. A steer is binding evidence: an item the
   steer settles is `decided` under it; an item the steer forbids is not
   presented.

A failed condition sends the item to `confirm` when its recommendation is
safe-by-default and independent (TRIAGE.md), else to `debate`, and the card
names the condition that failed. Every condition is checkable from the card
alone.

### Evidence grade

No percentages: a number nobody measured is not a number. One grade per card,
so the human knows what kind of checking the accept asks of them.

| Grade | Meaning | What the accept means the human did |
|---|---|---|
| `repo` | `file:line`, registry row, config value, measured fact | clicked through; the line says what the card says |
| `spec` | a quoted PRD / SDD / ADR / glossary passage, or a standing steer | read the passage; it means what the card says |
| `pattern` | a documented house convention cited by path (`CLAUDE.md`, `.claude/rules`, a staples registry) | agreed the convention applies here |
| `judgment` | agent reasoning, no citation | cannot occur on a decided card, by condition 2; on a `confirm` or `debate` card it labels the recommendation honestly |

### Record home

A grill-time decided item is accepted by the human in the round, so the record
is the grill log: the `Settled:` row's tail, grammar owned by
[GRILL-LOG-FORMAT.md](GRILL-LOG-FORMAT.md). A row without an accepted date does
not exist — an unaccepted decision is not settled.

### The decided-card contract

Rationale is a contract, not a style note: the human's condition for letting
the agent decide is that every such decision is surfaced cleanly and
explicitly, with clear rationale. A card is presentable as `decided` only when
it carries **all six** fields. A card missing one **degrades to `confirm`**
before the round is assembled — never silently dropped, never shown as decided
with a gap.

| # | Field | Content | Check |
|---|---|---|---|
| C-1 | Decision | one sentence: the thing that is true from now on | non-empty; one sentence |
| C-2 | Alternatives beaten | every option weighed, one clause each; at least one, and at least two including the third-paradigm option at the top design layers | list length meets the layer's minimum |
| C-3 | Evidence + grade | the cited fact and its grade | citation resolves; grade is `repo`, `spec`, or `pattern` |
| C-4 | Why it beat the runner-up | one sentence naming the runner-up and the criterion that decided it | names an id from C-2 |
| C-5 | Reverse clause | what to revert or rework if the human reverses later | non-empty; one clause |
| C-6 | Scope guard | `HL: none` and `depends-on: {ids or none}` | no locked id; every listed id exists |

The six render in that order, C-1 as the heading and C-4 directly under it, so
a reader who reads two lines has the decision and the why; C-3's citation is a
click-through anchor. The test the six exist to pass: a non-author audits the
card in one read, without opening the conversation. A contradicting note
reports that test as failed.

## Round response

One send per round returns one ordered response. `LAVISH-KIT.md` (plugin root)
owns the grammar and the component contracts; read it there. Fold the page's
composed response and any editor annotations into one round response:

1. composed lines first, page order;
2. each annotation resolves to its enclosing card and is appended after that
   card's line; an unresolvable anchor pins to the page;
3. a side-question leaves the round (`LAVISH.md`);
4. silence never accepts: an unmarked `decided`, `debate`, or `locked` item is
   unanswered, re-asked next round, never defaulted;
5. a note contradicting its own mark applies neither, per "A contradicting
   note";
6. a note phrased as guidance, an instruction, or a reference is a steer,
   applied per "Steering, and one escape".

The markdown fallback carries the same grammar, typed by the human, and its
parser enforces what the page enforces: a response missing a mark on a decided
card is rejected with the ids, never applied in part.

Nothing is dropped. Append the merged response verbatim to the grill log's
`Open:` row until the round is applied, so a crash between poll and apply loses
no human words.
