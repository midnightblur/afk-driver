# 0009-sync-harness — harness sync, glossary terms, trace matrix

## Goal
Sync the CLAUDE.md harness for the research, prepared-ask, consultation and dispatch capabilities so the next agent discovers them and knows how to use/extend them, settle the staples registry, and emit the trace matrix. Run /afk:claude-md scoped to THIS feature's net diff (this branch vs the parent), capturing: (1) ONE lazily-loaded instruction in the nearest component/leaf CLAUDE.md (`skills/afk/CLAUDE.md` — the plugin's skill-extension notes) — max 3 dense sentences on how to add a participant provider, extend the consult protocol, or invoke research, pointing at the key files (`scripts/dispatch_harness.py`, `hooks/lib/providers/<name>.sh`, `skills/utils/research/`, `skills/utils/consult/`, `RESEARCH.md`) + the spec dir; (2) ONE awareness sentence in the plugin-root `CLAUDE.md` that names the feature and leads to (1); and (3) ONLY IF applicable, the STAPLES.md change — the PRD flags no candidate staple, so (3) is a no-op unless the diff shows otherwise. Then (4) write plan/TRACE.md per the trace-matrix spec in skills/afk/to-subtasks/HARNESS-SYNC.md — every PRD Acceptance Criterion mapped to its subtask, commits, and proving test, unsatisfied rows flagged. Also register the six workflow terms the PRD names (research, world question, consultation, participant, prepared ask, disposition) in the plugin-root `GLOSSARY.md` per its format, and refresh the `FRESHNESS.md` rows the earlier slices left pointing at this feature.

## Complexity
standard

## Design refs
- SDD: SDD.md#§14 row "`plugin.json` manifests … catalogs that must list `research`, `consult` and `afk-researcher`" — +6 glossary terms; catalog mentions
- ADR: adr/requirements/0001-no-priorities-registry-now.md — no registry file; IOU on a retro-observed trigger

## Scope
- CLAUDE.md                        # plugin root: ONE awareness sentence
- skills/afk/CLAUDE.md             # the leaf how-to note
- GLOSSARY.md                      # the six workflow terms
- FRESHNESS.md                     # rows for the feature's artifacts, if an earlier slice left one incomplete
- docs/afk/research-enhancement/plan/TRACE.md
# docs only — NO source edits

## Seams
- implement: §14 row "`plugin.json` manifests, `skill-registry-gate.sh`, `native-contract-gate.sh`, `genericity-gate.sh`, `wiring-gate.sh` and the `README.md` / `CLAUDE.md` catalogs that must list `research`, `consult` and `afk-researcher`" — this subtask owns the six `GLOSSARY.md` terms and the CLAUDE.md awareness + how-to lines (INV-004)

## Acceptance
- [ ] The how-to note lives in the nearest component/leaf CLAUDE.md (`skills/afk/CLAUDE.md`), not the plugin root (HARNESS-SYNC.md)
- [ ] The plugin-root CLAUDE.md carries exactly ONE awareness sentence leading to that note (HARNESS-SYNC.md)
- [ ] The staples registry was settled: the PRD flags no candidate ("Candidate new staple: none"), so this is explicitly a no-op unless the net diff shows a standing expectation (PRD "Implementation Decisions")
- [ ] `GLOSSARY.md` gains entries for research, world question, consultation, participant, prepared ask, disposition per `skills/utils/glossary/GLOSSARY-FORMAT.md`; each points at its owning file (`RESEARCH.md`, `DECISIONS.md` "Prepared ask", `skills/utils/consult/PROTOCOL.md`) (PRD "Implementation Decisions" row "Registry surfaces"; SDD §14 row "`plugin.json` manifests …")
- [ ] Nothing added restates code; every line clears the /afk:claude-md inclusion bar (HARNESS-SYNC.md)
- [ ] Written via /afk:claude-md (HARNESS-SYNC.md)
- [ ] plan/TRACE.md exists: every PRD Acceptance Criterion AC-001..AC-044 has a row (subtask, commits, proving test), unsatisfied rows explicitly flagged (HARNESS-SYNC.md)
- [ ] The IOUs the ADRs name — the priorities registry trigger (ADR-0001) and the executor/write-role hop on `state.json` (ADR-0004 requirements) — are recorded in `.claude/wiring-ious.md` anchored to their ADR (ADR-0001; ADR-0004)

## Produces
- docs/afk/research-enhancement/plan/TRACE.md#Criterion (verbatim) — the trace matrix: one row per PRD Acceptance Criterion
- GLOSSARY.md#**Prepared ask** — the six new workflow terms (research, world question, consultation, participant, prepared ask, disposition)
- skills/afk/CLAUDE.md#Research and consultation — the leaf how-to note

## Consumes
- 0006-research-skill skills/utils/research/SKILL.md#name: research — the skill the how-to note and glossary point at
- 0007-consult-skill skills/utils/consult/PROTOCOL.md#Dispositions — the owning file the `disposition` glossary entry points at
- 0005-research-doctrine RESEARCH.md#Question types — the owning file the `world question` glossary entry points at
- 0004-prepared-ask DECISIONS.md#Prepared ask — the owning file the `prepared ask` glossary entry points at

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | grep the awareness sentence's path in the plugin-root CLAUDE.md; confirm `skills/afk/CLAUDE.md` carries the how-to heading | the pointer resolves |
| static | grep every PRD Acceptance Criterion id (AC-001..AC-044) against plan/TRACE.md rows — each criterion has a row (or an explicit `— UNSATISFIED` flag) | the trace matrix is complete |
| static | `python scripts/glossary_usage.py` (the glossary steward's checker) + `python hooks/run-hook.py plugin stop-gates.sh` | glossary entries well-formed; prose passes the plugin's Stop gates |

## Context excerpts
> (PRD header) Vocabulary: `GLOSSARY.md` (plugin root); new terms below are registered there by the sync-harness subtask.
> (PRD "Implementation Decisions" row "Registry surfaces") `GLOSSARY.md` terms (research, world question, consultation, participant, prepared ask, disposition), `CAPABILITIES.md` rows, `skills/afk/setup/MANIFEST.md` opt-in rows, `FRESHNESS.md` rows, both plugin manifests, CLAUDE.md and README catalogs | same-commit rule per `FRESHNESS.md`
> (PRD "Implementation Decisions") Candidate new staple: none.
> (PRD "Out of Scope") Executor or write-role hop to another provider; automatic host replacement (ADR-0004; IOU on `state.json`). · A priorities registry file (ADR-0001; IOU on a retro-observed trigger).
> (SDD §14 row "`plugin.json` manifests …") +2 skills, +1 agent (+ Codex agent stub), +1 doctrine file, +6 glossary terms, +1 capability row, catalog mentions in CLAUDE.md and README.md
> (ADR-0001 requirements) No `PRIORITIES.md` registry file is created in this release; the trigger to create one is `/afk:retro` observing repeated re-mining of the same priority (recorded as an IOU, homed beside the staples registry when built).

## Parent PRD
docs/afk/research-enhancement/PRD.md

## Parent SDD
docs/afk/research-enhancement/SDD.md

## Blocked by
0001-config-blocks, 0002-provider-verbs, 0003-dispatch-harness, 0004-prepared-ask, 0005-research-doctrine, 0006-research-skill, 0007-consult-skill, 0008-caller-pointers

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
