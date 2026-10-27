---
name: fix
description: Orchestrates a bug fix — root-cause via /afk:diagnose, proportional coverage, escape analysis. Use when a verification finding, human/QA bug report, or Jira bug needs fixing.
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# afk:fix — fix a bug and keep the source of truth true

Run when a bug surfaces — typically a feature's **verification phase** (agent- or human-found), or ad-hoc on released code. Also the **recovery path** when a verification tier stays red after its targeted retry, and the follow-up to a red feature smoke gate.

`fix` is a **thin orchestrator**; does not re-implement diagnosis. `/afk:diagnose` owns reproduce → failing test → spec comparison → root cause → verdict → fix proposal, and changes no product code. `fix` wraps that with **context intake**, **the test-first fix the proposal describes**, **proportional higher-tier tests**, **feature-session artifact reconciliation**.

Phases 2 to 3.5 run the steps of the shared fix procedure, [IN-PLACE-FIX.md](IN-PLACE-FIX.md), under its hard rules — see Hard rules.

## Argument

A Jira bug key, free-text bug description, a `DIAGNOSIS.md` path, or nothing (infer the finding from conversation — e.g. a verification result just came back red).

## Phase 0 — Intake & classify

1. **Source of the finding.**
   - **Jira bug** (key in arg or derivable from branch): `tracker_get` with `fields=summary,status,priority,issuetype,labels,assignee,reporter,description,comment`. Delegate the pull to an `afk-reader` subagent returning a task-shaped bug digest — symptom, expected, repro hints, env, cited to ticket fields — per `DELEGATION.md` (plugin root).
   - **Ad-hoc** (human/QA/agent verification finding): take symptom + repro hints from conversation — already in context, no delegation.
2. **Session type.** **feature-building (unreleased)** vs **ad-hoc / maintenance**, by the signals in [IN-PLACE-FIX.md](IN-PLACE-FIX.md) "Unreleased feature". Ad-hoc → **skip Phases 3 and 3.5**.
3. **Locate artifacts** (feature session only): `{service}/specs/{year}r{release}/{TICKET-ID}/` — `PRD.md`, `SDD.md`, `VERIFICATION-PLAN.md`, `adr/{requirements,design}/`, `plan/`.
4. **Public contract check** — `${AFK_PLUGIN_ROOT}/VERIFICATION.md` §Verification loop item 5.

## Phase 1 — Diagnose (delegate, do not duplicate), then fix test-first

1. **Get the diagnosis.** A `DIAGNOSIS.md` path → run `afk-python ${AFK_PLUGIN_ROOT}/skills/utils/diagnose/scripts/check_diagnosis.py <path>`; a refusal → `blocked`; an accepted file is the diagnosis, used without running diagnose again. Otherwise run **`/afk:diagnose`**, handing it the ticket key when there is one, else the description, with everything from intake (repro steps, env, exact captured symptom) as context. A finding already in hand — a red tier, a review or adversary finding — asks for a light diagnosis that reuses it as the reproduction. Running in a linked worktree (`git rev-parse --git-dir` differs from `--git-common-dir`), hand diagnose that worktree and the starting-branch answer `branch tip`.
   - Ticketed or known-env bug → push diagnose toward an **automated** loop (api or e2e/browser) over HITL — you have the env and steps.
2. **Route** on diagnose's status line (`DIAGNOSIS: <verdict> <path>`, its last line) or on a handed diagnosis's Verdict part:
   - V-1 obvious fix → step 3.
   - V-2 several fixes or V-3 spec gap whose latest size-call row for its Work id, across both grill sections of the `GRILL-LOG.md` beside it, is `still small` (`${AFK_PLUGIN_ROOT}/skills/afk/grill-requirements/GRILL-LOG-FORMAT.md` "Size-call row") → step 3, applying the row's `settled:` answer as the Fix proposal.
   - Any other V-2 or V-3, or V-4 works as specified → stop with no code change. A wrong binding SDD/ADR decision in a feature session → report `design_conflict` and route per Phase 3. Otherwise report `blocked` naming the verdict and the diagnosis path.
   - V-5 cannot reproduce → stop; report `cannot_reproduce` with the diagnosis's Attempts.
   - `DIAGNOSIS: blocked — <reason>` → stop; report `blocked` with that reason.
