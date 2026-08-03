---
name: execute
description: Runs one plan subtask end-to-end — design, TDD, gates, commit, push, Draft-MR — stopping at CR/Merge. Use on /afk:execute {NNNN-slug}, or when an invoker requests DRIVEN mode.
---

# afk:execute — run one subtask from the local plan

Run against a **single subtask** from the on-disk plan — interactively by default (`/afk:execute {NNNN-slug}`, cwd a worktree on the parent ticket's branch), or non-interactively when the invoker requests DRIVEN mode (below).

Everything **local**: contract, design docs, progress tracker live on disk under the ticket's `plan/` directory. Writes no Jira. SCM is **GitLab** (`glab` CLI) — the only external surface touched (push + Draft MR).

Before starting, ensure:

- cwd is a clean worktree on the parent branch (`kapteyn/development/{username}/{enh_id_lower}`). Create worktree + branch yourself if absent.
- A Draft MR for that branch exists (`glab mr create --draft` if not). Carries the auto-maintained subtask checklist block.

Job: take one subtask through `designing` → `developing` → `verifying` → `reviewing`, get **every declared verification tier green** and the independent review gate **settled** (every finding fixed or settled — `skills/afk/review/SETTLEMENT.md`), commit + push, update the Draft MR, advance its row in `PLAN.md`, then **stop**. CR/Merge is the human's call — see Step 12.

## Argument

A single subtask id — its filename stem under `plan/`, e.g. `0003-export-registry` (`.md` optional). Plan lives at the ticket's `{…}/{TICKET-ID}/plan/` directory; locate it relative to the worktree, or pass the full path.

## Driven mode

When the invocation says DRIVEN (invoker passes the flag plus a live-app base URL), run the identical contract with these deltas:

- **No human available.** Never pause for input; convert any would-be question into the closest structured failure outcome (Step 13) and stop.
- **Commit + push pre-authorized** by the invoker for this branch — the interactive no-auto-commit rule does not apply inside a driven run.
- **Mandated tiers are hard.** No `env-limited` waivers of any kind; a tier that cannot go green — environmental or not — is `test_fail`, not a waiver. Only waivers pre-declared in `VERIFICATION-PLAN.md` exist.
- **Step 10.5 (adversarial execution gate) mandatory.** On by default interactively too; only the human may skip it.
- Live surfaces (`api`, `e2e/browser`, Step 10.5) run against the invoker-provisioned instance at the passed base URL — never a developer's own running instance.

## Process

**Journal as you go.** Every tracker status flip (Steps 3, 5, 8, 10, 11), every push (Step 7), every gate verdict (Steps 10, 10.5), and the terminal outcome (Step 13) also lands as one appended line in `plan/JOURNAL.md` — format `skills/afk/to-subtasks/JOURNAL-FORMAT.md`; create the file with its header first if missing. Append-only: never edit or delete a prior line. Lets a human who wasn't watching reconstruct the run.

1. **Read the contract.** `ctx_read` `plan/{NNNN-slug}.md`; parse its sections against the subtask contract (`## Goal / Complexity / Design refs / Scope / Seams / Acceptance / Produces / Consumes / Verification / Context excerpts / Parent PRD / Parent SDD / Blocked by / Conflict procedure`; a missing `## Complexity` reads as `standard` — the field sizes the *spawning* orchestrator's dispatch, not this skill's behaviour; a missing `## Context excerpts` means an older plan — fall back to reading the parent docs below). Read `plan/PLAN.md` for rank order, `## Blocked by` graph, seam register. **`## Context excerpts` is your spec context** — the emitter selected the verbatim PRD/SDD/ADR passages this slice needs. Open the full `## Parent PRD` / `## Parent SDD` / cited ADRs **only** when a question the excerpts don't settle arises (an ambiguous Acceptance bullet, a seam the excerpts don't pin, a suspected excerpt-vs-source gap); that fallback read goes through an `afk-reader` digest per `DELEGATION.md` (plugin root).

   **Blocked-by guard.** If any id in this subtask's `## Blocked by` isn't `done` in the tracker, stop with `blocked(blocked_by: …)` naming the laggards — don't start a subtask whose prerequisites haven't landed. Read the graph as-is; a subtask blocked by every other simply runs last.

   If running in Cited mode, follow the additional steps in [CITED-MODE.md](CITED-MODE.md).

2. **Preflight: verify Consumed contracts (cited mode).** If running in Cited mode, follow the additional steps in [CITED-MODE.md](CITED-MODE.md).

3. **Status → `designing`.** `bash tools/payable/ai-agents/plugins/workflow/skills/afk/execute/scripts/plan-status.sh {plan-dir} {NNNN-slug} designing` — sets the row's `Status` cell + stamps the header `Last updated` date, touching nothing else; every later status flip uses the same script.

