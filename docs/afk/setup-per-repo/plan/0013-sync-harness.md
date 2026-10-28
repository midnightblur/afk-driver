# 0013-sync-harness — sync the AGENTS.md harness and emit the trace matrix

## Goal
Sync the AGENTS.md harness for setup-per-repo so the next agent discovers it and knows how to use/extend it, settle the staples registry, and emit the trace matrix. Run /afk:agents-md scoped to THIS feature's net diff (this branch vs the parent), capturing: (1) ONE lazily-loaded instruction in the nearest component/leaf AGENTS.md — max 3 dense sentences on how to add/extend or invoke the feature, pointing at the key types + the spec dir; (2) ONE awareness sentence in the affected service-root AGENTS.md that names the feature and leads to (1); and (3) ONLY IF applicable, the STAPLES.md change — register a candidate new staple the PRD flagged, or advance/fill an existing staple's Reference this feature now exemplifies. If nothing is staple-worthy, (3) is a no-op. Then (4) write plan/TRACE.md per the trace-matrix spec in skills/afk/to-subtasks/HARNESS-SYNC.md — every PRD Acceptance Criterion mapped to its subtask, commits, and proving test, unsatisfied rows flagged.

## Complexity
mechanical

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — the modules the instruction points at

## Scope
- AGENTS.md                         # the repository-root AGENTS.md (service root)
- skills/afk/AGENTS.md              # the nearest leaf for setup and worktree behaviour
- docs/afk/setup-per-repo/plan/TRACE.md   # the trace matrix this subtask emits
# docs only — NO source edits; this plugin has no STAPLES.md, so (3) is a no-op

## Seams
(none — documentation only)

## Acceptance
- [ ] The how-to note lives in the nearest component/leaf AGENTS.md, not the service root (HARNESS-SYNC.md)
- [ ] The service-root AGENTS.md carries exactly ONE awareness sentence leading to that note (HARNESS-SYNC.md)
- [ ] The staples registry was settled: this plugin has no staples registry and the PRD flagged no candidate, so this is explicitly a no-op (PRD §Implementation Decisions "Staples: none")
- [ ] Nothing added restates code; every line clears the /afk:agents-md inclusion bar (HARNESS-SYNC.md)
- [ ] Written via /afk:agents-md (HARNESS-SYNC.md)
- [ ] plan/TRACE.md exists: every one of the 48 PRD Acceptance Criteria has a row (subtask, commits, proving test), unsatisfied rows explicitly flagged (HARNESS-SYNC.md)

## Produces
- docs/afk/setup-per-repo/plan/TRACE.md#| Criterion (verbatim) | — the trace matrix header row

## Consumes
- 0012-smoke-api scripts/tests/test_setup_per_repo_acceptance.py#def test_a1_setup_walk_steps — the proving tests the trace matrix names

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | grep the awareness sentence's path in the root AGENTS.md; confirm `skills/afk/AGENTS.md` exists on disk | the pointer resolves |
| static | grep every PRD Acceptance Criterion id (AC-001 … AC-080, 48 ids) against plan/TRACE.md rows — each has a row or an explicit `— UNSATISFIED` flag | the trace matrix is complete |

## Context excerpts
> (PRD §Implementation Decisions) Staples: none. This plugin has no staples registry.

## Parent PRD
docs/afk/setup-per-repo/PRD.md

## Parent SDD
docs/afk/setup-per-repo/SDD.md

## Blocked by
0001-safe-writer, 0002-settings-reader, 0003-repository-list, 0004-placement, 0005-worktree-creator, 0006-worktree-guard, 0007-forge-account, 0008-jira-sign-in, 0009-settings-writer, 0010-setup-walk, 0011-smoke-e2e, 0012-smoke-api

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
