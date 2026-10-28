# PRD — small lane

Work id: `small-lane` (no parent ticket). Source: `GRILL-LOG.md` "Requirements grill", rounds 1–6, settled 2026-10-13. Terms: `GLOSSARY.md` "Small lane".

## Problem Statement

A small bug has no light path. Today a developer gets one of two things:

- `/afk:diagnose` diagnoses and then fixes in the same run, so nobody approves the fix before code changes.
- `/afk:bug` runs a separate capture pipeline: a background fixer, a one-at-a-time queue, a local merge for re-test and its own tracker writes. That makes a second tracker writer next to `/afk:to-ticket`.

Neither path proves the bug is real against the specs before a fix. Neither leaves a record a ticket reader can act on without the code. The only other route is the full design chain (requirements grill, PRD, SDD, plan), and that is too heavy for a small bug.

## Solution

The small lane (the light path for a small bug) runs in 3 steps:

1. `/afk:diagnose` checks that the bug is real, compares it with the specs, reproduces it with a failing test, finds the root cause and writes a diagnosis with a verdict and a fix proposal. It never changes product code.
2. `/afk:fix` runs the diagnosis and asks the caller to approve the proposal. Then it fixes test-first, runs every verification tier, collects proof and ships a merge request.
3. `/afk:to-ticket` gains a bug and ad-hoc mode. It becomes the only skill that writes to the tracker.

`/afk:bug` is removed. A bug that needs design options or a product owner's call goes to a grill, which ends with a size call. Inside a bigger job, an agent fixes a defect in place with no diagnosis step. A defect outside the agent's slice gets a diagnosis and its own ticket, so the ticket stands alone.

## Catalog

### Diagnosis verdicts (V) — routes for a human caller

| ID | Verdict | Route |
|----|---------|-------|
| V-1 | real bug, obvious fix | the proposal goes to approval |
| V-2 | real bug, several possible fixes | a grill, which ends with a size call (G-1) |
| V-3 | spec gap | a grill with the product owner, which ends with a size call (G-1) |
| V-4 | works as specified | the fix stops; with approval, the diagnosis is posted on the ticket; a behaviour change is an enhancement ticket |
| V-5 | cannot reproduce | the fix stops; with approval, what was tried and what is needed are posted on the ticket |

