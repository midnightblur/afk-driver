---
name: execute
description: Execute one subtask from a local plan end-to-end interactively — read its contract from plan/NNNN-slug.md, design, develop under TDD, run every declared verification tier, commit, push, update the Draft MR, and advance the subtask's row in PLAN.md — then stop at CR/Merge for the human. Use when the user runs `/afk:execute {NNNN-slug}` on the parent branch to build one planned subtask, or when `/afk:fix` routes a stuck verification tier back to it. You run this yourself; there is no autonomous driver and no Jira. Reports a structured outcome.
---

# afk:execute — run one subtask from the local plan interactively

Run this skill yourself, in a Claude Code session, against a **single subtask** from the on-disk plan. No autonomous driver — invoke `/afk:execute {NNNN-slug}` from a session whose cwd is a worktree checked out on the parent ticket's branch.

Everything is **local**: contract, design docs, progress tracker all live on disk under the ticket's `plan/` directory. This skill writes no Jira. SCM is **GitLab** (`glab` CLI) — the only external surface it touches (push + Draft MR).

Before starting, ensure:

- cwd is a clean worktree on the parent branch (`mvu/afk/{ticket-id}`). Create worktree + branch yourself if it doesn't exist yet.
- A Draft MR for that branch exists (`glab mr create --draft` if not). The MR carries the auto-maintained subtask checklist block.

Your job: take one subtask through `designing` → `developing` → `verifying` → `reviewing`, get **every declared verification tier green** and the independent review gate `clean`/`advisory`, commit + push, update the Draft MR, advance its row in `PLAN.md`, then **stop**. CR/Merge is the human's call — see Step 12.

## Argument

A single subtask id — its filename stem under `plan/`, e.g. `0003-export-registry` (`.md` optional). The plan lives at the ticket's `{…}/{TICKET-ID}/plan/` directory; locate it relative to the worktree, or pass the full path.

## Process

1. **Read the contract.** `ctx_read` `plan/{NNNN-slug}.md`; parse its sections against the subtask contract (`## Goal / Design refs / Scope / Seams / Acceptance / Produces / Consumes / Verification / Parent PRD / Parent SDD / Blocked by / Conflict procedure / Implementation Notes`). Read `plan/PLAN.md` for rank order, the `## Blocked by` graph, the seam register. Read the `## Parent PRD` file.

   **Blocked-by guard.** If any id in this subtask's `## Blocked by` isn't `done` in the tracker, stop with `blocked(blocked_by: …)` naming the laggards — don't start a subtask whose prerequisites haven't landed. Read the graph as-is; a subtask blocked by every other simply runs last.

   If running in Cited mode, follow the additional steps in [CITED-MODE.md](CITED-MODE.md).

2. **Preflight: verify Consumed contracts (cited mode).** If running in Cited mode, follow the additional steps in [CITED-MODE.md](CITED-MODE.md).

3. **Status → `designing`.** Set this subtask's `Status` cell in the PLAN.md progress tracker to `designing`; stamp the `Last updated` date. One-cell edit — preserve the rest of the table.

4. **Plan inside Scope.** Stay strictly within the `## Scope` globs. Check your diff against those globs and the forbidden-pattern list before committing — adding entity classes is fine; hand-written `UpgradeGroup_*.java` / liquibase changesets / `db/changelog/*` edits are not (see Hard rules).

5. **Status → `developing`; apply TDD.** Flip the tracker cell to `developing`, then use `/afk:tdd`: failing test first, make it pass, refactor. The `## Verification` tiers are your green-bar checks (Step 8).

6. **Commit.** Each message starts with the subtask id in brackets: `[{NNNN-slug}] <message>`. Cross-module edits carry a marker comment in the added hunks (see Hard rules).

   If running in Cited mode, follow the additional steps in [CITED-MODE.md](CITED-MODE.md).

7. **Push and update the Draft MR.** Push to the parent branch. Update the MR's auto-maintained checklist block (`<!-- afk:subtasks:start -->` … `<!-- afk:subtasks:end -->`) via `glab` so this subtask reads done — preserve everything outside the block verbatim.

8. **Status → `verifying`; run every Verification tier.** Flip the tracker cell to `verifying`. Run **every row** of the subtask's `## Verification` table — `static`, then `unit`, then `integration`, then `api`, then `e2e/browser` as present. Each row's command must go green:
   - **static** — the compile/lint/type command AND a grep of every `## Produces` anchor (declared symbols must exist).
   - **unit / integration / api / e2e** — run the exact command. A seam-implementing subtask's seam-test (an integration/unit row) must assert on the framework's real output, not your DTO. An **api**-tier row hits the endpoint over REST and asserts the real envelope + the below-the-UI authz guard — needs a running backend. Any tier whose command drives a live surface (`api`, `e2e/browser`) needs its runtime up first — bring up whatever that row's command requires (running backend, app, token/env) before running it, exactly as the tier's command specifies. If a tier fails, retry once with a targeted fix. Still red → **route to `/afk:fix`** (it wraps `/afk:diagnose` + proportional coverage, and on this unreleased feature reconciles any stale spec artifact), then re-run this subtask from Step 8. If `/afk:fix` returns `design_conflict`, follow the Step 13 `design_conflict` path instead. If it still can't get the tier green, stop with `test_fail` (or `build_fail` for a static/compile failure), naming the tier. Partial tier coverage is failure: a UI subtask whose e2e row is red is not `success`.

