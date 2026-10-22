## Goal
Sync the AGENTS.md harness for the small lane so the next agent discovers it and knows how to use/extend it, settle the staples registry, and emit the trace matrix. Run /afk:agents-md scoped to THIS feature's net diff (this branch vs the parent), capturing: (1) ONE lazily-loaded instruction in the nearest component/leaf AGENTS.md — max 3 dense sentences on how to add/extend or invoke the feature, pointing at the key types + the spec dir; (2) ONE awareness sentence in the affected service-root AGENTS.md that names the feature and leads to (1); and (3) ONLY IF applicable, the STAPLES.md change — register a candidate new staple the PRD flagged, or advance/fill an existing staple's Reference this feature now exemplifies. If nothing is staple-worthy, (3) is a no-op. Then (4) write plan/TRACE.md per the trace-matrix spec in skills/afk/to-subtasks/HARNESS-SYNC.md — every PRD Acceptance Criterion mapped to its subtask, commits, and proving test, unsatisfied rows flagged.

## Complexity
mechanical

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — the files the how-to note points at
- ADR: adr/design/0001-in-place-fix-is-a-shared-procedure-file.md — the procedure file agents extend

## Scope
- AGENTS.md                      # the plugin root: tooling is the feature (one awareness sentence)
- skills/afk/AGENTS.md           # nearest leaf for the fix, diagnose and to-ticket skills
- docs/afk/small-lane/plan/TRACE.md   # the trace matrix this subtask emits
# docs only — NO source edits; no STAPLES.md exists in this repository (PRD Implementation Decisions)

## Seams
(none — documentation only; touches no SDD §14 seam)

## Acceptance
- [ ] The how-to note lives in the nearest component/leaf AGENTS.md, not the service root (SDD §8)
- [ ] The service-root AGENTS.md carries exactly ONE awareness sentence leading to that note (SDD §8)
- [ ] The staples registry was settled: the PRD records no staple and no candidate, so this is explicitly a no-op (PRD §Implementation Decisions)
- [ ] Nothing added restates code; every line clears the /afk:agents-md inclusion bar (SDD §8)
- [ ] Written via /afk:agents-md (SDD §8)
- [ ] plan/TRACE.md exists: every PRD Acceptance Criterion AC-001..AC-041 has a row (subtask, commits, proving test), unsatisfied rows explicitly flagged (PRD §Acceptance Criteria)

## Produces
- docs/afk/small-lane/plan/TRACE.md#| Criterion (verbatim) | — the trace-matrix header row

## Consumes
- 0011-bug-removal-release adr/0008-one-tracker-writer.md#Supersedes: ADR-0001 — the final tracker boundary the awareness sentence must not contradict

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | grep the awareness sentence's path in the root AGENTS.md; confirm `skills/afk/AGENTS.md` exists on disk | the pointer resolves |
| static | grep every PRD Acceptance Criterion id (AC-001..AC-041) against plan/TRACE.md rows — each has a row (or an explicit `— UNSATISFIED` flag) | the trace matrix is complete |

## Context excerpts
> (PRD Implementation Decisions) Staples: none; this repository has no `STAPLES.md`. Staple candidate: none.
> (SDD §8) No new skill (D-35); each new file lives beside the skill that owns it. Dependency direction: the plugin's own; a downstream file never names its caller (C-3).

## Parent PRD
docs/afk/small-lane/PRD.md

## Parent SDD
docs/afk/small-lane/SDD.md

## Blocked by
0001-diagnosis-format, 0002-developer-settings, 0003-tracker-attach, 0004-diagnose-rewrite, 0005-bug-mode, 0006-fix-procedure, 0007-ship-script, 0008-standalone-fix, 0009-in-place-callers, 0010-out-of-slice, 0011-bug-removal-release, 0013-config-contract

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
