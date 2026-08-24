# DECISIONS.md — the hands-off decision protocol

One home for how an agent running hands-off resolves a **decision point** — a fork where specs, contract, findings, or reality disagree and more than one defensible option exists. Skills point here; this file names no caller. A decision point must not stop a run the human would have waved through: the agent decides **two-way doors** itself, on the record; it parks **one-way doors** and **ties** for the human.

## Classify the fork

Weigh the options and form a recommendation exactly as if presenting the choice to a human: the options, the evidence, one winner. Then classify.

**Two-way door — decide, record, continue.** All three must hold:

1. **Reversible on the branch.** Undo is a branch-local edit: revert the commits, rework dependent code written since. Disqualified by effect, not by code: data migration or backfill semantics, a write to an external system, a change to a published contract with existing callers.
2. **A clear winner.** One sentence of cited evidence says why the recommendation beats each alternative — a spec/contract passage, a documented repo pattern, a measured fact. No such sentence → a tie.
3. **Inside agent authority.** The fork touches no human-locked aspect and voids no recorded signature (`skills/afk/grill-solution/HUMAN-SIGNOFF.md`); it reshapes no plan structure (Scope globs, subtask graph, declared `Produces`/`Consumes` seams); it crosses none of the caller's hard boundaries (merge, Jira, branches beyond the feature branch).

**One-way door, or a tie** — any condition fails → the caller's park/ask path. The park report names the fork, the options, and the recommendation, so the human rules in one glance instead of re-deriving the analysis.

## Record every auto-taken decision

An auto-taken decision is a recommendation the human never saw — record it as one they can audit and reverse. Two writes, at decision time:

1. **Ledger** — append an entry to `plan/DECISIONS.md`. Create the file with the header below if missing. Append-only: never edit or delete a prior entry; `{n}` increments per plan. Wording per `LANGUAGE.md` §3.

   ```
   # Decisions — auto-taken hands-off (protocol + grammar: DECISIONS.md, workflow plugin root). Newest last.

   ## D-{n} — {one-line fork}
   - {YYYY-MM-DD} · decided by {skill or gate}
   - Options: {A — one clause} vs {B — one clause}
   - Chosen: {option} — {one-sentence evidence}
   - Supersedes: {quoted SDD §x / ADR-NNNN / contract passage | none}
   - To reverse: {one clause — what to revert or rework}
   ```

2. **Journal** — one `decision(D-{n})` line in `plan/JOURNAL.md` (event grammar: `skills/afk/to-subtasks/JOURNAL-FORMAT.md`).

## Read + report duties

- **Before working a slice**: read `plan/DECISIONS.md` when present. A `Supersedes:` line overrides the exact spec passage it quotes — build on the recorded call; a new fork on the same ground gets a new entry, never an edit.
- **End of run**: the orchestrator's final report lists every `D-{n}` whose journal line falls inside the run's window, each with a ≤6-word gloss (`REPORTING.md` id rule) — the human audits every hands-off decision in one place when the run ends, not mid-run.
- The ledger lives and dies with `plan/` (a run artifact). A decision worth outliving the feature routes through the normal channels — superseding ADR, glossary entry, workflow lesson.

With a human at the keyboard the classification is unchanged; the park path becomes a direct question to them.
