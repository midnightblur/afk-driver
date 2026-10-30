# Execution Plan — afkv2 S2 — page skills, to-prd with Jira publish, to-subtasks

> Parent ticket: GitHub #153   Mode: cited
> Sources: [PRD](../PRD.md) · [SDD](../SDD.md) · [ADRs](../adr/)
> Branch (for /afk:execute): feat/afkv2-s2
> Last updated: 2026-10-30 (status column maintained by /afk:execute)
> Feature: in-progress   <!-- /afk:smoke-test stamps "complete (smoke green …)" iff a smoke gate exists -->
> Review policy: lean   <!-- lean | full — slice review-gate roster; semantics owned by skills/afk/review/SKILL.md "Gate policy". Seeded lean; flip to full by hand for the full roster on every slice; absent (older plans) reads full -->

This is one of 4 plan folders for afkv2 (`plan-s1`..`plan-s4`, decision D-S-4).
Sessions S1, S2 and S3 run in parallel on their own branches into `feat/afkv2`;
S4 runs on day 4 after their pull requests merged. Citation tags: `(PRD §AC-NNN)`
and similar name a PRD id; `(ADR-NNNN design)` is `adr/design/`,
`(ADR-NNNN requirements)` is `adr/requirements/`.

Cross-session rule: an input another session builds is fixed by the SDD
(§3 command contracts, §4 schema v0, §8 "Frozen on day 1"). Until the producer's
pull request merges into `feat/afkv2`, test against a recorded fake built from
that contract (SDD §3: "the consumer tests against a recorded fake"). After the
merge, merge `feat/afkv2` into this branch and run the same tests against the
real producer; S4 subtask 0016 repeats that run for every session.

## Inputs

| Input | Value | Source |
|-------|-------|--------|
| Benchmark repository (AC-021) | `C:\Users\mvu\IdeaProjects\core-services` (about 53,000 files) | benchmark of 2026-10-29 |
| v1 round documents for engine fixtures | `C:\Users\mvu\AppData\Local\Temp\claude\C--Users-mvu-PersonalProjects-afk-driver\23e372bc-cde6-4631-9ea7-43a4a91d8684\scratchpad\grill\grill-final.json`, `...\grill\sdd.json` (copy into the fixtures folder; the scratchpad is temporary) | SDD §4 "Migration & backfill" |
| Toy repository, written test ticket | owner names it by day 4 | PRD AC-001 |
| Jira test project (D-4) | owner names it by day 4 | PRD Further Notes, Parked |
| Demo ticket (Q26) | owner gives it by day 5 | PRD Further Notes, Parked |

## Decisions taken at slicing (two-way doors, reversible on the branch)

| Id | Decision | Why | Reverse |
|----|----------|-----|---------|
| D-S-1 | Run branch = `<feature branch>-run`, an orphan branch with `plan/` at its root | AC-071 needs one name both S2 (writer) and S3 (reader) use; the SDD fixes the layout but not the name | rename in 0010 + 0015 |
| D-S-2 | Division approval = PLAN.md header line `> Division: approved <YYYY-MM-DD>`, written by to-subtasks after the developer's mark | AC-060 needs one record both S2 and S3 read; not in SDD §8 "Frozen on day 1" | change in 0010 + 0015 |
| D-S-3 | Published-ticket log = `%LOCALAPPDATA%\afkv2\published-tickets.txt`, one line `<ISO-8601 UTC> <ticket key> <receipt 8 chars>` per publish | the SDD §14 switch-back report needs a source; S2 writes it, S3 reads it | change in 0008 + 0011 |
| D-S-4 | 4 plan folders (`plan-s1`..`plan-s4`); subtask ids numbered 0001-0017 across all of them, so an id is unique feature-wide | one folder per session branch avoids merge conflicts on PLAN.md; the session numbering of the PRD division is kept | merge into one `plan/` |
| D-S-5 | Inside S3, code-review and create-change-request come before autopilot (0013, 0014, 0015) | autopilot calls both; a producer must rank before its consumer | — |
| D-S-6 | The page engine (one SDD §8 module) is cut in 3 slices along the SDD §8 "Ported vs new" rows and the registry: 0003 render / check + show / poll, 0004 diagram registry entries, 0005 ingest | owner-approved division W-2; each slice is one public verb set or registry entries | merge 0003-0005 |
| D-S-7 | `## Seams` lists only SDD §14 rows (the plan check requires a §14 row + its investigation); §9b rows go to `## Acceptance`, `## Verification` and the seam register below | the v1 plan check grounds every `## Seams` bullet on §14 | — |
| D-S-8 | Codex live checks (hook after the trust review, compaction, Stop-hook wait) are owner-run steps: they need afkv2 enabled in the owner's global Codex config | a global switch on the owner's machine is the owner's call; no credentials are copied | the agent runs them with the owner's approval |
| D-S-9 | One `0017-sync-harness` subtask, in plan-s4 only, not one per plan | 4 harness syncs would edit the same AGENTS.md lines; S4 runs after all sessions merged | — |

