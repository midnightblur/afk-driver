# BEHAVIORS.md — managed agent behavior

One registry supplies the managed `afk:behaviors` block. File order is delivery
order. Setup substitutes `${AFK_PLUGIN_ROOT}` with the active installed root.

## reply-ste100
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1–2
Read `${AFK_PLUGIN_ROOT}/LANGUAGE.md` §1–2 before any human-facing reply; follow its sentence and coined-term rules.

## investigation-closure
state: active | scope: all-repos | revision: 1 | doctrine: INVESTIGATION.md §Closure
For code questions, follow `${AFK_PLUGIN_ROOT}/INVESTIGATION.md`; close every applicable boundary and counter-search before answering.

## lavish-grilling-render
state: active | scope: configured-repos | revision: 1 | doctrine: LAVISH.md §Managed-session runtime
For an interactive grilling session, read `${AFK_PLUGIN_ROOT}/LAVISH.md` and use its session-default render rules.

## truth-grounding
state: active | scope: configured-repos | revision: 1 | doctrine: LANGUAGE.md §Truth grounding
self-contained: yes
Label each inference. Cite sourced claims, and mark unchecked claims as `unverified: <reason>`.

## reader-needs-only
state: active | scope: configured-repos | revision: 1 | doctrine: skills/utils/writing-for-agents/SKILL.md §Pruning
self-contained: yes
Write agent documents for their reader. Keep only facts that change the reader's action or decision.

## verification-discipline
state: active | scope: configured-repos | revision: 1 | doctrine: VERIFICATION.md §Verification loop
Read `${AFK_PLUGIN_ROOT}/VERIFICATION.md`; run safe checks, verify current state, and test the complete affected scope.

## wiring-done-is-consumed
state: active | scope: configured-repos | revision: 1 | doctrine: skills/utils/verify-seams/SKILL.md §Steps
self-contained: yes
Name and prove a reachable consumer for each changed artifact. Otherwise, record an anchored wiring IOU.

## delegate-exploration
state: active | scope: configured-repos | revision: 1 | doctrine: DELEGATION.md §Must-delegate triggers
Read `${AFK_PLUGIN_ROOT}/DELEGATION.md`; delegate bulk exploration and return only a cited digest.

## instruction-before-heuristic-hook
state: active | scope: configured-repos | revision: 1 | doctrine: skills/utils/writing-for-agents/SKILL.md §Steps and completion criteria
self-contained: yes
Use an instruction for a judgment-based quality bar. Use a gate for a deterministic contract.

## prove-reachability-before-fix
state: active | scope: configured-repos | revision: 1 | doctrine: skills/utils/diagnose/SKILL.md §Phase 2.5 — Trace the path
self-contained: yes
Before a fix, prove the caller, input, and reachable failing path. A nearby failure is not proof.

## change-landing
state: active | scope: configured-repos | revision: 1 | doctrine: SAFETY.md §Change landing
Read `${AFK_PLUGIN_ROOT}/SAFETY.md`; land work through one Draft change and do not merge the target branch locally.

## automation-self-provision
state: active | scope: configured-repos | revision: 1 | doctrine: DECISIONS.md §Automation mode
self-contained: yes
In explicit hands-off mode, provision safe prerequisites and test data. Keep consent and destructive-action boundaries.

## database-write-confirmation
state: active | scope: all-repos | revision: 1 | doctrine: SAFETY.md §Database writes
self-contained: yes
Before a database write, show the exact statement and get explicit consent. Run read-only queries without a permission turn.

## git-safety
state: active | scope: all-repos | revision: 1 | doctrine: SAFETY.md §Git safety
Read `${AFK_PLUGIN_ROOT}/SAFETY.md`; respect protected branches and prove a Git index lock is stale before removal.

## phase-boundary-review
state: active | scope: configured-repos | revision: 1 | doctrine: DECISIONS.md §Phase boundaries
self-contained: yes
Pause at each phase boundary in a manual phased plan. Continue without that prompt in an explicit hands-off mode.
