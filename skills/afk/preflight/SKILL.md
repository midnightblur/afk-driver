---
name: preflight
description: The feature-level ship gate — refuses without a green smoke gate, merges master in (never rebases) behind an ancestry guard, re-runs validations + a fresh integrated review + a final seam check within a shared 2-cycle fix cap, commits ship evidence, and background-babysits CI to flip the Draft MR to Ready. Use when an invoker chains it after the smoke gate goes green, or to re-run `/afk:preflight {plan-dir}` by hand on a parked feature.
---

# afk:preflight — the feature-level ship gate

Runs once per feature, after every subtask is `done` **and** the feature
smoke gate is green. Definition: `GLOSSARY.md` (plugin root) — "Preflight" /
"CI-babysit". Invoked automatically once the smoke gate goes green, or run by
hand (`/afk:preflight {plan-dir}`) to resume a parked feature. Brings the
branch up to date, gets the whole feature independently reviewed and
seam-checked, records ship evidence, babysits CI until the Draft MR can flip to
Ready — then **stops**. Never merges the MR (CR/Merge stays the human's, same
boundary `/afk:execute` and `/afk:smoke-test` honor).

## Argument

`plan-dir` — path to the feature's `plan/` directory (`PLAN.md`, `JOURNAL.md`,
subtask contracts). Defaults to the plan dir of the current worktree's branch
when omitted and unambiguous.

## Refusal guard (runs before anything else)

Read `PLAN.md`'s header `Feature:` line. Anything other than
`complete (smoke green …)` or `complete (minimal gate, …)` → refuse
immediately: report `refused(no_green_smoke)` quoting the header line verbatim,
**write nothing** — no `## Preflight` section, no `plan/JOURNAL.md` line. The
one guard that must leave zero trace on disk; so a feature can never ship on a
gate that never ran.

## The `## Preflight` table (persisted state)

First run creates a `## Preflight` section in `PLAN.md` — skeleton in
`skills/afk/to-subtasks/PLAN-TEMPLATE.md`, columns
`# | Step | Status | Cycle | Evidence` (lockstep with the mission-control
renderer's gates panel, `skills/afk/mission-control/scripts/mc/panels/gates.py`
— that parser is the shape's other lockstep half; a column rename here is a
same-commit change there). One row per PF step below. This skill is the table's
sole writer; every other reader (renderer, human, orchestrating driver) only
reads it.

**Resume.** Re-run reads the table back first: rows already `green` are skipped;
execution resumes at the first non-`green` row. A crash or park never repeats a
completed step.

## The PF-1..7 ladder

Each step updates its table row (`Status` + `Evidence`) the moment it completes
— a crash between steps re-runs exactly the one in-flight step, never two.
`park(PF-n: reason)` always means: stop, notify per `REPORTING.md` (plugin
root), leave the MR Draft, leave every not-yet-reached row untouched.

**PF-1 — merge & ancestry guard.**
1. Record current `HEAD` (`git rev-parse HEAD`).
2. `git merge origin/master` — **never** `rebase`, **never** `--force` push
   (Hard rules below; binding requirement, not style).
3. Merge conflict → `park(PF-1: merge_conflict)` immediately — never
   auto-resolved, only a human untangles intent across two histories.
4. On a clean merge, **ancestry guard**: `git merge-base --is-ancestor
   {recorded-HEAD} HEAD` must succeed, confirming the pre-merge tip is still
   reachable — no rewritten history. Guard failure → `park(PF-1:
   ancestry_guard_failed)`, **before any push**.
5. Only once the guard passes: push (plain `git push`, the now-fast-forwarded
   remote tracking branch).

**PF-2 — validations.** Re-run the repo's mandated validation suite
(`build-scripts/run_validations.py` plus the reactor build, in core-services)
against the merged tip. A **mechanical** red (formatter, config-validation,
merge-induced compile break) is fixable within the shared cycle cap below. A
**semantic** red (a validation asserting something is actually wrong, not just
malformed) → `park(PF-2: semantic_red)` — never auto-fixed.

