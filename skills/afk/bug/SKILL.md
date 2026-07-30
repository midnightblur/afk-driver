---
name: bug
description: Capture a bug mid-task without losing your place, file it to Jira, dispatch an autonomous fixer, auto-retest. Use on /afk:bug — capture / dispatch / status / retest / purge.
---

# afk:bug — mid-task bug capture + autonomous fix pipeline

Five subcommands, one per verb of a bug's life:

| Subcommand | Does | Never |
|------------|------|-------|
| `capture` | Writes the evidence bundle + ledger entry to disk, then files a Jira Bug with the evidence embedded | Blocks on anything — not on config, not on a FixVersion answer |
| `dispatch` | Spawns an autonomous fixer in its own worktree off the source branch; delivers a Draft MR for a human to merge | Runs a second fixer while one is live; merges anything itself |
| `status` | Lists every in-flight bug with its lifecycle state; flags stranded fixes and unpublished captures; reconciles fixes that landed out-of-band | Writes any external side effect |
| `retest` | Re-runs the bug's reproduction once the fix lands in your branch; verifies or refutes | Edits any file |
| `purge` | Deletes a bug's on-disk directory (live or archived) — the only cleanup path | Auto-deletes anything |

This is the **public interface** (frozen — Software Design Document (SDD) §8): the subcommand set is exactly `capture / dispatch / status / retest / purge`.

A bug's whole world is one gitignored directory under `.claude/bugs/` in the main checkout. Its machine state, the S1–S10 lifecycle, the directory layout, and the archive/purge rules have **one home**: [LEDGER-FORMAT.md](LEDGER-FORMAT.md). The human-readable evidence dossier grammar has one home: [BUNDLE-FORMAT.md](BUNDLE-FORMAT.md). The per-developer config keys and their fail-closed rules have one home: [CONFIG.md](CONFIG.md). This file never restates any of them — it points, and orchestrates.

## Binding invariants (SDD §6 — never violate)

Three invariants hold across every subcommand and every run:

