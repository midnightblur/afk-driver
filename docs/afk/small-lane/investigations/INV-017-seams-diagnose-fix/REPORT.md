# INV-017 — L9 seams: diagnose, fix, lesson lockstep, grill size call

Verdict: `partial` (ledger `COVERAGE.json`, 0 validator defects). Frontier B14: other repositories, installed plugin caches, live harness loaders. Written by the orchestrator from the run's reply; the run's own write was refused.

## Seam rows (draft)

| Seam | Existing contract | Planned change | Impacted | Verdict |
|---|---|---|---|---|
| diagnose never fixes | `diagnose/SKILL.md:3` "→ fix → regression-test"; Phase 2.5 `:86-91` investigate + `rationale-read`; Phase 5 `:119-133` fix + regression test; Phase 6 `:135-147` cleanup + post-mortem; invocable by default | DIAGNOSIS.md, K-1/K-2, verdict, base-branch ask, check script | `fix/SKILL.md:12,31,38,42,93,112`; `execute:77`; `WORKFLOW-FEEDBACK.md:31`; `AGENTS.md:117,130`; `README.md:741,787`; `scripts/hitl-loop.template.sh:2` | reworked |
| fix standalone + in-place procedure | input Jira key / text / none (`fix:18`); never commits (`:107`); outcomes `:90-97` | standalone only; shared procedure file for callers | `execute:67,77,93,123`; `preflight:99,125`; `ROUND.md:162`; settle-change `:53` (inline, unaffected) | reworked |
| ESCAPE-ANALYSIS + WORKFLOW-FEEDBACK ↔ lesson ledger | miss classes `ESCAPE-ANALYSIS.md:18-29` ↔ `LEDGER-FORMAT.md:79-88`; `lesson-append.sh` checks event + class only | phase anchors move | `AGENTS.md:153`; phase anchors `ESCAPE-ANALYSIS.md:1,27,37-38`, `WORKFLOW-FEEDBACK.md:1,6,16,19,31,33`, `fix:110`; `[miss:]`/`[lesson:]` no slot in execute OUTCOME | extends |
| grill size call | grills take no argument; grill-requirements reads sources `:16`, exits `:91-104`; grill-solution assumes PRD `:3,14`, exits `:113-115` | size-call file; DIAGNOSIS.md as a source | entry `grill-requirements:16`, `grill-solution:14`; exit before `:104`, `:115` | extends |

## Landmines (verified)

- `BEHAVIORS.md:47` doctrine home "§Phase 2.5 — Trace the path"; `scripts/behavior_registry.py:283-298` rejects a missing heading, `:316-317` forces a revision bump; run by `hooks/behavior-registry-gate.sh:22` and `hooks/behavior-drift.sh:29`; tests `scripts/tests/test_behavior_registry_gate.py:51`, `hooks/tests/hook-smoke.sh:570`, `test_protected_branch_acceptance.py:1089`.
- Conflict A: PRD B-6 in-place smoke fix vs `smoke-test/SKILL.md:80` "Never patches to green", `autopilot/SKILL.md:67`; smoke gate has no commit step.
- Conflict B (inferred): `BEHAVIORS.md:49` reachability proof before any fix; the in-place procedure has no diagnosis step, so it carries the proof itself.
- Outcome names fixed_no_test, cannot_reproduce, needs_artifact_sync appear only in `fix/SKILL.md`; L7 "all routed by every caller" is new handling per caller.

## Must-dos

1. Keep `## Phase 2.5 — Trace the path` verbatim, or move BEHAVIORS.md:47 rev 2 + setup transport + CHANGELOG in one commit.
2. Keep diagnose's LANGUAGE pointer, `name: diagnose`, quoted description (`test_skill_frontmatter.py:86`); never `user-invocable: false`.
3. Keep investigate + `rationale-read` in diagnose; partial ledger reported inside DIAGNOSIS.md.
4. Dropping the hitl template updates `MANIFEST.md:384`; check script gets a test in scripts/tests.
5. Procedure carries: intake + VERIFICATION item-5 contract check (`fix:23,27`); spec reconciliation + needs_artifact_sync; escape analysis (api/e2e) + lesson; red-first regression test, proportional tiers, corpus ratchet (`:53`), `[DEBUG-` cleanup (`:112`); `rationale-add` pending ids; reachability proof.
6. `FRESHNESS.md:53` lists the procedure file.
7. Caller caps stay: execute one pass, Step 10.5 cap 2, preflight shared cap 2, PF-3 outside; disputes stay with the caller's referee (`SETTLEMENT:39`).
8. Smoke gate needs a commit owner; rewrite `smoke-test:80`, `autopilot:67`.
9. `AGENTS.md:153` updated for outcome-status lockstep + capture pointer.

## Unverified / out of partition (inferred)

- B1 alias/wire forms not enumerated (markdown skill has none, inferred); B3, B5, B6, B7, B10 no enumeration method.
- Stale today: `GLOSSARY.md:337` lists 5 miss classes (ESCAPE-ANALYSIS has 6); `providers/PARITY.md:75`, `providers/CONFORMANCE.md:44` list diagnose as missing; `diagnose:147` hands off to unshipped `/improve-codebase-architecture`; `AGENTS.md:153` already wrong (execute Step 4, 10.5, preflight PF-4c carry no CAPTURE pointer).

## Tool workarounds (plugin defects)

- merge_fragments: 84 seed placeholders dropped before fold.
- 5513 nodes under `docs/afk/small-lane/**` set `irrelevant` (this feature's own records).
- Overlapping tracer fragments (186 shared nodes) cannot fold one by one; folded as one combined fragment.
