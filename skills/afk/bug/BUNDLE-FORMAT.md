# Bundle format — `bundle.md`

The **one home** for the evidence-bundle grammar: the confidence labels every
fact carries, the repro section, and the capture-context fields. The bundle is
the durable, human-readable dossier that makes a bug diagnosable long after the
session that found it ended. It lives beside `state.json` in the bug directory
(layout: [LEDGER-FORMAT.md](LEDGER-FORMAT.md)).

A bundle is markdown with the sections below. It is written once at capture and
is read-mostly thereafter; a later evidence addition appends, preserving what
was captured.

## Mandatory rules

- **Every fact carries a confidence label** (Catalog B) — no unlabelled
  assertion. A reader must be able to tell an observation from a hunch at a
  glance.
- **Repro is not optional.** The bundle contains either concrete repro steps OR
  an explicit `could-not-reproduce` reason. A bundle with neither is invalid —
  capture refuses it.
- **Capture context is recorded**: the branch the bug was found on and its
  dirty-state (clean, or which files were uncommitted). A fix may only reproduce
  with the dev's work-in-progress present; without this, the fixer can't tell.

## Confidence labels (Catalog B)

The single authoritative copy of PRD Catalog B. Every fact in the bundle is
tagged with exactly one.

| ID | Label | Meaning |
|----|-------|---------|
| C1 | `verified` | Observed directly; proof attached (command output, screenshot) |
| C2 | `inferred` | Concluded from evidence, not directly observed |
| C3 | `guessed` | Plausible hypothesis, unchecked |

- A `verified` fact SHOULD point at its proof — an inline command/output block
  or a `screenshots/<file>` reference (the `screenshots/` dir is defined in
  [LEDGER-FORMAT.md](LEDGER-FORMAT.md)).

## Section grammar

```
# Bug: {one-line title}

## Capture context
- Branch: {branch the bug was found on}
- Dirty state: {clean | list of uncommitted/WIP files}
- Found: {YYYY-MM-DD HH:mm}

## Summary
{one short paragraph — what's wrong, tagged facts}

## Facts
- [{C1|C2|C3}] {fact} {optional proof: inline block or screenshots/<file>}
- ...

## Reproduction
{numbered concrete steps}
--- OR ---
## Could not reproduce
{explicit reason — e.g. only observed once, environment-specific, timing}

## Suspected cause            (optional)
- [{C2|C3}] {hypothesis}
```

- Exactly one of `## Reproduction` / `## Could not reproduce` is present.
- `## Suspected cause` facts are `inferred` or `guessed` by nature — never
  `verified` (a verified cause belongs in `## Facts`).

### Hypothetical bundle

```
# Bug: export CSV drops the last row when the grid is filtered

## Capture context
- Branch: kapteyn/development/dev/export-tuning
- Dirty state: 2 uncommitted files (ExportService.java, grid-store.ts)
- Found: 2026-01-10 14:30

## Summary
Filtered CSV export is off-by-one: [C1] the last visible row is missing from the
file, while [C2] the on-screen count is correct.

## Facts
- [C1] 41 rows shown, 40 rows in the CSV — see screenshots/grid-vs-csv.png
- [C1] Unfiltered export is complete (100/100 rows)
- [C2] The filtered row set is sliced before the writer sees it

## Reproduction
1. Open the invoice grid, apply any filter yielding > 1 row.
2. Export to CSV.
3. Compare the last visible row against the file's last line.

## Suspected cause
- [C3] An exclusive upper bound in the filtered-range copy
```
