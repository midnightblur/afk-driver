# GRILL-LOG.md format

The checkpoint of a grill, in the spec folder. A row is overwritten as its state changes. Later skills read it. Each grill writes only its own `##` section; this one writes `## Requirements grill`.

## Rows

`grill_log.py` writes every row. A verbatim text is a JSON string, so its line breaks and quotes survive.

| Row | Written by | Grammar |
|-----|-----------|---------|
| Round 0 | `row` | `- Round 0: "<the human's words>"` |
| Ledger | `row` | `- Ledger: <claim> → pending \| verified (<citation>) \| refuted (<citation>) \| unverified-external (human acknowledged)` |
| Term | `term` | `- Term: <term> → pending \| verified (<glossary path>)` |
| Policy | `row` | `- Policy: <actor or story> → permitted <roles>; denied <roles>; scope <slice or unscoped>; validation <rules>` |
| Staples | `row` | `- Staples: none`, or `- Staples: <staple> → in \| out, <reason>` |
| Examples | `row` | `- Examples: <id, case and data of each worked example>` |
| Spinoff | `row` | `- Spinoff: <summary> → <pain>; <why it is out>` |
| Devil | `row` | `- Devil: pass ran; <each finding and how it resolved>` |
| Escape | `row` | `- Escape: taken R<n>` |
| Session | `sync` | `- Session: <id> · page document pages/grill-<id>.json` |
| Settled, by mark | `sync` | `- Settled: <card text> · settled by mark <signal> R<n> · card <id>` |
| Settled, by note | `sync` | `- Settled: <card text> · settled by note R<n> · reading: <reading> · card <id>` |
| Settled, decided card | `sync` | `- Settled: <decision> · decided-by agent R<n> · accepted <date> · <grade>: <evidence> · reverse: <clause> · card <id>` |
| Open | `sync` | `- Open: <card text> · card <id>` |
| Carried | `sync` | `- Carried: <card text> · card <id>`: an older card with a note, returned as a new card |
| Info | `sync` | `- Info: <card text> · card <id>`: an `info` card with a note |
| Owner note | `sync` | `  owner note on <id> (<note id>): "<the human's words>"`, under the row of its card |
| Steer | `sync` | `- Steer: <map node id> (<note id>): "<the human's words>"` |
| Exit gate | `gate` | `- Settled: exit gate passed <date> · session <id>` |

A `sync` overwrites the rows it writes, and removes an exit gate row, because the document moved.

## Exit gate

`gate` checks the mechanical part and lists every failure:

- every `Ledger` row is `verified` or `unverified-external`; no `Term` row is `pending`;
- `Policy`, `Staples`, `Examples` and `Devil` rows exist;
- the current round has an answer; no asking card of it is `open`, `blocked` or `needs_reading`; no returned card waits for a new card.

Before you run it, confirm each judgment check. A miss is one more round.

- Every actor, story, out-of-scope item and non-functional concern is settled.
- Every candidate term surfaced in the session has a human-verified glossary entry.
- Every actor and story has a role policy with a denied role, a data scope and a validation policy.
- Every requirement carries its pain, and every restriction survived its counter-question.
- Every validity change was walked over older records, and each record it can reject has a repair path.
- Every `Devil` finding is resolved or accepted by the human.