## Solution map

```mermaid
flowchart LR
  subgraph Components
    VZ["visualize guide"]
    GR["grill"]
    PR["to-prd + Jira publish"]
    PS["propose-solution"]
    TS["to-subtasks + plan contract"]
  end
  T6([0006 visualize-skill]) --> VZ
  T7([0007 grill-skill]) --> GR
  T8([0008 to-prd-jira-publish]) --> PR
  T9([0009 propose-solution-skill]) --> PS
  T10([0010 to-subtasks-skill]) --> TS
  T8 -. seam .-> S1{{"§14 v1 PRD block (use)"}}
  T8 -. seam .-> S2{{"§9b Jira REST (use)"}}
```

*S2 builds the chain's front half in chain order; every skill reads the one
before it from disk.*

## Seam register

| § | Seam (SDD row) | Implemented by | Used by |
|---|----------------|----------------|---------|
| §14 | "v1 PRD block written by build_description" | S3 0012-forge-tracker-port | 0008-to-prd-jira-publish |
| §9b | "Jira REST" | S3 0012-forge-tracker-port | 0008-to-prd-jira-publish (via recorded fake) |
| §9b | "lavish host" | S1 0003 | 0007, 0009 (via recorded fake) |
| §9b | "Codex Stop hook" | S1 0003 | 0007, 0009 |

## Progress tracker

| # | Subtask | Title | Status | Blocked by | Tiers | Seams |
|---|---------|-------|--------|------------|-------|-------|
| 1 | 0006-visualize-skill | visualize skill | done | — | static, unit | — |
| 2 | 0007-grill-skill | grill skill | done | 0006-visualize-skill | static, unit, integration | — |
| 3 | 0008-to-prd-jira-publish | to prd jira publish | done | 0007-grill-skill | static, unit, integration | use §14 |
| 4 | 0009-propose-solution-skill | propose solution skill | done | 0008-to-prd-jira-publish | static, unit, integration | — |
| 5 | 0010-to-subtasks-skill | to subtasks skill | pending | 0009-propose-solution-skill | static, unit, integration | — |

Status values: `pending` → `designing` → `developing` → `verifying` → `reviewing` → `done`,
or `blocked(<reason>)`. <!-- status set: lockstep copy — owned by /afk:execute (progress-tracker status column) -->
`/afk:execute` advances the row it is working and writes
the date in the header; everything else in PLAN.md is yours to edit.

## Feature smoke gate (minimal)

`.afk/config.yaml` declares no `verification.tiers`, and the repository has no
build-gate kind: the app-start, e2e and api rows are dropped. The two rows below
name the afkv2 tree directly.

| # | Check | Command | Status |
|---|-------|---------|--------|
| 1 | compile | `afk-python -m compileall -q afkv2` | |
| 2 | regression | `afk-python -m pytest afkv2/tests -q` (the afkv2 tree is the changed module) | |

Last run: —
