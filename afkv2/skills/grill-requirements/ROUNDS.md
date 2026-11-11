# Grill rounds

The rules for what goes on a round. How the page lays it out: `/afkv2:use-lavish`. How a signal settles: the round pass in `../use-lavish/ROUND-PASS.md`.

## What to find

Walk the requirement tree in dependency order. A round is complete when you took every decision you legitimately can, not when a count is reached.

| Round group, in order | Holds |
|-----------------------|-------|
| 1 | the pain, actors, scope, candidate terms |
| 2 | stories, access and validation policy, staples, validity walks, worked examples |
| 3 | devil's-advocate findings, repair paths |
| 4 | what remains |

A simple ticket folds several groups into one round. An item waits for a later round only when it depends on an answer not yet given.

- **Pain.** Every requirement records the pain it removes in one sentence. A requirement with no pain gets challenged.
- **Restrictions.** On every "only", "never" or "must not", ask: what legitimate scenario does this block, and how does the user recover?
- **Validity walks.** When a rule changes what is valid, walk the records made before the change. Every record the rule can reject needs a named repair path that its role can reach.
- **Access and validation policy.** For every actor and story: the permitted roles and at least one denied role; which data this actor sees only a slice of, or "unscoped"; the rules on inputs and on workflow moves. Write one `Policy` row each.
- **Worked examples.** One frequent, one edge and one risky use case, from starting data to result, with sample data when the feature makes data, and at least 1 for every story. Write each as an entry of `examples`, and one `Examples` row.
- **Terms.** Scan every statement for words 2 people could read differently. Draft your own definition, and put it on a `confirm` card. An item that rests on an unverified term waits.
- **Staples.** With a `STAPLES.md`: each active staple whose trigger matches gets an in or out call with a reason, on a `confirm` card. With none: write `Staples: none`.
- **Spinoffs.** Real work outside this ticket gets a `Spinoff` row, not a requirement.
- **Decisions.** A requirement that is hard to reverse, surprising without context and a real trade-off: state it on its card. The next skill records it.

## The session's content

The page document holds the whole topic, with or without a page shown. Each round sends only the entries that changed, by "Sections and change lines" of `/afkv2:use-lavish`.

| List | Holds |
|------|-------|
| `sections` | 1 entry per part of the topic: its `title`, its `state` (`not_reached` until a question or a note reaches it, then `current`), its current text in `body`, and the sections it depends on in `links`. A merge or a removal: "Sections and change lines" of `/afkv2:use-lavish` |
| `stories` | 1 entry per user story, its `text` in 1 sentence |
| `examples` | each worked example: its `title`, its `kind` (frequent, edge or risky), the `stories` it covers, and its starting data and result in `body` |
| `questions` | the questions for others, in the order to ask them, each with its parts, its `origin` and its `state` (below) |

Each entry you send carries an `id`. Give a new entry a new `id`, unique in its list, and never reuse one.

A card names the section it asks about in `section`.

### Questions for others

A question for others is a point that neither the developer nor the code can settle. It is an entry of `questions`, written for a person outside the session. It joins the list in 2 ways:

- A note says the developer cannot answer, or names who would: add the question in the next round, with `state: open` and `origin: {note: <note id>}`.
- You find a point only someone else can answer: propose it on a `confirm` card that shows the question with its parts. Add it to `questions` only after the developer accepts that card, with `state: open` and `origin: {card: <card id>}`. A proposal card that stays open or gets another mark adds nothing.

Write each required part, and each other part that applies:

| Field | Part |
|-------|------|
| `who` | who to ask: 1 or more roles (product owner, tester, director, another team), or `everyone`; always required |
| `question` | 1 sentence the person can answer; always required |
| `context` | what the feature is about, only as much as the question needs; always required |
| `why` | what waits on the answer, and what goes wrong on a guess; always required |
| `ways` | the options, when there are any, in plain words; a recommendation only when the developer wants one shown |
| `choices` | the known answers to tick, when the answer is 1 or several of a few: `{options, several}`; `options` holds 2 to 12 options, each with an `id` and the `text` shown; `several` is `true` when more than 1 may be ticked, else `false` |
| `example` | a small case with sample data, when the point is complex |
| `links` | the sections that help the discussion |
| `waits_on` | the question it waits on |

