---
name: execute
description: Execute one subtask from a local plan end-to-end interactively — read its contract from plan/NNNN-slug.md, design, develop under TDD, run every declared verification tier, commit, push, update the Draft MR, and advance the subtask's row in PLAN.md — then stop at CR/Merge for the human. You run this yourself in a session on the parent branch; there is no autonomous driver and no Jira. Reports a structured outcome.
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

   **Cited mode** (non-empty `## Design refs` + a `## Parent SDD`): the SDD/ADRs
   constrain you.
   - Read every cited SDD section and ADR via `ctx_read` BEFORE planning.
   - Treat the SDD §8 public interface and the cited ADR patterns as **frozen** —
     no invented signatures, no silent pattern substitution.
   - Treat the `## Seams` rows as binding: a seam you `implement:` you also
     test (its seam-test is a `## Verification` row); a seam you `use:` you call
     across without changing its contract.
   - Executor latitude is below the line: file/package layout within the module,
     private helpers, internal naming, test fixtures, library call shape.

2. **Preflight: verify Consumed contracts (cited mode).** If `## Consumes` is
   non-empty, every line is `{PRODUCER-ID} {file-path}#{grep-anchor} —
   {description}`. For each:
   - `ctx_read` `{file-path}` (relative to the worktree root). Missing file →
     the producer hasn't landed what it promised → stop with `contract_mismatch`
     (carry `{PRODUCER-ID}`) **before any other work** — no status change, no
     commits, no verification runs.
   - `ctx_search` `{grep-anchor}` in `{file-path}`. Absent → producer drifted →
     same `contract_mismatch`.
   - Quote the offending bullet verbatim. **Do not retry, do not auto-correct the
     producer.** A `contract_mismatch` halts on purpose: the producer must be
     fixed (re-run it or emit a corrective subtask) first. Record the break in
     **both** subtask files' `## Implementation Notes` and set both rows in
     PLAN.md to `blocked(contract_mismatch: …)`.

3. **Status → `designing`.** Set this subtask's `Status` cell in the PLAN.md
   progress tracker to `designing` and stamp the `Last updated` date. (This
   replaces the old Jira Dev-Designing transition — it's a one-cell edit,
   preserve the rest of the table.)

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

   **Honor `## Produces` (cited mode).** Every declared artifact must exist on
   the branch by success. Step 9 greps every declared anchor right before the
   success exit and aborts with `produces_drift` if any are missing — drifting
   from your own declared contract is not survivable mid-session. If the declared
   signature turns out wrong, that's a `design_conflict`, not a license to change
   it silently.

7. **Push and update the Draft MR.** Push to the parent branch. Update the MR's
   auto-maintained checklist block (`<!-- afk:subtasks:start -->` …
   `<!-- afk:subtasks:end -->`) via `glab` so this subtask reads done —
   preserve everything outside the block verbatim.

8. **Status → `verifying`; run every Verification tier.** Flip the tracker cell
   to `verifying`. Run **every row** of the subtask's `## Verification` table —
   `static`, then `unit`, then `integration`, then `e2e/browser` as present.
   Each row's command must go green:
   - **static** — the compile/lint/type command AND a grep of every `## Produces`
     anchor (the symbols you declared must exist).
   - **unit / integration / e2e** — run the exact command. A seam-implementing
     subtask's seam-test (an integration/unit row) must assert on the
     framework's real output, not your DTO.
   If a tier fails, retry once with a targeted fix. Still red → stop with
   `test_fail` (or `build_fail` for a static/compile failure), naming the tier.
   Partial tier coverage is failure: a UI subtask whose e2e row is red is not
   `success`.

9. **Producer self-preflight on `## Produces` (cited mode).** Before declaring
   success, verify every artifact you declared lands on the branch. For each
   `{file-path}#{grep-anchor} — {contract}`:
   - `ctx_read` `{file-path}`; missing → `produces_drift`, quote the bullet, do
     not retry or amend silently.
   - `ctx_search` `{grep-anchor}`; absent → implementation diverged from the
     declared signature → `produces_drift`.
   - **JPA-entity pickup (core-services Java).** If `{file-path}` ends `.java`
     and contains `@Entity` / `@MappedSuperclass` / `@Embeddable`: a
     class-declaration grep hit is necessary but not sufficient. Confirm the
     class's package is reachable from the module's entity-scan config
     (`@EntityScan` / `entityPackages` / `hibernate.archive.autodetection`), then
     run the documented liquibase-hibernate7 pickup check (the subtask's
     integration-tier `## Verification` row) and inspect the generated diff — if
     it does not mention the new entity/column/table, the plugin isn't picking it
     up → `produces_drift`, naming the entity and the empty diff path.

   This is symmetric to Step 2's consumer-side preflight; without it, signature
   drift surfaces only at the next consumer — on the wrong subtask.
   `produces_drift` ("I didn't deliver the contract I declared, fix impl or
   re-slice") is **not** `design_conflict` ("the binding contract is wrong, route
   to grill-solution"). Pick the right one.

10. **Update Implementation Notes + tracker.** Append one note to this subtask
    file's `## Implementation Notes (auto-maintained)` block (preserve any human
    prose around it). Set the subtask's PLAN.md row `Status` to `done` and stamp
    the date.

11. **Stop at CR/Merge — the human decides.** Do **not** merge the MR yourself.
    Leave the Draft MR updated and the subtask `done` in the tracker, and report
    `success`. The human reviews the MR and merges out of band. Auto-merging is
    outside this skill's lane.

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
      targeted retry. Name the tier.
    - `timeout` — exited on a wall-clock cap.
    - `design_conflict` — cited mode. A binding SDD/ADR decision is wrong,
      infeasible, or contradicts reality. Name the SDD section / ADR + the
      concrete conflict; route the human to `/afk:grill-solution` for a
      superseding ADR before re-running.
    - `contract_mismatch` — cited mode. Step 2: an upstream `## Produces`
      artifact is missing or its anchor doesn't appear. Name the `{PRODUCER-ID}`
      and quote the bullet; record on both subtask files.
    - `produces_drift` — cited mode. Step 9: one of THIS subtask's own
      `## Produces` anchors doesn't appear in its file. Quote the bullet. Fix the
      impl OR re-emit the slice with a corrected `## Produces`.
    - `other` — unexpected failure.

## Conflict procedure (cited mode)

If the subtask has a `## Conflict procedure` block, follow it verbatim on a
binding-contract violation. The canonical flow:

1. Stop coding the moment you realize the SDD/ADR mandate is unimplementable or
   contradicts reality. Don't paper over it.
2. Stage no code; commit nothing under the conflict.
3. Report `design_conflict` quoting the SDD section + the conflict, and set the
   tracker row to `blocked(design_conflict: …)`.
4. Note it in the subtask's Implementation Notes and run `/afk:grill-solution`
   for a superseding ADR before re-running.

**Do NOT silently override the SDD/ADR.** Substituting a different pattern or
interface breaks the binding contract and produces work other subtasks can't
integrate with.

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
