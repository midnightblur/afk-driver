# Validation checklist

Checks (a) graph, (b) anchors, (e) tiers, (g) gate shape are **mechanical** —
run the validator, fix every finding, re-run until clean:

```
python3 skills/afk/to-subtasks/scripts/validate_plan.py {plan-dir}   # Windows: py -3
```

Exit 0 = clean · 1 = findings (one line each: file + rule id + detail) · 2 =
the plan didn't parse (fix the emitted files, not the script). The script's
header docstring is the canonical doc — the owning home of the contract-graph
(a), anchor-quality (b), tier-mandate (e), and gate-shape (g) rules, incl. the
forbidden-generic-token list and the Scope-glob → mandated-tier table.

Two (b)/(e) obligations stay with the emitter, beyond the script:

- A `[materialized]` bullet's stub module must `test-compile` (Process step 3.5).
- Every `## Verification` command must be runnable from repo root, and every
  runtime-effect Acceptance bullet ("within N seconds", live/watch/poll/
  reactive) must map to a unit/integration row that triggers the condition and
  asserts the outcome (rule: SKILL.md "Choosing verification tiers"). Tier
  mandates are hard downstream (no-waiver rule: the execute contract's "Driven
  mode" section); the script only guarantees the rows exist.

Checks (c), (d), (f) are judgment:

**(c) Acceptance citations.** Every cited bullet ends with `(PRD §…)` / `(SDD
§…)` / `(SDD §9b row "…")` / `(ADR-NNNN)`, and the citation **resolves** (grep
the target file — a phantom citation is worse than none). At least one bullet
cites the SDD §8 module row this subtask owns.

**(d) Seam coverage.** Every SDD §9b seam appears in the seam register with a
named implementer; the implementing subtask lists it `implement:` in `## Seams`
and carries its seam-test as a Verification row asserting on the framework's
real output. A seam sliced without that test fails the slice — the gap green
unit tests hide. Every `use:` seam points at a real register row. A
**materialized** seam's pre-created `{Seam}ContractTest` must be the
implementer's seam-test row (enabling + greening it is that subtask's job —
don't emit a second, parallel seam-test).

**(f) Scope sanity.** Globs are concrete (no bare `**`), and the union of all
subtask Scopes covers the PRD's stated work with no silent gap.
