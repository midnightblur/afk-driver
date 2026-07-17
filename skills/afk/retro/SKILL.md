---
name: retro
description: Cross-feature retrospective of the workflow itself — mines delivered plans' journals, review rollups, adversary reports, grill logs, park reasons, and the harness gate-latency metrics into systemic signals plus evidence-cited improvement proposals written as concrete plugin edits. Use when the user runs `/afk:retro` after features ship or on a periodic cadence.
---

# afk:retro — make the workflow learn from its own exhaust

Every run of the chain leaves structured exhaust: journal events, park reasons, review findings by class, adversary verdicts, remediation-cycle counts, gate latencies. Per-bug that exhaust is already consumed (escape analysis inside `/afk:fix`); nobody consumes it *across* features. This skill does: aggregates the exhaust of N delivered features into systemic signals — what the chain keeps getting wrong, where it stalls, what it costs — and turns the strongest into concrete, evidence-cited proposals to change the plugin. The systemic counterpart of the per-bug escape analysis.

**Read-only over everything it mines, including this plugin.** Writes exactly one artifact: its own retro report. Proposals are applied by a human (or a task the human cuts) — never by this skill.

## Argument

One or more of: a specs release folder (e.g. `{service}/src/main/resources/specs/{year}r{release}/`), individual ticket spec folders, or ticket ids to resolve. Default: newest release folder of the service in cwd. Optional `since:{YYYY-MM-DD}` filters journal events by date.

## What it mines (all read-only)

Locate every in-scope feature with a `plan/` dir; skip those without one (nothing ran). Per feature:

| Source | Extract |
|---|---|
| `plan/JOURNAL.md` | event lines (grammar: `skills/afk/to-subtasks/JOURNAL-FORMAT.md`): parks + reasons, stranded rows, heartbeat cadence, first→last timestamp (wall-clock), review/adversary/smoke verdict lines, re-review counts per subtask (remediation cycles) |
| `plan/PLAN.md` | subtask count, final Status column distribution, smoke-gate shape (full/minimal) + result |
| `plan/review/INDEX.md` + `*.findings.json` | finding counts by `class` and `severity`, open advisories, verdict per subtask |
| `plan/review/*.findings.json` × `*.outcomes.json` | per-`criterion` outcome rates — fixed vs dismissed vs deferred, joined on finding id |
| `plan/review/PATTERN-DEBT.md` | baseline↔repo-pattern conflicts: criterion + overriding rule per row |
| `plan/review/*-adversary.md` | adversary verdicts + finding classes |
| `GRILL-LOG.md` | which decisions were settled at grill time (to correlate: did downstream failures trace to a gap a grill should have caught?) |
| repo `.claude/metrics/gate-latency.jsonl` | gate p50/p95, red rates, `lock_wait_ms` share — summarize via `bash tools/payable/ai-agents/plugins/workflow/hooks/gate-metrics-report.sh` |
| repo `.claude/wiring-ious.md` | open IOUs and their age (consumers that never arrived) |
| main-checkout `.claude/lessons/LEDGER.jsonl` | per-lesson status trail (fold via `bash tools/payable/ai-agents/plugins/workflow/hooks/lesson-digest.sh --all`; grammar: `skills/afk/lessons/LEDGER-FORMAT.md`): open-lesson age, `applied` lessons whose class/target recurs |

Bulk reads are delegated per `DELEGATION.md` (plugin root): one subagent per feature returns the per-feature digest (the §1 table row data plus its raw signal lists); the orchestrator only aggregates and judges.

## Analysis — signals, not anecdotes

Aggregate across features, then rank. A signal needs **≥2 independent occurrences** (different features, or different subtasks of one feature) — a single incident belongs to `/afk:fix`'s escape analysis, not a retro. The signal families:

1. **Recurring finding classes** — which review/adversary `class`+concern combinations keep appearing. A class recurring across features means the *executor's* doctrine (or a target-repo CLAUDE.md rule) has a hole — caught downstream of where it should be prevented.
2. **Park patterns** — which outcome statuses recur (`contract_mismatch`, `produces_drift`, `review_fail`…), on what kind of subtask. Recurring `contract_mismatch` implicates slicing (anchor quality); recurring `review_fail` implicates the executor's step doctrine.
3. **Stall geography** — where wall-clock goes: per-subtask duration outliers from journal timestamps, remediation-cycle counts, gate latency p95 vs budget (`hooks/README.md` "Latency metrics & budget"), `lock_wait_ms` share.
4. **Grill-gap correlation** — downstream failures (parks, blocking findings, smoke reds) whose root cause was decidable at grill time. Each a missed staple/question candidate for the owning grill skill.
5. **Wiring debt** — open IOUs older than the feature that minted them.
6. **Criterion yield** — join each finding's `criterion` to its recorded outcome: a criterion whose findings are predominantly `dismissed` across features is a prune/reword candidate (proposal edits the owning `skills/afk/review/checklists/*.md`); a criterion that never fires is flagged as possible dead weight, never auto-pruned. This is what keeps the review catalog earning its cost instead of only growing.
7. **Pattern-debt recurrence** — the same criterion recurring in `PATTERN-DEBT.md` across features means the documented repo pattern itself deserves re-examination; surface it as input for `/afk:claude-md` (which owns those writes), not as a plugin edit.
8. **Lesson closure & recurrence** — the safety net behind conclude-at-detection capture (single incidents belong to the detection points; this family only grades what they already recorded). An `applied` lesson whose signal (same class + target area) recurs in a later feature means the edit didn't stick → propose the **next rung of the escalation ladder** (`skills/afk/lessons/LEDGER-FORMAT.md`) as a new lesson superseding it, citing the recurrence. Lessons `open` longer than the feature that minted them are stall signals — surface them for `/afk:lessons apply`. Status transitions are applied via `/afk:lessons`, never stamped here (the ledger is one of the ledgers the read-only rule covers).

## Output

Write the report to `{release-folder}/RETRO-{YYYY-MM-DD}.md` (format: [RETRO-FORMAT.md](RETRO-FORMAT.md)). Its load-bearing section is **Proposals**: at most 5, ranked by expected impact, each carrying its evidence (cited journal lines / finding ids / metric numbers), the root-cause hypothesis, and the concrete edit — file + section of the plugin artifact to change, with proposed wording. A proposal touching a lockstep pair or registry surface must name **every** partner file (`CLAUDE.md` "Lockstep" + `FRESHNESS.md` registry row) — a proposal that would create drift if half-applied is malformed.

End with the layered report per `REPORTING.md` (plugin root):

```
RETRO: <n> features, <m> subtasks — <p> proposals (top: <one-clause strongest signal>)
In plain terms: <one jargon-free sentence — the biggest thing slowing the workflow down or letting defects through, and what changing it would buy>
Report: {path}
```

## Hard rules

- **Read-only everywhere except its own report file.** Never edit a plugin file, plan artifact, ledger, or metric file. Proposals propose; humans apply.
- **Every claim cites.** A signal without its occurrences listed (feature + subtask + source line/id) is dropped. Numbers, not adjectives.
- **Don't double-count re-runs.** A re-executed subtask contributes its final outcome once; earlier journal lines for the same subtask count as remediation cycles, not extra occurrences.
- **No proposals about the target repo's code.** Product/code defects route to `/afk:fix`; this skill's proposals change the *workflow* (skills, doctrine files, gates, templates) only. Target-repo CLAUDE.md-rule gaps surface as input for `/afk:claude-md`, which owns those writes.
- **Cap the fan-out.** One digest subagent per feature; no nested fan-out.