The text names no internal decision, no plan term and no id: a person who never saw the session reads it. Explain a term this session made up where it first appears.

The order of the questions: "The questions block" of `/afkv2:use-lavish`. To place a follow-up, send it with `after`. A note that moves a question: send the question again with `after`. The new order holds from the next round on.

An answer, a drop and an assumption are readings of the round pass: `answer`, `drop` and `assume` in [../use-lavish/ROUND-PASS.md](../use-lavish/ROUND-PASS.md). In the round after an answer, answer rule AR-08 of `/afkv2:use-lavish` and the `answer` reading apply: give each point it touches a `confirm` card. A question that waits on a person past the end: propose an assumed answer on a `confirm` card. The developer's accept is the `assume`. A section that the assumed answer changes takes a change line with cause `answer` and the accepted `card`. A question drops only on the developer's note with a reason.

**As text.** When the developer asks for the questions as text, print the open questions for others as Markdown in chat: in list order; with a role named, only the questions whose `who` holds that role or `everyone`; each with every part it holds, 1 labelled line or block per part. No ids: a link names its section by title, and a wait names its question by its sentence.

## Claim ledger

A claim is any statement of how something works now: behaviour, a constraint, an ownership boundary. It may come from the ticket, from the human or from you. Verify it before anything settles on it: a subagent reads the code with `rg --hidden -g '!.git' PATTERN PATH` and returns `path:line`. Write one `Ledger` row per load-bearing claim.

| Status | Meaning |
|--------|---------|
| `pending` | the check runs; nothing settles on this row |
| `verified (<citation>)` | the code says so |
| `refuted (<citation>)` | the code says otherwise: name the contradiction in the next round, correct the requirement, and write the row again as `verified` against the actual behaviour |
| `unverified-external (human acknowledged)` | a system outside this repository, and the human accepted that on a card |

## Card kinds

| Kind | Use it when |
|------|-------------|
| `debate` | 2 or more live options, a tie, a one-way door, or a premise you cannot verify; the body names which condition failed and what resolving it would have cost |
| `confirm` | your recommendation is safe by default and independent of every open point; the human only accepts or overrides |
| `decided` | you decided, and the human audits it |
| `info` | context the human needs; it asks nothing |

In doubt, use `debate`. Silence never accepts: an unmarked card stays open and returns next round. A card that depends on an open `debate` card says "holds if <id> = <option>" and is derived again when the answer differs.

## The decide rule

A card is `decided` only when all hold:

1. The branch can undo it at low cost.
2. One cited sentence beats each option.
3. It touches no human-locked aspect, voids no signature, and crosses no boundary of another team.
4. Every premise it rests on is `verified` in the ledger.
5. It depends on no open `debate` card, or it says "holds if".
6. It contradicts no steer.

A failed condition makes it `confirm` when safe by default and independent, else `debate`.

The 6 fields of `decided` in the round input:

| Field | Content |
|-------|---------|
| `decision` | one sentence: what is true from now on |
| `why` | one sentence: the runner-up, and the criterion that beat it |
| `alternatives` | each option weighed, one clause each; at least 1 |
| `evidence`, `grade` | the cited fact; the grade below |
| `reverse` | what to revert if the human reverses it later |
| `depends_on` | card ids, or an empty list |

| Grade | Meaning | What an accept means the human did |
|-------|---------|------------------------------------|
| `repo` | `path:line` or a measured fact | checked the line |
| `spec` | a quoted requirement, or a steer | read the passage |
| `pattern` | a house rule cited by path | agreed that it applies |

A recommendation with no citation is a judgment. It goes on a `confirm` or `debate` card, labelled as a judgment.

## Read each note

Read each note for every meaning it holds. One note can hold several: an answer to its card, a thought about another part, a new idea, a point the developer cannot answer, guidance for the whole session. Act on each meaning in the next round:

