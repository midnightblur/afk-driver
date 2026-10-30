# Doors

A fork is a point where the specs, the contract, a finding or the facts disagree, and more than one option can be defended. Weigh the options as for a human: the options, the evidence, one winner.

A fork is a **two-way door** when all 3 of these hold:

1. Undo is a branch-local edit. A data migration, a write to an external system and a change to a published contract with callers fail this test.
2. One sentence of cited evidence shows why the winner beats each other option. A contract passage, a spec passage, a repository pattern or a measured fact counts.
3. The fork stays inside agent authority. It changes no human sign-off, no plan structure (Scope, subtask order, `## Produces`, `## Consumes`), no merge and no branch outside this run.

Any other fork is a **one-way door** or a tie: it parks for a human.

| Verb of `walk.py` | Use |
|-------------------|-----|
| `decide` | a two-way door: `fork`, `options`, `chosen`, `evidence`, `reverse`; optional `supersedes` (the passage it overrides, quoted) |
| `park` | a one-way door or a tie: `reason`, `fork`, `options`, `recommendation` |

Each verb writes the decision ledger (`plan/DECISIONS.md`) and the journal (`plan/JOURNAL.md`), and commits them on the run branch. `park` also blocks every dependent subtask, and its ledger entry is the record that retro reads.