G-1, the size call: a bug that is still small goes back to `/afk:fix`. A larger bug goes into the full chain until a medium lane exists (#108).

### Diagnosis kinds (K)

| ID | Kind | Reproduction | Clean copy of base branch | Spec comparison, root cause, diagnosis file |
|----|------|--------------|---------------------------|---------------------------------------------|
| K-1 | full diagnosis | built by diagnose as a failing test | yes, before it blames the code | yes |
| K-2 | light diagnosis | the reproduction the caller holds (a failing check or a finding) | no | yes |

### Where a bug is found (B) — what runs

| ID | Found as | Diagnosis | Fix | Who approves | Ticket + own merge request |
|----|----------|-----------|-----|--------------|----------------------------|
| B-1 | a bug a developer brings (ticket key or description) | K-1 | standalone fix | the developer | yes, shipped by the fix |
| B-2 | a check that fails on code the run just wrote | none | inside the build loop, one targeted retry | — | no |
| B-3 | a check still red after the retry | none | in-place fix | the agent caller, under `DECISIONS.md` | no |
| B-4 | a review finding that names a defect | none | in-place fix; a wrong finding is disputed in the settle loop | the agent caller, under `DECISIONS.md` | no |
| B-5 | an adversary finding | none | in-place fix; the finding's reproduction becomes the permanent test | the agent caller, under `DECISIONS.md` | no |
| B-6 | a red feature smoke gate | none | one in-place fix per failing scenario | the agent caller, under `DECISIONS.md` | no |
| B-7 | a failure that passes on re-run | none | never fixed by a product-code change; reported as flaky with both runs | — | no |
| B-8 | a bug a human reports while testing the feature branch | K-1 | lands on the feature branch | that human | no |
| B-9 | a defect outside the slice that blocks it | K-1 or K-2 | on its own branch and merge request off the base branch; the same fix goes on the feature branch | the agent caller, under `DECISIONS.md` | yes; the merge request links to the ticket |
| B-10 | a defect outside the slice that does not block it | K-1 or K-2 | none | — | ticket only |

### Proof (P)

| ID | Kind of proof |
|----|---------------|
| P-1 | the test that failed before the fix and passes after, with its output |
| P-2 | the result of every verification tier the fix ran |
| P-3 | a capture from the running app before and after the fix, or the request and response for an API bug |

## User Stories

1. As a developer, I run `/afk:fix` on a bug. It diagnoses the bug, I approve or steer the proposal, and it fixes test-first and runs every tier. Then it collects proof, files or updates the ticket and opens a ready merge request with a reviewer.
2. As a developer, I run `/afk:diagnose` with a ticket key or a description. I get a diagnosis with a verdict and a fix proposal, and no product code changes.
3. As an agent that implements a feature, I fix a check that stays red, or a finding that names a defect, in place with no diagnosis. I approve it under the decision protocol and ship it with the feature.
4. As a developer whose diagnosis finds several possible fixes or a spec gap, I go to a grill that ends with a size call.
5. As a developer whose diagnosis finds that the behaviour works as specified, the fix stops. To change the behaviour, I file an enhancement ticket with `/afk:to-ticket`, and that ticket needs a grill.
6. As a developer whose diagnosis cannot reproduce the bug, I get what was tried and what is needed. With my approval, it is posted on the ticket.
7. As a developer, I file a bug or an ad-hoc enhancement ticket with `/afk:to-ticket` from a diagnosis or a written description, also in the middle of a task.
8. As a developer who upgrades the plugin, I read in the release notes that `/afk:bug` is gone and `/afk:diagnose` no longer fixes. The notes also tell me how to clean up what the old pipeline left.

## Acceptance Criteria

### Diagnose

- [ ] AC-001 A `/afk:diagnose` run leaves product code unchanged; the only code it adds is the failing test that reproduces the bug.
- [ ] AC-002 A diagnose run accepts a ticket key or a written description. Without either, it asks for one and writes nothing.
- [ ] AC-003 A diagnosis holds the checked symptom, the spec comparison, the reproduction, the root cause, one verdict from V-1..V-5 and a fix proposal. A diagnosis that lacks any of these is incomplete, and `/afk:fix` refuses it.
- [ ] AC-004 Each fact in a diagnosis carries a mark that says how sure it is (the evidence-bundle grades).
- [ ] AC-005 A full diagnosis (K-1) reproduces the bug on a clean copy of the base branch before it names a root cause in the code.
- [ ] AC-006 A light diagnosis (K-2) names the reproduction it reused. It still records the spec comparison, the root cause and the verdict.
- [ ] AC-007 Diagnose gives a verdict only with a reproduction or a recorded failed attempt; with neither, it gives no verdict.
- [ ] AC-008 The diagnosis file is on disk in the ticket's spec folder before any tracker or forge call.
- [ ] AC-009 A standalone diagnose run works in its own worktree off the base branch. It keeps the failing test on a local branch, and the diagnosis names that branch.
- [ ] AC-010 A standalone diagnose run ends with the diagnosis, the verdict and the proposal, and offers the fix. It writes no ticket.

### Fix

- [ ] AC-011 `/afk:fix` changes no code without (a) a diagnosis with verdict V-1, or a V-2 or V-3 diagnosis whose grill sent the bug back, and (b) an approval of the proposal from the caller or a prior approval that covers it.
- [ ] AC-012 With verdict V-4, the fix stops with no code change. It posts the diagnosis on the ticket only after approval.
- [ ] AC-013 With verdict V-5, the fix stops with no code change. It posts what was tried and what is needed only after approval.
- [ ] AC-014 One approval on the proposal covers the code change, the ticket writes and the merge request. The fix asks no second time in the same run.
- [ ] AC-015 A steer on the proposal sends it back to diagnosis. No code changes until a revised proposal is approved.
- [ ] AC-016 The fix never approves its own proposal. An agent caller approves under `DECISIONS.md`. When the change is not easy to undo, or no option is a clear winner, the agent caller stops for the human.
- [ ] AC-017 The fix makes the diagnosis's failing test pass and runs every verification tier. It declares success only when every tier is green.
- [ ] AC-018 A standalone fix that succeeds leaves proof P-1, P-2 and P-3 on the ticket, and P-1 and P-2 plus a link to the ticket's proof on the merge request.
- [ ] AC-019 When no ticket exists, a standalone fix creates one after approval and before it changes code.
- [ ] AC-020 At the merge request, a standalone fix posts the merge request link and the proof on the ticket and moves the ticket to the configured in-review state.
- [ ] AC-021 A standalone fix ends at a merge request with tests passing. It flips the request to ready and adds a reviewer when one is configured. It never merges.
- [ ] AC-022 An in-place fix never commits, pushes, opens a merge request or writes a ticket. It returns today's outcomes and no diagnosis verdict.
- [ ] AC-023 A fix keeps escape analysis, spec reconciliation and the workflow lesson in both modes.
- [ ] AC-024 The fix runs in the current session. No background fix, one-at-a-time queue, local merge for re-test or push notification exists.

### Where a bug is found

- [ ] AC-025 For every row of catalog B, the diagnosis, fix, approver and ticket columns hold for a bug found that way.
- [ ] AC-026 B-9: the fix is on its own branch off the base branch with its own merge request, linked to its own ticket. The same change is on the feature branch, and the feature's merge request names the separate one as a dependency. Neither merge request is merged by an agent.
- [ ] AC-027 B-9 and B-10: the ticket holds the diagnosis and the proof, so a reader can act on it without the feature's context.
- [ ] AC-028 In a hands-off run, B-9 and B-10 write their tickets, and B-9 opens its separate merge request, without stopping for the human. Starting the run is the prior approval.
- [ ] AC-029 B-7: a failure that passes on re-run produces no product-code change; the report carries both runs.

### Grill size call

- [ ] AC-030 A grill that a bug was sent to (V-2, V-3) ends with a size call. A bug that is still small returns to `/afk:fix` with the grill's decision; a larger bug goes into the full chain.

### Tickets

- [ ] AC-031 `/afk:to-ticket` creates or updates a bug or ad-hoc ticket from a diagnosis or from a written description, on Jira and on GitHub Issues.
- [ ] AC-032 Ticket state changes use only the states and transitions in the repository's configuration. A transition not in the configuration is refused with no tracker write.
- [ ] AC-033 Evidence goes on the ticket as comments from the diagnosis and the proof.
- [ ] AC-034 On Jira, the bug mode asks for the fix version and backfills it. On GitHub Issues, it does not ask.
- [ ] AC-035 No skill other than `/afk:to-ticket` writes to the tracker.
- [ ] AC-036 A tracker write runs only with a human present or under a prior approval that covers ticket writes; otherwise it is refused with no write.
- [ ] AC-037 A ticket filed by the old `/afk:bug` pipeline is fixed when its key is passed to `/afk:fix`, with no migration step.

### Removal and release

- [ ] AC-038 After the change, no reference to `/afk:bug` remains outside `CHANGELOG.md`, and `/afk:setup audit` passes.
- [ ] AC-039 The change ships in a major release. Invoking `/afk:bug` after it finds no skill and no alias.
- [ ] AC-040 The developer settings that `/afk:bug` documents keep their names and meaning; their documentation has a new home.
- [ ] AC-041 The release notes state that `/afk:bug` is gone and `/afk:diagnose` no longer fixes. They also give the clean-up steps for bugs and worktrees the old pipeline left in flight.

## Access & validation policy

| Capability | Permitted | Denied | Data scope | Key validation rules |
|------------|-----------|--------|------------|----------------------|
| Run `/afk:diagnose` | developer; agent caller (light or full diagnosis, B-8..B-10) | none denied by role; product-code change denied to every caller (AC-001) | unscoped: one repository | ticket key or description required (AC-002); verdict needs reproduction or a recorded attempt (AC-007) |
| Approve a fix proposal | the caller: developer, human tester (B-8), agent caller under `DECISIONS.md` | the fix itself (AC-016); an agent caller on a change not easy to undo or with no clear winner | unscoped | AC-011, AC-015 |
| Change code with `/afk:fix` | after approval or prior approval | any caller without a diagnosis that found a real bug (AC-011) | unscoped | V-4 and V-5 stop the fix (AC-012, AC-013) |
| Ship a merge request | standalone fix; B-9 separate merge request | in-place fix (AC-022); merge by any agent (AC-021, AC-026) | unscoped | tests passing (AC-021) |
| Write to the tracker | `/afk:to-ticket` with a human present or under prior approval that covers ticket writes | every other skill (AC-035); a run with neither a human nor that prior approval (AC-036) | unscoped: the repository's one configured tracker project | configured states only (AC-032) |

## Implementation Decisions

| Module | Responsibility |
|--------|----------------|
| M1 `/afk:diagnose` | Rewritten without its fix phases. Writes the diagnosis (K-1, K-2). Runs in its own worktree when it runs alone. Stays user-invocable. |
| M2 `/afk:fix` | Diagnose, then approval, test-first fix, every tier, proof (P), then ship (standalone) or return (in place). Keeps escape analysis, spec reconciliation and the workflow lesson. |
| M3 shared markdown | The diagnosis format, the verdict routes (V), the approval rule and proof (P), each in one file that the skills point at. No new skill. |
| M4 `/afk:to-ticket` bug and ad-hoc mode | Creates or updates a ticket, applies configured states and posts evidence comments, on Jira and GitHub Issues. On Jira, it asks for the fix version and backfills it. |
| M5 `/afk:bug` removal | Removes the skill and every reference (AC-038), moves the documentation of the developer settings, rewrites the tracker-boundary text and adds a major changelog entry. |
| M6 callers | `/afk:execute`, `/afk:preflight`, `/afk:smoke-test` and `/afk:autopilot` route B-2..B-10. |
| M7 grills | A grill that a bug was sent to ends with the size call (G-1). |

Decisions:

- Diagnose and fix split: diagnose never fixes; fix runs diagnose. → [ADR-0001](adr/requirements/0001-diagnose-never-fixes.md)
- One consent rule for code, ticket writes and merge requests; the caller approves; prior approval stands in. → [ADR-0002](adr/requirements/0002-one-consent-rule.md)
- `/afk:to-ticket` is the only tracker writer; `/afk:bug` is removed with no alias. → [ADR-0003](adr/requirements/0003-to-ticket-sole-tracker-writer.md)
- No diagnosis step for a bug inside a bigger job. → [ADR-0004](adr/requirements/0004-no-diagnosis-inside-a-bigger-job.md)
- A defect outside the slice gets a diagnosis and its own ticket; a blocking one also gets its own merge request. → [ADR-0005](adr/requirements/0005-defect-outside-the-slice.md)
- The small lane takes bugs only; an enhancement always goes to a grill. → [ADR-0006](adr/requirements/0006-bugs-only-in-the-small-lane.md)
- The fix runs in the current session; the background fixer, the queue, the local merge and notifications go. → [ADR-0007](adr/requirements/0007-fix-runs-in-the-current-session.md)
- Mid-task capture is a ticket filed by `/afk:to-ticket` from a description; diagnosis and fix run later.
- A diagnosis is published to the ticket and linked from the merge request.
- Staples: none; this repository has no `STAPLES.md`. Staple candidate: none.

## Testing Decisions

- Test behaviour seen from outside: what a script writes to a stub tracker or forge, what a validator accepts or refuses. Do not test prose wording.
- M4: script tests against stub trackers for create, update, configured states, evidence comments and the fix-version backfill, on Jira and GitHub Issues. Prior art: the existing to-ticket and tracker adapter tests under `scripts/tests/`.
- M5: a check that fails while any `/afk:bug` reference survives outside `CHANGELOG.md`, plus `/afk:setup audit`.
- M3: a validator for the diagnosis sections and verdict (AC-003), when the design makes the format script-checked.
- M6: plan and contract validator cases for the B-9 and B-10 routes, where a script reads them.
- M1, M2, M7 prose: covered by the existing gates (skill registry, genericity, wiring, native contract).
- Every test runs on Windows and on WSL before push.

## Out of Scope

- Medium and large lanes, and the multi-session decision map → #108.
- A logic branch for `/afk:prototype` → a later feature.
- Migration of tickets filed by the old pipeline → none; AC-037 covers them.
- Small enhancements → an enhancement is never small (ADR-0006).

## Further Notes

- Reconciled: the round 2 rule "a tracker write happens only from a human-present run" is replaced by AC-036. Round 3 added prior approval that covers ticket writes. Round 5 made the start of a hands-off run that prior approval.
- Reconciled: the round 3 routes for an agent caller, and the works-as-specified outcome for an agent caller, are dropped. With no diagnosis inside a bigger job, no verdict reaches an agent caller (round 5).
- Reconciled: the round 5 rule for B-10 ("ticket, no fix") gains a diagnosis in round 6.
- Not settled in the grill, for `/afk:grill-solution`: the route for B-9 or B-10 when the agent's diagnosis gives V-2..V-5. Inferred default: `DECISIONS.md` applies; a non-obvious case parks for the human.
- Not settled in the grill, for `/afk:grill-solution`: which actor commits the B-8 fix on the feature branch. AC-022 forbids the in-place fix to commit.
- Known limit: a grilled bug that is too large for the small lane goes into the full chain until #108 ships.
- ADR-0001 of the plugin (the 2-writer tracker boundary) has no file. Its rule changes with ADR-0003 of this feature.
