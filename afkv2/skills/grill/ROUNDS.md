# Grill rounds

The rules for what goes on a round. How it looks: the page guide. How a signal settles: the round pass in `../visualize/components/card.md`.

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
- **Worked examples.** One frequent, one edge and one risky use case, from starting data to result, with sample data when the feature makes data. Write one `Examples` row.
- **Terms.** Scan every statement for words 2 people could read differently. Draft your own definition, and put it on a `confirm` card. An item that rests on an unverified term waits.
- **Staples.** With a `STAPLES.md`: each active staple whose trigger matches gets an in or out call with a reason, on a `confirm` card. With none: write `Staples: none`.
- **Spinoffs.** Real work outside this ticket gets a `Spinoff` row, not a requirement.
- **Decisions.** A requirement that is hard to reverse, surprising without context and a real trade-off: state it on its card. The next skill records it.

## Claim ledger

A claim is any statement of how something works now: behaviour, a constraint, an ownership boundary. It may come from the ticket, from the human or from you. Verify it before anything settles on it: a subagent reads the code with `rg --hidden -g '!.git' PATTERN PATH` and returns `path:line`. Write one `Ledger` row per load-bearing claim.

| Status | Meaning |
|--------|---------|
| `pending` | the check runs; nothing settles on this row |
| `verified (<citation>)` | the code says so |
| `refuted (<citation>)` | the code says otherwise: name the contradiction in the next round, correct the requirement, and write the row again as `verified` against the actual behaviour |
| `unverified-external (human acknowledged)` | a system outside this repository, and the human accepted that on a card |

## Card kinds

| Kind | Use it when | Page section order |
|------|-------------|--------------------|
| `debate` | 2 or more live options, a tie, a one-way door, or a premise you cannot verify; the body names which condition failed and what resolving it would have cost | first |
| `confirm` | your recommendation is safe by default and independent of every open point; the human only accepts or overrides | second |
| `decided` | you decided, and the human audits it | third |
| `info` | context the human needs; it asks nothing | last |

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

## A note that contradicts its mark

An `accept` with "not sure this holds for X" applies neither. Ask the point again in the next round with new material: evidence the first card did not show, or the same argument through a different lens. Answer the note's concern by name on the card. A second contradiction makes it `debate` with the human's note as the opening argument, and no recommendation.

## Steers and the escape

A note on a map node, or a note that gives guidance for the whole session, is a steer. Write it to the log word for word. It binds every later decision it applies to, and you cite it with grade `spec`. A steer that makes a settled point wrong returns that point, and the next banner says so. Keep deciding what the steer allows.

The human writes `take over` on its own line: write an `Escape` row, `taken R<n>`. For the rest of the session, stop deciding and stop recommending: one question per round, with no `decided` card. You still do the work: claims, options, evidence. Settled points stay settled. The escape ends with the session.

## Devil's-advocate pass

When the tree looks exhausted, start one fresh subagent. Give it the settled requirements, pains, restrictions and ledger from `GRILL-LOG.md`, not this conversation. Its brief: attack. Which requirement treats a symptom, which restriction blocks a legitimate scenario, which 2 requirements conflict, what nearby pain stays open. Show its findings as the last round. Write a `Devil` row when each one is resolved or accepted.