9. **Producer self-preflight on `## Produces` (cited mode).** If running in Cited mode, follow the additional steps in [CITED-MODE.md](CITED-MODE.md).

10. **Status → `reviewing`; independent review gate.** Every tier is green (Step 8) and the `## Produces` anchors confirmed (Step 9) — but green tiers don't prove the code honours the CLAUDE.md rules, covers the whole spec, or is free of risky refactoring. Flip the tracker cell to `reviewing` and run **`/afk:review {NNNN-slug}`** before declaring done. It spawns fresh, independent subagents (they never see your reasoning) across the seven concerns and is **read-only** — it returns one verdict line: `REVIEW: <verdict> — crit=… high=… med=… low=… [findings: <path>]`.

    - **`clean`** → proceed to Step 11.
    - **`advisory`** (only `medium`/`low`) → don't block on nits. Carry the findings into Step 11's `## Implementation Notes` note and add a brief MR note, then proceed to Step 11.
    - **`blocking`** (any `critical`/`high`) → remediate **by each finding's `class`**, then re-verify:
      - `correctness` / `spec` (incl. a behaviour-risk refactor) → route to **`/afk:fix`** (diagnose-backed; it adds the regression / behaviour-pinning test the gate demanded).
      - `compliance` / `smell` / `test` → fix **inline**: flip the cell back to `developing`, apply the fix within Scope, return.
      - `scope` → trim the out-of-scope change back inside the Scope globs; if the finding genuinely needs work **outside** Scope, stop with `blocked` per the Scope hard rule (not `review_fail`) so the human can re-slice.
      - Commit the remediation (`[{NNNN-slug}] review fix: …`), push, update the MR checklist, and **re-run from Step 8** (tiers → preflight → this gate).
    - **Cap at 2 review cycles.** If the gate is still `blocking` after the second remediation, **stop with `review_fail`** — name the surviving `critical`/`high` findings and their `class`; do **not** mark the subtask `done`.

    Standalone, `/afk:review` is also runnable on its own (`/afk:review {NNNN-slug}`) to audit a slice without gating.

11. **Update Implementation Notes + tracker.** Append one note to this subtask file's `## Implementation Notes (auto-maintained)` block (preserve any human prose around it) — include any `advisory` review findings from Step 10. Set the subtask's PLAN.md row `Status` to `done`; stamp the date.

12. **Stop at CR/Merge — the human decides.** Do **not** merge the MR yourself. Leave the Draft MR updated and the subtask `done` in the tracker; report `success`. The human reviews the MR and merges out of band. Auto-merging is outside this skill's lane. Anything the plan defines beyond a single subtask — a feature-level gate the human runs once all subtasks are `done` — is likewise not yours to trigger. Run **every** subtask uniformly from its contract, including one whose `## Goal` says to invoke another skill: invoke that skill as written — don't recognize a subtask by kind, hand-write its output, or reimplement what it delegates to.

13. **Report the structured outcome.** End with a one-line outcome so the human (or an orchestrator) tells `success` from a structured failure at a glance. The same status drives the PLAN.md `Status` cell (`done` on success, `blocked(<status>: …)` otherwise):

    ```
    OUTCOME: <status> — <one-line summary> [producer: <PRODUCER-ID|none>]
    ```

    | Status | Meaning / next action |
    |---|---|
    | `success` | Every Verification tier green, the Step 10 review gate `clean`/`advisory`, code committed + pushed, MR updated, subtask `done`. The human handles CR/Merge. |
    | `test_fail` / `build_fail` | A Verification tier stayed red after one targeted retry **and** an `/afk:fix` pass (Step 8). Name the tier. |
    | `review_fail` | Step 10: the independent review gate stayed `blocking` after two remediation cycles. Name the surviving `critical`/`high` findings + their `class`. Set this row `blocked(review_fail: …)`. |
    | `blocked_by` | Step 1: a `## Blocked by` prerequisite isn't `done` yet. Name the laggards; set this row `blocked(blocked_by: …)`. Run the prerequisites first. |
    | `timeout` | Exited on a wall-clock cap. |
    | `other` | Unexpected failure. |

    Cited-mode statuses (`design_conflict`, `contract_mismatch`, `produces_drift`) are defined in [CITED-MODE.md](CITED-MODE.md).

## Conflict procedure (cited mode)

If running in Cited mode, follow the additional steps in [CITED-MODE.md](CITED-MODE.md).

## Hard rules (inherited from core-services CLAUDE.md)

- **Never alter DB directly.** Add JPA entities; let liquibase-hibernate7 pick them up. No hand-written `UpgradeGroup`, `PreDbMigration`, or `db/changelog/*` edits. Step 9's pickup check enforces this — `@Entity` without a passing pickup-verification run is `produces_drift`, not success.
- **Never auto-commit outside this AFK lane.** This skill is the *only* context where the agent commits autonomously.
- **Cross-module edits need marker comments.** A ticket-prefixed line like `// {TICKET-ID}: shared helper added` in the added hunks of any file outside the home module.
- **No `--no-verify`, no `--force`, no global git config changes.**
- **Stay inside Scope globs.** If work requires going outside, stop with detail explaining what was needed and why.
- **Only the tracker's Status column and the auto-maintained blocks are yours.** In PLAN.md edit only the working subtask's `Status` cell + the `Last updated` date; in the subtask file only the `## Implementation Notes` block; in the MR only the checklist block. Everything else round-trips verbatim.