**PF-3 — fresh-context review.** Run **`/afk:review --feature`** against the
merged tip — the integrated feature diff as a whole (every subtask's changes
together, not one slice), reviewed by fresh contexts that haven't seen the
implementation's own reasoning, with the cross-slice design roster that skill's
`--feature` mode defines. Gate on its `REVIEW:` verdict line. `clean`/`advisory`
→ proceed. `blocking` → remediate by class within the shared cap
(`correctness`/`spec` → `/afk:fix`; `compliance`/`smell`/`test`/`design` →
inline fix; `pattern-debt` never blocks; `scope` is unreachable — the
`--feature` roster carries no scope concern); still blocking after the cap →
`park(PF-3: review_blocking)`. However the step ends, record each finding's
outcome in `plan/review/feature-{base-short}.outcomes.json`
(`fixed` / `dismissed(<reason>)` / `deferred`) — the caller-side half of the
review telemetry.

**PF-4 — seam check.** Run `/afk:verify-seams final` over the whole feature —
the orphan hunt classifying every produced artifact wired / weak / orphan,
blocking on open IOUs in final mode. `wired`/`weak` → proceed. An orphan or a
final-mode-blocking open IOU → same routing as PF-3 (remediate within the
shared cap, else `park(PF-4: orphan_artifact)`).

**PF-4b understanding — advisory artifact generation (never parks).** Reached
only once PF-4 is `green`. Invoke **`/afk:understand {plan-dir}`** in auto mode
(its own defaults — `skills/afk/understand/SKILL.md` M-1); it synthesizes the
feature's diff, journal, and review records into the checked-in understanding
artifact and rides this ladder's existing commit/push authorization for its one
docs-only commit (ADR `adr/design/0001`; SDD §3).

- **`generated`** → row `green`; record the committed artifact path in
  `Evidence` (PF-5's evidence block names it); proceed to PF-5.
- **`failed({reason})`** — or the `no_derivable_diff` refusal a live feature
  branch never reaches in auto mode — → row **`advisory-failed`** and proceed
  to PF-5 anyway. **Never `park`.** The skill has already written its own
  journal event; no fix attempt, no counter increment, no MR-block change.

This is an **advisory** row: it sits **outside the shared fix cap**
(PF-2/PF-3/PF-7), never consumes a cycle, and its only non-green outcome
(`advisory-failed`) advances the ladder rather than blocking it. On **resume**,
an `advisory-failed` (non-`green`) row re-runs like any other non-green row
(Resume rule above).

**PF-4c lessons — advisory open-drafts surface (never parks).** Run
`bash tools/payable/ai-agents/plugins/workflow/hooks/lesson-digest.sh --count`
from the repo root; set the row `green` with
`Evidence: open lessons: <n> (grammar: skills/afk/lessons/LEDGER-FORMAT.md)`.
This is how workflow-lesson drafts captured during hands-off runs reach the
human at the ship gate: `<n> > 0` changes nothing mechanically — the count
rides the PF table into the report and MR evidence block; applying the drafts
is `/afk:lessons apply`, never this ladder's job. Advisory like PF-4b: outside
the shared fix cap, no cycle, no fix attempt, no park.

**PF-5 — ship evidence.**
1. Render the mission-control end-state snapshot: invoke the renderer CLI in
   `--once` mode against this feature's spec folder (fronted by
   `/afk:mission-control {spec-folder} --once` — see that skill; it writes
   `{spec-folder}/plan/mission-control/index.html`, gitignored per
   `skills/afk/mission-control` doctrine).
2. Copy that rendered file to a **tracked** path outside the gitignored
   directory (e.g. `{spec-folder}/plan/SHIP-SNAPSHOT.html`) and commit it — the
   one moment the artifacts are frozen, so this copy can never go stale after
   (never re-derived afterward; nothing reads it back).