| Meaning | Next round |
|---------|-----------|
| an answer to its card | the reading of the round pass |
| a thought about another part, or a new idea | a change to that part's section, or a new section, with a change line of cause `note` |
| the developer cannot answer, or names who would | a question for others ("Questions for others") |
| guidance for the whole session | a steer ("Steers and the escape") |

A thought on a section that no question reached yet is the developer's lean: the section records it as a lean, not as settled, and the card of that part starts from it. The reply to the note states each reading (answer rule AR-05 of `/afkv2:use-lavish`).

## A note that contradicts its mark

An `accept` with "not sure this holds for X" applies neither. Ask the point again in the next round with new material: evidence the first card did not show, or the same argument through a different lens. Answer the note's concern by name on the card. A second contradiction makes it `debate` with the human's note as the opening argument, and no recommendation.

## Steers and the escape

A note on a map node, or a note that gives guidance for the whole session, is a steer. Write it to the log word for word. It binds every later decision it applies to, and you cite it with grade `spec`. A steer that makes a settled point wrong returns that point, and the next banner says so. Keep deciding what the steer allows.

The human writes `take over` on its own line: write an `Escape` row, `taken R<n>`. For the rest of the session, stop deciding and stop recommending: one question per round, with no `decided` card. You still do the work: claims, options, evidence. Settled points stay settled. The escape ends with the session.

## Without a page

When `present` refuses at `show`, or the developer asks to work without a page, the grill asks round by round in chat from the same files. `build` still runs each round and writes the round into the page document. `ingest` and `apply-readings` read the answer, and the log and the end check give the same verdict as with a page.

After a refusal at `show`, `present` already checked and rendered the round and scanned the page and the log for secrets. When the developer asked for chat, run `present` with `--no-show`. A `show` opens the page, and on Codex the Stop hook then waits up to 1 hour for a send from the page:

```sh
<python> "<this skill's folder>/../use-lavish/scripts/page_round.py" present --no-show --doc "<doc>" --scan "<log>"
```

Handle a refusal and report the notices as for `present` in step 5 of [SKILL.md](SKILL.md).

- Ask the round in 1 chat message: each asking card as a numbered question with only the context it needs: the verdict or the options, the evidence, and the section it asks about. No ids.
- Ask each open question for others in the same message, with its parts and its choices numbered, by "As text".
- Write the developer's reply to `raw_file` as the send the page would make, in the grammar of `engine/prompt_lines.py` (plugin root). The first line is `[round R-<n>]`. Each number becomes its card id. A mark is a line `<card id> <mark>`, with a mark word of the card's kind from `MARKS` in `engine/ingest.py`; an option of a `debate` card is its letter. Each note is its own entry. A choice of a question for others is a line `<question id> tick <option id>`, with each picked option id; any other answer is a note on the question. Then go to step 7 of [SKILL.md](SKILL.md).

## Coming back

A grill that came back continues its finished page with the new input. A settled point stays settled unless the new input touches it; a touched point returns as a new card with `carries`. The grill ends only after its end check passes again.

Every pass of `gate` answers `stale` and `changed`. A list is empty when it has nothing. Tell the developer each list that is not empty:

- `stale`: each later document of the ticket that exists. Name each one as possibly out of date, with the skill that writes it again: `PRD.md` and `adr/requirements/` by `/afkv2:to-prd`, `SDD.md` and `adr/design/` by `/afkv2:propose-solution`, the plan (`plan/PLAN.md` on the run branch) by `/afkv2:to-subtasks`.
- `changed`: each settled point that changed after the round of the last passed end check, by its `text`.

## Devil's-advocate pass

When the tree looks exhausted, run the devil pass on the other provider. It reads only `GRILL-LOG.md`, not this conversation, and attacks it. `--session` is the provider of this session, `claude` or `codex`:

```sh
<python> "<this skill's folder>/../../scripts/other_provider.py" attack --log "<log>" --session <provider>
```

Show each finding of `findings` as a card of the last round, with its `kind`, `what` and `where`. Write a `Devil` row when each one is resolved or accepted, and name `provider` and `model` of the answer in it. A refusal (`no-provider`, `judge-timeout`, `judge-unreadable`): tell the developer its `reason`, and ask whether to run the pass again or to go on without it. Write the answer and the code in a `Devil` row.
