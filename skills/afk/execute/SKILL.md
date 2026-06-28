---
name: execute
description: Execute one subtask from a local plan end-to-end interactively — read its contract from plan/NNNN-slug.md, design, develop under TDD, run every declared verification tier, commit, push, update the Draft MR, and advance the subtask's row in PLAN.md — then stop at CR/Merge for the human. Use when the user runs `/afk:execute {NNNN-slug}` on the parent branch to build one planned subtask, or when `/afk:fix` routes a stuck verification tier back to it. You run this yourself; there is no autonomous driver and no Jira. Reports a structured outcome.
---

# afk:execute — run one subtask from the local plan interactively

You run this skill yourself, in a Claude Code session, against a **single
subtask** from the plan `/afk:to-subtasks` emitted. There is no autonomous
driver — you invoke `/afk:execute {NNNN-slug}` from a session whose cwd is a
worktree checked out on the parent ticket's branch.

Everything is **local**: the contract, the design docs, and the progress tracker
all live on disk under the ticket's `plan/` directory. This skill writes no
Jira. The SCM is **GitLab** (`glab` CLI) and that is the only external surface
it touches (push + Draft MR).

Before you start, make sure:

- The cwd is a clean worktree on the parent branch (`mvu/afk/{ticket-id}`).
  Create the worktree + branch yourself if it doesn't exist yet.
- A Draft MR for that branch exists (`glab mr create --draft` if not). The MR
  carries the auto-maintained subtask checklist block.

Your job: take one subtask through `designing` → `developing` → `verifying`,
get **every declared verification tier green**, commit + push, update the Draft
MR, advance its row in `PLAN.md`, then **stop**. CR/Merge is the human's call —
see Step 11.

## Argument

A single subtask id — its filename stem under `plan/`, e.g. `0003-export-registry`
(the `.md` is optional). The plan lives at the ticket's
`{…}/{TICKET-ID}/plan/` directory; locate it relative to the worktree, or pass
the full path.

## Process

1. **Read the contract.** `ctx_read` `plan/{NNNN-slug}.md` and parse its sections
   against the subtask contract (`## Goal / Design refs / Scope / Seams /
   Acceptance / Produces / Consumes / Verification / Parent PRD / Parent SDD /
   Blocked by / Conflict procedure / Implementation Notes`). Read `plan/PLAN.md`
   for rank order, the `## Blocked by` graph, and the seam register. Read the
   `## Parent PRD` file.

   **Blocked-by guard.** If any id in this subtask's `## Blocked by` is not `done`
   in the tracker, stop with `blocked(blocked_by: …)` naming the laggards — don't
   start a subtask whose prerequisites haven't landed. The terminal
   `NNNN-smoke-e2e` / `NNNN-smoke-api` build subtasks are `Blocked by` every slice.

   If running in Cited mode, follow the additional steps in [CITED-MODE.md](CITED-MODE.md).

2. **Preflight: verify Consumed contracts (cited mode).** If running in Cited mode, follow the additional steps in [CITED-MODE.md](CITED-MODE.md).

3. **Status → `designing`.** Set this subtask's `Status` cell in the PLAN.md
   progress tracker to `designing` and stamp the `Last updated` date. It's a
   one-cell edit — preserve the rest of the table.

4. **Plan inside Scope.** Stay strictly within the `## Scope` globs. Check your
   diff against those globs and the forbidden-pattern list before committing —
   adding entity classes is fine; hand-written `UpgradeGroup_*.java` / liquibase
   changesets / `db/changelog/*` edits are not (see Hard rules).

5. **Status → `developing`; apply TDD.** Flip the tracker cell to `developing`,
   then use `/afk:tdd`: failing test first, make it pass, refactor. The
   `## Verification` tiers are your green-bar checks (Step 8).

6. **Commit.** Each message starts with the subtask id in brackets:
   `[{NNNN-slug}] <message>`. Cross-module edits carry a marker comment in the
   added hunks (see Hard rules).

   If running in Cited mode, follow the additional steps in [CITED-MODE.md](CITED-MODE.md).

7. **Push and update the Draft MR.** Push to the parent branch. Update the MR's
   auto-maintained checklist block (`<!-- afk:subtasks:start -->` …
   `<!-- afk:subtasks:end -->`) via `glab` so this subtask reads done —
   preserve everything outside the block verbatim.

