# INV-012 — how a hands-off run decides, parks and resumes

feat-small-lane@d346cfb · partial · 5/14 boundaries closed · 1517 nodes · 75 claims · ledger: COVERAGE.json

## Answer

**DECISIONS.md.**
- An agent decides only when all 3 hold:
  - the change can be undone on the branch: no migration, no outside write, no published-contract change;
  - one cited sentence picks a clear winner;
  - the decision is inside the agent's authority (`:21-25`).
- Otherwise the run takes the caller's park path, naming the fork, the options and a recommendation (`:27`).
- Each decision is recorded as a `D-{n}` entry in `plan/DECISIONS.md`, plus a journal line. With no `plan/`, it goes in the grill log's `Settled:` row (`:33-48`).
- DECISIONS.md names no status. Execute maps a park to `needs_decision`, or to `design_conflict` in cited mode (`execute/SKILL.md:129`; `CITED-MODE.md:131-134`).

**Execute exits.** Any exit other than success writes `blocked(<status>: …)` (`:110`).

| Status | Retry |
|---|---|
| test_fail, build_fail | 1 targeted retry, then 1 `/afk:fix` pass (`:67`) |
| review_fail | stops after 10 settle rounds without agreement |
| adversary_fail | 2 cycles |
| blocked_by | none |
| needs_decision | after the human answers |
| design_conflict | none; goes to grill-solution |

`blocked` (`:79`) and `env_unreachable` (`:94`) are set but not listed in Step 14.

**Execute calls to `/afk:fix`.**

| Step | Call | Input | Outcome read back |
|---|---|---|---|
| 8 | 1 pass | none named | only `design_conflict` |
| 10 | per finding | finding key and location | none |
| 10.5 | per finding, 2 cycles | finding key and location | none |

No caller routes the fix outcomes `fixed_no_test`, `cannot_reproduce`, `needs_artifact_sync` or `blocked` (`fix/SKILL.md:92-97`).

**Autopilot.**
- Any outcome other than success parks the slice. Independent slices continue, and each park sends a notification (`:35,38-39`).
- Dependents are skipped as `parked(waiting on ID)`, and their rows stay `pending`.
- Resume means running autopilot again, optionally with `from:{slug}`. Only `done` rows are skipped (`:14,30`).
- Autopilot runs slices in sequence (`:42`).

**Preflight and smoke test.**
- PF-3 (review) and PF-4 (orphans) call `/afk:fix` for correctness and spec findings, capped at 10 rounds and a shared cap.
- PF-2 and PF-7 fix inline, 2 cycles shared across both.
- Smoke test never calls `/afk:fix`. A red result sets `Feature: smoke-failing`; the human re-runs the slice or grills again (`smoke-test:53,80,87`).

**Outside dependency.** No mechanism models one (closed B1–B13).
- `## Blocked by` accepts plan subtask ids only (`SUBTASK-CONTRACT.md:114-115`). `validate_plan.py` does not reject an outside id (`:416-420`).
- Inferred: a Blocked-by entry for an outside id would block its slice on every run.

## Findings

- `GLOSSARY.md:330` says preflight fixes only mechanical failures, which contradicts `preflight:99,125`.
- The `README.md:596-599` status list is incomplete.
- `mission-control insights.py:23` ignores `park-inherited` and `stranded`.
- No tests cover the status set, the park or the resume.

## Unverified

- Whether the Step 10 round count resets after Step 10.5 re-runs from Step 8.
- Whether preflight's shared fix cycles survive a resume.
- B3, B5, B6, B7, B10 have no method, and the B1 alias forms were not enumerated.
- Plugin defect: `merge_fragments.py:108-136` places seed nodes that clash with every tracer node. They were removed before the fold.

## Frontier

B14: other repositories, live forge and CI state.

Written by the orchestrator from the investigation's reply; the investigation's own REPORT.md write was refused.
