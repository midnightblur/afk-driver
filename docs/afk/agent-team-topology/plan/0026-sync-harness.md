## Goal
Sync the AGENTS.md harness for agent team topology and multi-model so the next agent discovers it and knows how to
use/extend it, settle the staples registry, and emit the trace matrix. Run /afk:agents-md scoped
to THIS feature's net diff (this branch vs the parent), capturing: (1) ONE lazily-loaded
instruction in the nearest component/leaf AGENTS.md — max 3 dense sentences on how to add/extend
or invoke the feature, pointing at the key types + the spec dir; (2) ONE awareness sentence in the
affected service-root AGENTS.md that names the feature and leads to (1); and (3) ONLY IF
applicable, the STAPLES.md change — register a candidate new staple the PRD flagged, or
advance/fill an existing staple's Reference this feature now exemplifies. If nothing is
staple-worthy, (3) is a no-op. Then (4) write plan/TRACE.md per the trace-matrix spec in
skills/afk/to-subtasks/HARNESS-SYNC.md — every PRD Acceptance Criterion mapped to its subtask,
commits, and proving test, unsatisfied rows flagged.

## Complexity
mechanical

## Design refs
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — the changed seams whose harness text and trace rows this subtask settles

## Scope
- AGENTS.md
- skills/afk/AGENTS.md
- docs/afk/agent-team-topology/plan/TRACE.md
# docs only — NO source edits

## Seams
- (none — documentation only)

## Acceptance
- [ ] The how-to note lives in the nearest component/leaf AGENTS.md, not the service root (SDD §14)
- [ ] The service-root AGENTS.md carries exactly ONE awareness sentence leading to that note; CLAUDE.md, the one-line pointer @AGENTS.md, is not edited (SDD §14)
- [ ] The staples registry was settled: this repository has no staples registry, so (3) is explicitly a no-op (PRD Staples)
- [ ] Nothing added restates code; every line clears the /afk:agents-md inclusion bar (SDD §14)
- [ ] Written via /afk:agents-md, which this branch ships at skills/afk/agents-md/ (plan D-15) (SDD §14)
- [ ] plan/TRACE.md exists: every PRD Acceptance Criterion has a row (subtask, commits, proving test), unsatisfied rows explicitly flagged (SDD §14)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §14)

## Produces
- docs/afk/agent-team-topology/plan/TRACE.md#Criterion (verbatim) — the trace matrix

## Consumes
- 0024-status-set-and-journal-reasons skills/afk/execute/SKILL.md#unrecorded_agent — the last status surface the trace covers

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `grep -n 'Criterion (verbatim)' docs/afk/agent-team-topology/plan/TRACE.md`; `grep -n 'unrecorded_agent' skills/afk/execute/SKILL.md` | Produces and consumed anchors present |
| static | grep the awareness sentence's path in the service-root AGENTS.md; confirm that leaf AGENTS.md exists on disk | the pointer resolves |
| static | grep every PRD Acceptance Criterion against plan/TRACE.md rows — each criterion has a row (or an explicit `— UNSATISFIED` flag) | the trace matrix is complete |

## Context excerpts
> (PRD Staples) This repository has no staples registry — verified by filename and content search; the registry lives in consuming repositories. No staple is folded in, and none is skipped silently.

> (PRD Implementation Decisions) **A candidate new staple** is not raised: this repository has no staples registry (see Further Notes).

## Parent PRD
docs/afk/agent-team-topology/PRD.md

## Parent SDD
docs/afk/agent-team-topology/SDD.md

## Blocked by
- 0001-glossary-terms
- 0002-config-transport-and-pattern-keys
- 0003-manifest-module
- 0004-knowledge-store
- 0005-pattern-resolver-and-builtin-records
- 0006-transport-family-and-herdr
- 0007-desktop-tool-transport
- 0008-inbox-wait-script
- 0009-spawn-permission-check
- 0010-team-entry-script
- 0011-job-supervisor
- 0012-cleanup
- 0013-provider-layer-codex
- 0014-delegation-doctrine
- 0015-team-skill-and-manifests
- 0016-sessionstart-handlers
- 0017-spawn-steps
- 0018-review-gate-pane-workers
- 0019-adversary-pane-agent
- 0020-subagent-fallback-report-writers
- 0021-fix-afk-lite
- 0022-bug-pane-legs
- 0023-lesson-ledger-lock
- 0024-status-set-and-journal-reasons
- 0025-dashboard-team-section

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