8. **Status → `verifying`; run every Verification tier.** Flip the tracker cell
   to `verifying`. Run **every row** of the subtask's `## Verification` table —
   `static`, then `unit`, then `integration`, then `api`, then `e2e/browser` as
   present. Each row's command must go green:
   - **static** — the compile/lint/type command AND a grep of every `## Produces`
     anchor (the symbols you declared must exist).
   - **unit / integration / api / e2e** — run the exact command. A
     seam-implementing subtask's seam-test (an integration/unit row) must assert
     on the framework's real output, not your DTO. An **api**-tier row hits the
     endpoint over REST (`node --test` against `11700-payable/verification/api`,
     using `../core`, or a disposable probe importing `../core`) and asserts the
     real envelope + the below-the-UI authz guard — it needs a running backend.
     The terminal build subtasks run inside the in-tree
     `11700-payable/verification` module (paths relative to this same worktree —
     their specs land on this branch/MR like any other code): `NNNN-smoke-e2e`'s
     `static` tier is `cucumber-js --dry-run` (offline) and its `e2e/browser` tier
     (`npm run smoke`) needs a running app + the suite's env (auth/base-URL per
     `11700-payable/verification/ui-e2e/README.md`); `NNNN-smoke-api`'s `static`
     tier is `node --check` (offline) and its `api` tier (`node --test`) needs a
     running backend + a token (minted via `../core`). Bring those up before the
     tier, the same as `/afk:smoke-test` does.
   If a tier fails, retry once with a targeted fix. Still red → **route to
   `/afk:fix`** (it wraps `/afk:diagnose` + proportional coverage, and on this
   unreleased feature reconciles any stale spec artifact), then re-run this
   subtask from Step 8. If `/afk:fix` returns `design_conflict`, follow the
   Step 12 `design_conflict` path instead. If it still can't get the tier green,
   stop with `test_fail` (or `build_fail` for a static/compile failure), naming
   the tier. Partial tier coverage is failure: a UI subtask whose e2e row is red
   is not `success`.

9. **Producer self-preflight on `## Produces` (cited mode).** If running in Cited mode, follow the additional steps in [CITED-MODE.md](CITED-MODE.md).

10. **Update Implementation Notes + tracker.** Append one note to this subtask
    file's `## Implementation Notes (auto-maintained)` block (preserve any human
    prose around it). Set the subtask's PLAN.md row `Status` to `done` and stamp
    the date.

11. **Stop at CR/Merge — the human decides.** Do **not** merge the MR yourself.
    Leave the Draft MR updated and the subtask `done` in the tracker, and report
    `success`. The human reviews the MR and merges out of band. Auto-merging is
    outside this skill's lane. The **feature-level** smoke gate (the integrated
    browser journeys against a running app) is likewise not yours — when the plan
    has a `## Feature smoke gate` and every subtask is `done`, the human runs
    `/afk:smoke-test`. The terminal `NNNN-smoke-e2e` / `NNNN-smoke-api` subtasks
    (which *build* those specs from `VERIFICATION-PLAN.md`, following the canonical
    recipes at `11700-payable/verification/ui-e2e/AUTHORING.md` and
    `11700-payable/verification/api/AUTHORING.md`) are normal subtasks you run like
    any other; the gate that *runs* them integrated is the separate skill.

12. **Report the structured outcome.** End with a one-line outcome so the human
    (or an orchestrator) can tell `success` from a structured failure at a
    glance. The same status drives the PLAN.md `Status` cell (`done` on success,
    `blocked(<status>: …)` otherwise):

    ```
    OUTCOME: <status> — <one-line summary> [producer: <PRODUCER-ID|none>]
    ```

    - `success` — every Verification tier green, code committed + pushed, MR
      updated, subtask `done`. The human handles CR/Merge.
    - `test_fail` / `build_fail` — a Verification tier stayed red after one
      targeted retry **and** an `/afk:fix` pass (Step 8). Name the tier.
    - `blocked_by` — Step 1: a `## Blocked by` prerequisite isn't `done` yet.
      Name the laggards; set this row `blocked(blocked_by: …)`. Run the
      prerequisites first.
    - `timeout` — exited on a wall-clock cap.
    - Cited-mode statuses (`design_conflict`, `contract_mismatch`,
      `produces_drift`) are defined in [CITED-MODE.md](CITED-MODE.md).
    - `other` — unexpected failure.

## Conflict procedure (cited mode)

If running in Cited mode, follow the additional steps in [CITED-MODE.md](CITED-MODE.md).

## Hard rules (inherited from core-services CLAUDE.md)

- **Never alter DB directly.** Add JPA entities; let liquibase-hibernate7 pick
  them up. No hand-written `UpgradeGroup`, `PreDbMigration`, or `db/changelog/*`
  edits. Step 9's pickup check enforces this — `@Entity` without a passing
  pickup-verification run is `produces_drift`, not success.
- **Never auto-commit outside this AFK lane.** This skill is the *only* context
  where the agent commits autonomously.
- **Cross-module edits need marker comments.** A ticket-prefixed line like
  `// {TICKET-ID}: shared helper added` in the added hunks of any file outside
  the home module.
- **No `--no-verify`, no `--force`, no global git config changes.**
- **Stay inside Scope globs.** If the work requires going outside, stop with
  detail explaining what was needed and why.
- **Only the tracker's Status column and the auto-maintained blocks are yours.**
  In PLAN.md edit only the working subtask's `Status` cell + the `Last updated`
  date; in the subtask file only the `## Implementation Notes` block; in the MR
  only the checklist block. Everything else round-trips verbatim.