3. Update the MR's **own** evidence marker block —
   `<!-- afk:preflight-evidence:start -->` … `<!-- afk:preflight-evidence:end
   -->` — via `glab`, sibling to `/afk:execute`'s pre-existing
   `<!-- afk:subtasks:start/end -->` checklist block. **Replace only this
   block**; every other byte of the description — including the sibling block —
   round-trips verbatim (§9b two-writer invariant: each writer owns exactly one
   block). Content: PF table summary, the snapshot's committed path, a
   `plan/JOURNAL.md` pointer, and — when PF-4b is `green` — the committed
   understanding-artifact path (from that row's `Evidence`) so reviewers can
   discover it (SDD §5 observability).

**PF-6 — launch ci-wait.** Launch `scripts/ci-wait.sh {mr-ref} 5400 180
[repo]` (budget 5400 s / 90 min, interval 180 s / 3 min — `SDD §10`-class
numbers, not invented per-run) as a background Bash task; append the launch to
`plan/JOURNAL.md`. The calling session/turn ends here — whatever resumes it
(human, orchestrator) picks up the routing below once the task exits.
`ci-wait.sh`'s exit-code contract is documented where it's bundled:
`scripts/ci-wait.sh` (its own header comment is the canonical copy; this table
mirrors it — a lockstep pair, keep both in sync):

| Exit | Meaning |
|---|---|
| `0` (`EXIT_OK`) | pipeline reached `success` |
| `1` (`EXIT_RED`) | pipeline reached `failed`/`canceled` |
| `2` (`EXIT_BUDGET_EXHAUSTED`) | 90 min elapsed, pipeline still non-terminal — it keeps running; park ≠ cancel |
| `3` (`EXIT_FLAKE`) | 3 consecutive `glab` read errors — auth/network flake |

**PF-7 — CI outcome routing.**
- **exit 0** → `glab` Draft→Ready flip on the MR; JOURNAL `done`; every PF
  row green (PF-4b may be `advisory-failed` — advisory rows never block);
  report `success` (below) and stop.
- **exit 1** → inspect the pipeline log. Mechanical failure (compile/format/
  config, merge-induced) and cycles remaining → fix, push (**increment the
  shared cycle counter before the attempt**, not after), relaunch PF-6 — a
  fresh pipeline gets a fresh 90-min window. **CI-only test red or a
  secret-detection hit → immediate `park(PF-7: ci_test_red)` /
  `park(PF-7: secret_hit)` — never a fix attempt** (a red only CI sees when
  local tiers were green signals env/config drift; an unsupervised agent's
  likeliest "fix" is reshaping the test to pass, worse than waiting for the
  human).
- **exit 2** → `park(PF-7: budget_exhausted)` — the pipeline keeps running.
  Resume re-reads live pipeline status via `glab` **first**, so a pipeline
  that finished green while parked completes instantly without a wasted
  relaunch.
- **exit 3** → `park(PF-7: glab_flake)` — flakes never consume a fix cycle.

## Shared fix-cycle cap

PF-2, PF-3, PF-7 share **one** counter, capped at **2** per preflight run (not
2 each). Increment **before** each attempt, so a crash mid-fix still counts the
attempt on resume. Exhausted → the next would-be fix becomes a park at that
step, naming which step hit the cap.

## Hard rules

- **Merge only, never rebase, never `--force` push.** Rebasing rewrites hashes
  `plan/JOURNAL.md` and `plan/TRACE.md` recorded per subtask, silently
  orphaning both; force-pushing a shared MR branch detaches GitLab review
  comments. The ancestry guard (PF-1) makes this mechanical, not just a promise.
- **The ancestry guard runs before every push**, not only the first —
  re-running PF-1 on resume re-checks it against the freshly recorded HEAD.
- **CI-only test reds and secret-detection hits are never auto-fixed** — always
  an immediate park, at any cycle count.
- **The `## Preflight` table is this skill's alone to write.** Everything else
  in `PLAN.md` (progress tracker, smoke gate) round-trips verbatim.
- **The evidence marker block is this skill's alone to write.** Every other
  byte of the MR description — including `/afk:execute`'s checklist block — is
  preserved verbatim.
- **No `--no-verify`, no global git config changes** (repo-wide hard rule,
  inherited here without exception).

## Reporting

```
OUTCOME: <status> — <one-line summary>
In plain terms: <one jargon-free sentence — is the feature shipped, and if not, what's blocking>
Journal: {plan-dir}/JOURNAL.md
```

| Status | Meaning |
|---|---|
| `success` | Every PF row green — PF-4b may be `advisory-failed` (advisory rows never block); MR flipped Ready; ship snapshot committed. The human still merges out of band. |
| `refused(no_green_smoke)` | The Step-0 guard fired; quote the actual `Feature:` header line. Nothing was written. |
| `parked(PF-{n}: {reason})` | A PF step could not proceed (see each step's routing above); the MR stays Draft. Re-run this skill once the human resolves `{reason}`. |
| `other` | Unexpected failure — name it; leave the table as-is for the next resume. |

## Boundary

- **Feature-level only.** Chained once per feature after smoke-green, or run by
  hand — never per-subtask; `/afk:execute`'s own per-subtask tail (tiers →
  review → adversary → commit → push → Draft-MR checklist) is untouched.
- **Never merges the MR.** Flips Draft → Ready on green and stops; CR/Merge is
  the human's call, same as every other AFK skill.
- **Never rewrites history.** No rebase, no force-push, no amend — see Hard
  rules.