3. **Fix test-first** (`/afk:tdd`) in the diagnosis worktree: of the worktrees in `git worktree list` whose folder holds the `DIAGNOSIS.md` path, the one with the longest folder path (linked worktrees can sit inside the main checkout), else the one on the Diagnosis branch. Neither → cut one onto that branch (`${AFK_PLUGIN_ROOT}/scripts/create-worktree --branch <Diagnosis branch> --dir <work id, lower-cased> --no-open`) when the branch holds the failing test (`git cat-file -e <Diagnosis branch>:<test path>`) or the diagnosis has none; else stop `blocked`, since a handed-over worktree kept the test uncommitted. A worktree fix may not edit (another session holds it) → stop `blocked`, naming it. Watch the failing test fail (it passes or does not build → stop `blocked`, naming the branch and the Base), apply the Fix proposal, watch it pass. A light diagnosis's reused check, or a seam absence recorded in Root cause, plays the failing test's part. The failing test and `DIAGNOSIS.md` stay beside the fix for whoever commits it: the test becomes the regression test, and the diagnosis ships with the fix. A worktree fix did not start in stays for the human to commit from; the report names its path.

Diagnose reads the rationale of the lines on the failing path (its Phase 2.5); run `rationale-read` (`RATIONALE.md` § Read path) on any other pre-existing line the fix edits. A fix that adds a comment classifies it per `RATIONALE.md` § Classification test and records each moved reason per § Write path. List the pending operation IDs in the exit report.

Exit gate: verdict V-1 (or a V-2/V-3 whose latest size-call row is `still small`), the Fix proposal applied, the diagnosis's failing test green (or the seam absence the diagnosis records in Root cause).

## Phase 2 — Broaden coverage (proportional)

Run [IN-PLACE-FIX.md](IN-PLACE-FIX.md) step 4, with the diagnosis's failing test as the seam regression test, then its step 5, with the diagnosis's reproduction as the step 1 failure. A tier or reproduction still red there → report `blocked`, naming it.

## Phase 2.5 — Escape analysis

Run [IN-PLACE-FIX.md](IN-PLACE-FIX.md) step 6. Carry the miss class into Phase 4's report.

## Phase 3 — Reconcile the source of truth (feature sessions only)

Run [IN-PLACE-FIX.md](IN-PLACE-FIX.md) step 7. Its `design_conflict` → report `design_conflict`. A stale artifact it records → report `needs_artifact_sync`, naming the artifact and its owning skill.

## Phase 3.5 — Workflow feedback

Run [IN-PLACE-FIX.md](IN-PLACE-FIX.md) step 8. Report the lesson id in Phase 4.

## Phase 4 — Report

End with the structured line plus one plain-terms sentence per the reporting protocol (`REPORTING.md` at the plugin root):

```
OUTCOME: <status> — <one-line summary> [ticket: <KEY|none>]
In plain terms: <one jargon-free sentence — what was broken, what's true now, what (if anything) still needs a human>
```

| Status | Meaning / next action |
|---|---|
| `fixed` | Root cause found, fix applied, regression test + any added tier green. |
| `fixed_no_test` | Fix applied, no new test, naming the proportionality reason (e.g. caption fix) or the absent-seam finding from diagnose. |
| `cannot_reproduce` | Diagnose couldn't build a loop; list what was tried and what's needed (env / artifact / instrumentation). |
| `design_conflict` | Fix requires changing a frozen SDD/ADR decision; routed to `/afk:grill-solution`. |
| `needs_artifact_sync` | Fix landed but a load-bearing artifact is now stale and unreconciled; name it + the owning skill. |
| `blocked` | Anything else; explain. |

Phase 2.5 ran → add the **miss class** to the summary; Phase 3.5 ran → append the **lesson id** so the workflow-improvement lesson isn't lost:

```
OUTCOME: fixed — <summary> [ticket: <KEY>] [miss: <class>] [lesson: <L-NNNN>]
```

## Hard rules

- **The hard rules of [IN-PLACE-FIX.md](IN-PLACE-FIX.md) bind every run of this skill, its no-commit rule included.** The human commits, or the run that invoked this skill does.
