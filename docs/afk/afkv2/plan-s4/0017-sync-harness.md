# 0017-sync-harness

## Goal
Sync the AGENTS.md harness for afkv2 so the next agent discovers it and knows how
to use/extend it, settle the staples registry, and emit the trace matrix. Run
/afk:agents-md scoped to this feature's net diff (`feat/afkv2` vs `main`),
capturing: (1) ONE lazily-loaded instruction in `afkv2/AGENTS.md` — max 3 dense
sentences on how to add/extend or invoke afkv2, pointing at the key files + the
spec dir; (2) ONE awareness sentence in the repository-root AGENTS.md that names
afkv2 and leads to (1); and (3) ONLY IF applicable, a STAPLES.md change — the PRD
flagged no new-staple candidate, so (3) is expected to be a no-op. Then (4) write
`docs/afk/afkv2/plan-s4/TRACE.md` per the trace-matrix spec in
skills/afk/to-subtasks/HARNESS-SYNC.md — every PRD Acceptance Criterion mapped to
its subtask (in any of plan-s1..plan-s4), commits, and proving test, unsatisfied
rows flagged.

## Complexity
mechanical

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — the module map the note points at

## Scope
- afkv2/AGENTS.md
- AGENTS.md   # one awareness sentence only
- docs/afk/afkv2/plan-s4/TRACE.md
- # docs only — NO source edits

## Seams
(none — this slice touches no SDD §14 seam row; its §9b rows are in ## Acceptance and the PLAN.md seam register)

## Acceptance
- [ ] The how-to note lives in `afkv2/AGENTS.md`, not the repository root (HARNESS-SYNC)
- [ ] The repository-root AGENTS.md carries exactly ONE awareness sentence leading to that note (HARNESS-SYNC)
- [ ] The staples registry was settled: the PRD flagged no candidate, so this is explicitly a no-op unless the human says otherwise (PRD Implementation Decisions "No new-staple candidate")
- [ ] Nothing added restates code; every line clears the /afk:agents-md inclusion bar; written via /afk:agents-md
- [ ] `docs/afk/afkv2/plan-s4/TRACE.md` exists: every PRD Acceptance Criterion has a row (subtask, commits, proving test), unsatisfied rows explicitly flagged

## Produces
- docs/afk/afkv2/plan-s4/TRACE.md#Criterion (verbatim) — the trace matrix

## Consumes
- 0016-chain-smoke-run docs/afk/afkv2/plan-s4/SMOKE-RUN.md#Chain smoke run — proof rows for AC-001 and the live checks

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `rg -F afkv2/AGENTS.md AGENTS.md`; `afkv2/AGENTS.md` exists on disk | the pointer resolves |
| static | every `AC-0NN` id in PRD.md has a row in TRACE.md (or an explicit `— UNSATISFIED` flag): `rg -o "AC-0[0-9]{2}" docs/afk/afkv2/PRD.md` vs the same over TRACE.md | the trace matrix is complete |

## Context excerpts
> (PRD Implementation Decisions) No new-staple candidate.

## Parent PRD
docs/afk/afkv2/PRD.md

## Parent SDD
docs/afk/afkv2/SDD.md

## Blocked by
- 0016-chain-smoke-run

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` (this plan folder's `DECISIONS.md`) and implemented; a
one-way door or a tie exits `design_conflict` quoting the SDD section + the
conflict. Never override off the record. Parked conflicts route back to
`/afk:grill-solution` for a superseding ADR.