4. **Plan inside Scope.** Stay strictly within the `## Scope` globs. Check your diff against those globs and the forbidden-pattern list before committing — entity classes fine; hand-written `UpgradeGroup_*.java` / liquibase changesets / `db/changelog/*` edits are not (see Hard rules).

   **Design to the review bars.** For each design-level checklist in `tools/payable/ai-agents/plugins/workflow/skills/afk/review/checklists/{design-quality,domain-alignment,resilience,api-contract}.md`, read its `## Guardrails` digest **only if the planned slice can hit its activation trigger** (trigger table: `skills/afk/review/SKILL.md`, judged from this contract's `## Scope` / `## Seams` / `## Produces`; unsure → read it). These are the bars the slice is later reviewed against — holding the design to them now costs a rename; failing them at the gate costs a remediation cycle.

   **Hold the design against open lessons.** Run `bash tools/payable/ai-agents/plugins/workflow/hooks/lesson-digest.sh` from the repo root and honour every open lesson whose `target` overlaps this slice's Scope or tech surface (format: `skills/afk/lessons/LEDGER-FORMAT.md`) — a mistake repeated after its lesson is on file is a review finding waiting to happen.

5. **Status → `developing`; apply TDD.** `plan-status.sh {plan-dir} {NNNN-slug} developing`, then use `/afk:tdd`: failing test first, make it pass, refactor. The `## Verification` tiers are your green-bar checks (Step 8).

6. **Commit.** Each message starts with the subtask id in brackets: `[{NNNN-slug}] <message>`. Cross-module edits carry a marker comment in the added hunks (see Hard rules). **Every `git commit` in this skill runs the commit-time code gates** (maven-compile, java-format, ui-lint — `hooks/precommit-gates.sh`), so a commit touching `.java` takes minutes, not seconds: invoke it with an explicit **600000 ms tool timeout**. A commit that dies on the default timeout leaves the gates' verdict unknown and the work uncommitted — it is not a signal to retry with `--no-verify`. Same contract for every later commit in this skill (Steps 10, 11).

7. **Push and update the Draft MR.** Push to the parent branch. Update the MR's auto-maintained checklist block (`<!-- afk:subtasks:start -->` … `<!-- afk:subtasks:end -->`) via `glab` so this subtask reads done — preserve everything outside the block verbatim.

8. **Status → `verifying`; run every Verification tier.** `plan-status.sh {plan-dir} {NNNN-slug} verifying`. Run **every row** of the subtask's `## Verification` table — `static`, then `unit`, then `integration`, then `api`, then `e2e/browser` as present. Each row's command must go green:
   - **static** — the compile/lint/type command AND a grep of every `## Produces` anchor (declared symbols must exist).
   - **unit / integration / api / e2e** — run the exact command. A seam-implementing subtask's seam-test (an integration/unit row) must assert on the framework's real output, not your DTO. An **api**-tier row hits the endpoint over REST and asserts the real envelope + the below-the-UI authz guard. A live-surface tier (`api`, `e2e/browser`) needs its runtime up — bring it up per the tier's command. On a tier fail, retry once with a targeted fix. Still red → **route to `/afk:fix`** (wraps `/afk:diagnose` + proportional coverage, and on this unreleased feature reconciles any stale spec artifact), then re-run this subtask from Step 8. If `/afk:fix` returns `design_conflict`, follow the Step 13 `design_conflict` path instead. If it still can't get the tier green, stop with `test_fail` (or `build_fail` for a static/compile failure), naming the tier. Partial tier coverage is failure: a UI subtask whose e2e row is red is not `success`.

   Tiers with long output (suite runs, full builds) run via an `afk-runner` subagent per `DELEGATION.md` trigger 3 (plugin root); turn tiers green off its digest, dropping inline only for the focused fix-one-failure loop.

9. **Producer self-preflight on `## Produces` (cited mode).** If running in Cited mode, follow the additional steps in [CITED-MODE.md](CITED-MODE.md).

10. **Status → `reviewing`; review settle loop.** Every tier green (Step 8) and `## Produces` anchors confirmed (Step 9): `plan-status.sh {plan-dir} {NNNN-slug} reviewing`, then gate through the settle loop (`skills/afk/review/SETTLEMENT.md` — round structure, fix-or-dispute, dispute adjudication, referee-kept termination; **you are its referee**). Per round, run **`/afk:review {NNNN-slug} --tag r{n}`** — it spawns fresh, independent subagents (they never see your reasoning) across its concern roster (full on the first round; delta rounds consolidate to its delta roster — that skill owns the scaling) and is **read-only** — returning one verdict line: `REVIEW: <verdict> — crit=… high=… med=… low=… [findings: <path>]` (grammar owned by `/afk:review` — lockstep copy here because this step parses it). The loop, not any single verdict, decides the gate: every actionable finding — `medium`/`low` included — is fixed or disputed per SETTLEMENT.md until a round comes back with nothing actionable.

    - **Fix routing by `class`** (SETTLEMENT.md owns the loop; this table owns the routing):
      - `correctness` / `spec` (incl. a behaviour-risk refactor) → route to **`/afk:fix`** (diagnose-backed; adds the regression / behaviour-pinning test the gate demanded).
      - `compliance` / `smell` / `test` / `design` → fix **inline**: `plan-status.sh {plan-dir} {NNNN-slug} developing`, apply the fix within Scope, return.
      - `scope` → trim the out-of-scope change back inside the Scope globs; if the finding genuinely needs work **outside** Scope, stop with `blocked` per the Scope hard rule (not `review_fail`) so the human can re-slice.
      - `pattern-debt` → no routing, never gates — it lives in the review's debt ledger; leave it.
    - **Close each round**: commit the remediation (`[{NNNN-slug}] review fix: …`), push, update the MR checklist, and re-run only the **cheap re-verification** (SETTLEMENT.md step 7): the `static` tier (compile + `## Produces` anchor greps) plus the `unit`/`integration` rows covering the changed code — **never a live tier (`api`, `e2e/browser`) per round**. Then the next review round.
    - **Settled** (a round yields nothing actionable — everything fixed or settled) → if any remediation commit landed during the loop, re-run the remaining declared live tiers (`api`, `e2e/browser`) **once** now — one expensive pass total, not per round; a red routes per Step 8. Then proceed to Step 10.5.
    - **Stalemate** (SETTLEMENT.md's hard round cap reached with findings still open) → **stop with `review_fail`** — name the surviving findings and their `class`; do **not** mark the subtask `done`. Non-convergence at the cap is unusual — a human must look.
    - **Record outcomes per round** as SETTLEMENT.md step 7 defines (`plan/review/{NNNN-slug}-{base-short}-r{n}.outcomes.json`) — the per-criterion telemetry `/afk:retro` aggregates. A concluded finding that exposed a doctrine gap — an instruction that existed but was ignored, or one that should exist — is captured as a workflow lesson in the same breath, per `skills/afk/lessons/CAPTURE.md`.

    Standalone, `/afk:review` also runs on its own (`/afk:review {NNNN-slug}`) to audit a slice without gating.

10.5. **Adversarial execution gate.** Run **`/afk:adversary {NNNN-slug} {app-base-url}`** in a **fresh session/subagent that has not seen this run's reasoning, diff, or tests** (its information diet is its own hard rule). The app instance must serve this slice's code — bring it up via `tools/payable/ai-agents/plugins/workflow/hooks/app-start-gate.sh` if the invoker didn't provision one.

    - **`clean`** → proceed to Step 11.
    - **`findings`** with any `critical`/`high` → remediate by each finding's `class` with the same routing as Step 10 (`correctness`/`spec` → `/afk:fix`; `authz`/`robustness` → inline within Scope), commit, push, and **re-run from Step 8**. These cycles have their **own cap of 2** (the Step 10 settle loop keeps separate accounting); still `critical`/`high` after the cap → stop with `adversary_fail`. Findings only `medium`/`low` → treat like an advisory review (live in `plan/review/*.md`); add a brief MR note and proceed. **Corpus ratchet:** remediating a `critical`/`high` adversary finding includes landing its repro as a permanent scenario in the matching verification catalog (`api` or `ui-e2e` per the repro's modality, corpus convention per that catalog's `AUTHORING.md`) in the same remediation commit — the gate that caught it once must catch it forever, for every future feature. A remediated finding that exposed a doctrine gap is likewise captured as a workflow lesson per `skills/afk/lessons/CAPTURE.md` (the ratchet owns the test side; the lesson owns the doctrine side).
    - **`tainted`** / **`env_unreachable`** → respawn fresh / restore the app, then re-run the gate; don't proceed around it. **Cap at 2 such re-run attempts**: still `tainted` after the second → stop with `adversary_fail` (name the taint); still `env_unreachable` → stop with `blocked(env_unreachable: …)` naming what wouldn't come up.

    Mandatory in driven mode; on by default interactively (only the human may skip it).

11. **Reconcile the glossary, then update the tracker.** If implementation revealed a domain term's actual semantics differ from its `GLOSSARY.md` definition (owning glossary located via `GLOSSARY-MAP.md`; format per `/afk:glossary`), update the entry and commit it separately: `[{NNNN-slug}] glossary: <terms>`. Then `plan-status.sh {plan-dir} {NNNN-slug} done`. The subtask file round-trips verbatim — this skill writes no per-run note anywhere; the run's signals live in the PLAN.md `Status`/`blocked(…)` cell, `plan/JOURNAL.md`, and `plan/review/*.md`.

12. **Stop at CR/Merge — the human decides.** Do **not** merge the MR yourself. Leave the Draft MR updated and the subtask `done` in the tracker; report `success`. The human reviews the MR and merges out of band. Auto-merging is outside this skill's lane. Anything the plan defines beyond a single subtask — a feature-level gate the human runs once all subtasks are `done` — is likewise not yours to trigger.

13. **Report the structured outcome.** End with a one-line outcome so the human (or an orchestrator) tells `success` from a structured failure at a glance. The same status drives the PLAN.md `Status` cell (`done` on success, `blocked(<status>: …)` otherwise):

    ```
    In plain terms: <one jargon-free sentence — what happened and its consequence for the reader>
    Journal: plan/JOURNAL.md · Contract: plan/{NNNN-slug}.md
    OUTCOME: <status> — <one-line summary> [producer: <PRODUCER-ID|none>]
    ```

    The plain-terms sentence and pointer lines follow the reporting protocol (`REPORTING.md` at the plugin root); the `OUTCOME:` line stays **last** so an orchestrator can parse the trailing line.

    | Status | Meaning / next action |
    |---|---|
    | `success` | Every Verification tier green, Step 10 settle loop settled (every finding fixed or settled), Step 10.5 adversarial gate `clean` (or medium/low-only findings, when the gate ran), code committed + pushed, MR updated, subtask `done`. Human handles CR/Merge. |
    | `test_fail` / `build_fail` | A Verification tier stayed red after one targeted retry **and** an `/afk:fix` pass (Step 8). Name the tier. |
    | `review_fail` | Step 10: the review settle loop hit its hard round cap with findings still open — stalemate (`skills/afk/review/SETTLEMENT.md`). Unusual by construction; a human must look. Name the surviving findings + their `class`. Set this row `blocked(review_fail: …)`. |
    | `adversary_fail` | Step 10.5: the adversarial execution gate still reports `critical`/`high` findings after its remediation cap. Name each finding + its `class` + repro path. Set this row `blocked(adversary_fail: …)`. |
    | `blocked_by` | Step 1: a `## Blocked by` prerequisite isn't `done` yet. Name the laggards; set this row `blocked(blocked_by: …)`. Run the prerequisites first. |
    | `timeout` | Exited on a wall-clock cap. |
    | `other` | Unexpected failure. |

    Cited-mode statuses (`design_conflict`, `contract_mismatch`, `produces_drift`) are defined in [CITED-MODE.md](CITED-MODE.md).

## Conflict procedure (cited mode)

If running in Cited mode, follow the additional steps in [CITED-MODE.md](CITED-MODE.md).

## Hard rules (inherited from core-services CLAUDE.md)

- **Never alter DB directly.** Add JPA entities; let liquibase-hibernate7 pick them up. No hand-written `UpgradeGroup`, `PreDbMigration`, or `db/changelog/*` edits. In cited mode Step 9's pickup check enforces this (`@Entity` without a passing pickup-verification run is `produces_drift`, not success); in uncited mode the guard is the static tier plus Step 4's diff check against the forbidden-pattern list.
- **Never auto-commit outside this AFK lane.** This skill is the *only* context where the agent commits autonomously.
- **Cross-module edits need marker comments.** A ticket-prefixed line like `// {TICKET-ID}: shared helper added` in the added hunks of any file outside the home module.
- **No `--no-verify`, no `--force`, no global git config changes.**
- **Stay inside Scope globs.** If work requires going outside, stop with detail on what was needed and why.
- **Negative existence claims are verified, never inferred.** Before writing "backend field/symbol X doesn't exist" into code, a test, or a doc (e.g. an exclusion comment), check the **generated** artifacts — the generated TS models (`target/typescript/backendModels.ts`), the APT output under `target/generated-sources/annotations` — and the declaring class's **full inheritance chain**, not just its hand-written source. Cite the checked artifact where the claim lands. A plausible inference shipped as a documented, tested-for exclusion is worse than no exclusion.
- **Sweep siblings of a pattern fix.** When a change fixes one instance of a repeated component/pattern (sibling grids, twin view/provider pairs), enumerate the siblings sharing the shape: apply the same fix to those inside Scope; name the out-of-scope ones in the outcome report as a surfaced gap. Never leave a twin silently unswept or "excluded" without the verified reason above.
- **Run every subtask uniformly from its contract** — including one whose `## Goal` says to invoke another skill: invoke that skill as written; don't recognize a subtask by kind, hand-write its output, or reimplement what it delegates to.
- **Only the tracker's Status column and the MR checklist block are yours.** In PLAN.md edit only the working subtask's `Status` cell + the `Last updated` date; in the MR only the checklist block. Everything else — including the subtask file, which round-trips verbatim — is not yours to touch.