1. **Capture is never lost.** The evidence bundle + ledger entry land on disk **before any external call** (Jira, git, network). A missing config, a Jira outage, a crash mid-publish — none of them can lose a capture.
2. **At most one live fixer.** Across *all* bugs, only one may be in the `fixing` state (LEDGER-FORMAT.md S4) at a time. The guard fires at **every** entry into `fixing` — a fresh `dispatch`, a queue promotion, a `blocked` → `fixing` resume, and a `refuted` → `fixing` re-dispatch alike: read every non-terminal ledger entry first, and if any bug already holds S4, the incoming one waits (`queued` S3, or a pending resume) instead of entering. A bug a fixer left `blocked` (S5), or left `failed` while still recorded `fixing` (S4), still owns its worktree — it **holds the lane** until it resumes, is re-dispatched, or is purged; the guard never hands S4 to a second bug behind its back.
3. **Single ledger writer.** Only the main interactive session writes any `state.json`. Publisher, fixer, and retester run as **subagents that only return results** — this session records them. No subagent prompt ever names a ledger path. Every write is a Catalog-A transition (an allowed edge in LEDGER-FORMAT.md's machine) plus one appended `history` event, never a silent field mutation.

State tokens below and every transition between them are defined and permitted **only** as LEDGER-FORMAT.md's state machine allows. A transition this file describes is legal only because that machine lists its edge.

## Subagent protocol (SDD §0, §5 — frozen)

Every heavy leg runs as a subagent so this session stays in control of the ledger and the conversation:

- **Publisher** — invokes `scripts/publish_bug.py` to do the Jira REST work; returns the created key (or a surfaced failure body).
- **Fixer** — spawned with [FIXER-PROMPT.md](FIXER-PROMPT.md); works only in its own worktree; returns exactly one trailing `BUGFIX:` line (grammar below).
- **Retester** — spawned with [RETEST-PROMPT.md](RETEST-PROMPT.md); runs the reproduction read-only; returns evidence (commands + output) and a claimed verdict for this session to spot-check.

**Authorization lives in the prompt, not the tool** (ADR-0003). A subagent prompt carries its own scope grant and procedure and is **blind to this skill** — it never references `/afk:bug`, this spine, or the ledger. The orchestrator parses **only** the subagent's trailing result line; everything above it is working notes. This session — never a subagent — records the outcome into `state.json`.

## Refuse hands-off invocation (PRD AC-019)

`capture` and `dispatch` are **interactive-only**. Invoked from a driven/hands-off run (an autopilot walk, a driven-mode execute), both **refuse** and stop — a background run must not file a Jira Bug or spawn a fixer without a human in the loop. Detect the driven context the same way the rest of the plugin does (the invoker declares it); on detection, report the refusal and do nothing else. `status`, `retest`, and `purge` are unaffected.

## `capture`

Freeze the bug where you stand, lose nothing, block on nothing.

1. **Write to disk first (S1).** Build the evidence bundle per [BUNDLE-FORMAT.md](BUNDLE-FORMAT.md). Create the bug directory, write `bundle.md` + `screenshots/`, and write `state.json` at `captured` with the first `history` event. This happens **before any external call** (invariant 1) and reads **no config** ([CONFIG.md](CONFIG.md): capture is never gated).
2. **Ask the FixVersion question — never block on it (AC-003).** Surface the inferred FixVersion candidates to the dev, but do not wait: an unanswered question still lets the ticket be created without a FixVersion. A late answer routes to the `backfill` path (below), which calls `publish_bug.py backfill`.
3. **Publish if config allows (S1 → S2).** Read `jiraAssignee` (K1); missing → fail closed per [CONFIG.md](CONFIG.md): the bug stays `captured` (S1) (AC-001). Present → spawn the **Publisher** subagent to run `scripts/publish_bug.py create` (assignee K1, evidence bundle, screenshots, optional FixVersion) then `transition` to Dev-Pending. Record the returned key: rename the bug directory to the Jira key and write the `published` (S2) transition. A surfaced Publisher failure leaves the bug `captured` with the error in `history` — the capture is intact; retry via `status`.
4. **Backfill (late FixVersion answer).** When the dev answers the FixVersion question after publish, spawn the Publisher to run `scripts/publish_bug.py backfill` for the recorded key; append a `history` event. No state change.

Return the bug's directory / key and its state so the dev can get back to what they were doing.

## `dispatch`

Hand a published bug to an autonomous fixer. Refused hands-off (above).

1. **Require a dispatchable bug (S2, or a re-dispatch of S10).** Dispatch operates on a `published` (S2) bug, or **re-dispatches** a `refuted` (S10) bug — re-dispatch is itself a guarded dispatch entry: it runs steps 2–7 below (so the one-fixer guard in step 2 covers the S10 → `fixing` entry) and **reuses the bug's existing worktree** (skip step 5 when `worktreePath` is already set). A bug still `captured` (S1) — e.g. publish was deferred by missing config — is **published first** (via the `capture` publish step); if it can't be published, dispatch is refused with the reason. Never transition `captured` → `fixing`: S1's only permitted edge is S2 (LEDGER-FORMAT.md).
2. **Enforce one live fixer (S3 vs S4).** Read every non-terminal ledger entry (invariant 2). Any bug already holding the S4 lane (`fixing`, or a `blocked`/`failed` bug that has not left it) → write this bug `queued` (S3) and stop; it auto-promotes when the lane is freed (step 7). Capture stays available throughout (AC-006).
3. **Resolve the base branch (AC-007).** The base is the current branch's open MR target. No open MR → **ask the dev**, showing merge-base candidates. Current branch is `master` or `rm-release/*` → it is itself the base.
4. **Guard the base (AC-008).** The base branch must exist on `origin`; if it doesn't, refuse dispatch with the reason — a fixer worktree off a non-existent base is not created.
5. **Create the fixer worktree (S4) (AC-009).** Read `worktreeBasePath` (K3); missing → fail closed per [CONFIG.md](CONFIG.md): dispatch refused, the bug stays `published` (S2). Run `scripts/create-worktree` for a fix branch off the base, passing `--no-open` so the **IDE is not launched** (a human running the same script still gets the IDE by default). Parse the script's last line: `WORKTREE_PATH=<abs>` on success, `ERROR=<reason>` on failure (contract in `scripts/create-worktree`). Record `worktreePath` + `baseBranch` and write the `fixing` (S4) transition.
6. **Spawn the fixer with its full input set.** Read `mrReviewer` (K2). Spawn a subagent with [FIXER-PROMPT.md](FIXER-PROMPT.md), filling **all** of the placeholders it declares: `{BUNDLE_PATH}` (the bug's `bundle.md`), `{WORKTREE_PATH}` + `{FIX_BRANCH}` (from step 5), `{BASE_BRANCH}` (the recorded base), and `{MR_REVIEWER}` (K2). K2 absent → fail closed per [CONFIG.md](CONFIG.md): pass an empty reviewer — the fix tops out at `fix-pushed` (S6), never `mr-ready` (S7); dispatch still proceeds. The fixer reproduces on the clean base first, fixes, tests, pushes, opens a Draft MR, babysits CI, and flips Ready — all inside its own worktree.
7. **Record the result, then promote.** Parse **only** the fixer's trailing `BUGFIX:` line and transition the ledger accordingly (grammar below). Then **promote the queue** — but only if that result **freed the lane**, i.e. it was `mr-ready` or `fix-pushed`; a `blocked` (S5) or `failed` (S4) result keeps it (invariant 2). Only when the lane is freed and a bug is `queued` (S3) do you take the next one to `fixing` (S4) and dispatch it.

## `status`

Read-only situational awareness; any session can pick up where another left off (AC-018).

- **List non-terminal bugs** with their Catalog-A state (LEDGER-FORMAT.md). Include **unpublished captures** (S1 with no `ticketKey`) so a capture stranded by missing config is visible and re-publishable.
- **Flag stranded fixes:** a bug in an in-flight state (`fixing`/`fix-pushed`) whose fixer subagent is no longer live (session died mid-fix). Report it as resumable — a later session re-dispatches into the **same** worktree rather than creating a new one.
- **Reconcile out-of-band landings:** if a fix branch's `fixSha` has become an ancestor of the dev's current `HEAD` via an external pull, move the bug to `awaiting-retest` (S8) so `retest` picks it up — this is how a pull (not a fast-path merge) triggers verification (AC-017).
- Retry a failed publish (S1 with a publish error in `history`) by re-running the Publisher.

Writes only `state.json` reconciling transitions (single-writer); no external side effect.

## `retest`

Verify the fix actually resolved the bug once it lands in the dev's branch. Auto-fires; never edits (AC-017, AC-020).

1. **Trigger on ancestry.** When a bug's `fixSha` becomes an ancestor of the dev's current `HEAD`, the bug is at `awaiting-retest` (S8). Own merges (the fast path below) reach S8 immediately; external pulls are reconciled by `status`.
2. **Spawn the retester** with [RETEST-PROMPT.md](RETEST-PROMPT.md), filling the placeholders it declares: `{BUNDLE_PATH}` (the bug's `bundle.md`, carrying the reproduction steps) and `{REPO_PATH}` (the dev's checkout now containing the fix). It re-runs the repro **read-only** and returns the commands it ran plus their output as evidence — **no file edits**.
3. **Spot-check, then transition.** The retester returns one trailing `RETEST: <passed|failed>` line ([RETEST-PROMPT.md](RETEST-PROMPT.md) owns that grammar) plus its evidence; this session maps it: `passed` → `verified` (S9), `failed` → `refuted` (S10). But `verified` (S9) requires the main agent's own spot-check of the evidence, not the subagent's bare claim — a `passed` line whose evidence you cannot confirm, or a **missing/unparseable** `RETEST:` line, is treated as **not verified**: the bug stays `awaiting-retest` (S8), resumable, never advanced to a terminal state on a claim alone. On a confirmed pass → `verified` (S9): archive the whole bug directory under `done/` and remove the fixer worktree (LEDGER-FORMAT.md). On `failed` → `refuted` (S10): notify the dev with the evidence and offer to re-dispatch — routed back through `dispatch` (step 1), so its one-fixer guard applies and the existing worktree is reused rather than a fresh S10 → `fixing` edge run unguarded.

**Fast path (AC-016).** On **explicit per-instance dev confirmation only**, `retest` may first do a **local merge** of the fix branch into the dev's current branch — nothing else. No confirmation → no merge. The MR is **left untouched**, still open and targeting the source branch. The local merge lands the fix (→ S8) and retest proceeds as above.

## `purge`

Explicit cleanup only (LEDGER-FORMAT.md purge rule): delete a bug's `{ticket}/` directory — live under `.claude/bugs/` or archived under `done/`. Nothing auto-deletes a bundle; `purge` is the single path that removes one, and it acts only on the bug the dev names.

## `BUGFIX:` result grammar (one home)

The **single home** for the fixer's result contract. The fixer subagent ends its return with exactly one line; this orchestrator parses **only** this line (SDD §0) and maps it to a ledger transition:

```
BUGFIX: <status> — <summary>
```

| `<status>` | Meaning | Ledger transition |
|------------|---------|-------------------|
| `mr-ready` | Fix + regression tests green in the worktree, pushed, MR pipeline green, MR flipped Ready with reviewer (K2) assigned | `fixing` → `fix-pushed` → `mr-ready` (S4→S6→S7) |
| `fix-pushed` | Fix + regression tests green, pushed, Draft MR open, but the MR stays Draft — pipeline not green (red or CI budget exhausted), or no reviewer configured (K2) | `fixing` → `fix-pushed` (S4→S6) |
| `blocked` | The fixer needs a dev decision — a structured question, **including** "only reproduces with work-in-progress" when the bug did not reproduce on the clean base (AC-010) | `fixing` → `blocked` (S4→S5); resumes to `fixing` on the dev's answer |
| `failed` | Unrecoverable fixer error (the pipeline could not be run at all); the worktree is left for inspection | stays `fixing` (S4), keeps the lane (invariant 2); surfaced + stranded-visible via `status` |

`<summary>` is one plain-terms clause. The fixer's own file ([FIXER-PROMPT.md](FIXER-PROMPT.md)) is the authority on *how* it earns each status; this table is the authority on the **token set** the orchestrator accepts. A returned token outside this set is a `failed` (unparseable result).

## Push notifications (SDD §5, REPORTING.md)

The dev is often away while a bug is in flight, so the transitions that need a human push a notification (carrying subject + status + one plain-terms sentence, per REPORTING.md's push-notification rule — never a bare status token):

- **`blocked` (S5)** — the fixer asked a question; the dev's answer resumes the same fixer with context intact.
- **`refuted` (S10)** — retest failed; the fix did not resolve the bug; re-dispatch is offered.
- **`mr-ready` (S7)** — the fix is pushed, green, and Ready for the dev to review and merge.
- **park** — a `fix-pushed` (S6) outcome the fixer had to park because CI could not be confirmed green (pipeline red, or the CI budget elapsed): the fix is pushed and the MR is left Draft, waiting on the dev (SDD §5/§7 park event).

Every terminal `/afk:bug` report follows the layered shape in REPORTING.md (plugin root): the structured headline, one `In plain terms:` sentence, then the pointer to the bug directory.

## Hard rules

Bare pointers — each rule is stated once, above, at its point of use:

- **Invariants 1–3** (capture-before-external, one-live-fixer, single-writer) hold everywhere — see "Binding invariants".
- **Never merge for the dev** (AC-011) — see the `dispatch` subcommand-table row and [FIXER-PROMPT.md](FIXER-PROMPT.md); the human owns the merge.
- **Fail closed on config** — per [CONFIG.md](CONFIG.md); capture alone is never gated.
- **Refuse hands-off `capture` + `dispatch`** (AC-019); `status`/`retest`/`purge` stay available.
- **Point, never restate** — the state machine, bundle grammar, and config keys live in their format siblings ([LEDGER-FORMAT.md](LEDGER-FORMAT.md) / [BUNDLE-FORMAT.md](BUNDLE-FORMAT.md) / [CONFIG.md](CONFIG.md)); reference by path, never copy a table.
