---
name: smoke
description: The feature-level completion gate. After every subtask in a local plan is done, run the feature's browser smoke suite (e2e at 11700-payable/e2e) against a running app and, only on green, stamp the feature complete in PLAN.md. Distinct from the per-subtask e2e/browser tier — this verifies the integrated whole as a user would. Optional + human-gated: it runs only when /afk:to-subtasks emitted a `## Feature smoke gate` (smoke_e2e=yes). Also the human's standalone/manual runner; CI and scheduled jobs run the same suite directly. Touches no Jira and merges nothing. Use as the final acceptance check once a feature's subtasks have all landed, or to manually re-verify a feature's sanity.
---

# afk:smoke — the feature-level smoke gate

`/afk:execute` proves each subtask works in isolation: every declared
`## Verification` tier — including a per-subtask `e2e/browser` row when the
subtask touches UI — goes green before that subtask is `done`. That is **one
slice's** UI, in a dev worktree.

This skill is a different animal: the **integrated feature smoke gate**. It runs
the feature's browser smoke suite — the cross-subtask user journeys — against a
**real running app**, and only when they all pass does it stamp the feature
**complete**. It is the milestone the per-subtask flow never had: "all subtasks
`done`" is not "the feature works"; this gate is.

The same suite then lives on permanently in `11700-payable/e2e/<feature>`, so CI,
scheduled jobs, and ad-hoc human sanity runs invoke it directly. This skill is
the **AFK-facing gate** plus a convenient **manual runner** — not the only way
the suite ever runs.

## When it applies

Only when `/afk:to-subtasks` decided the feature needs a smoke gate
(`smoke_e2e = yes`, a per-feature human call). That decision lives in `PLAN.md`
as a `## Feature smoke gate` section (scenarios ↔ user stories, suite path, run
command, target env) and a terminal `NNNN-smoke-e2e` subtask that **authors**
the specs as reviewed code. If `PLAN.md` has no `## Feature smoke gate`, this
feature opted out — there is nothing to run (exit `no_gate`).

This skill never authors specs. The specs are written by the terminal
`NNNN-smoke-e2e` subtask through `/afk:execute`, reviewed in an MR like any
code. This skill only **runs** them as the gate.

## Argument

- `plan_path` *(or `ticket_id`)* — locates `…/{TICKET-ID}/plan/PLAN.md`.
- `target` *(optional)* — the running app the browser hits: `local` (default —
  the dev server), `staging`, or an explicit base URL. Never silently default to
  a target the human didn't pick when release-gating; `local` is for dev sanity,
  `staging` for acceptance.
- `scope` *(optional)* — run a named subset of scenarios (manual spot-check);
  default is the whole suite. A scoped run never stamps the feature complete.

## Process

1. **Locate the gate.** Read `PLAN.md`. Find `## Feature smoke gate`. Absent →
   this feature has no smoke gate → report `no_gate` and stop (nothing failed;
   nothing to do). Read the suite path, the run command, and the scenario table
   (each scenario traces to a PRD User Story).

2. **Precondition — feature fully built.** Every row in the `## Progress
   tracker` (including the terminal `NNNN-smoke-e2e` authoring subtask) must be
   `done`. Any subtask not `done` → refuse with `preconditions_unmet`, naming the
   laggards. A smoke gate on a half-built feature is meaningless — the integrated
   journeys can't pass until every slice has landed.

3. **Precondition — app reachable.** Confirm the `target` app instance is up
   (hit its base/health URL). Not reachable → `env_unreachable`; tell the human
   to start the app / bring up the env. Needing a **real running app** is this
   gate's defining trait — it is what separates it from the per-subtask tiers,
   which may run against a stub or a transient dev server.

4. **Run the suite.** Execute the suite's run command against `target` (one
   browser run, all scenarios — or the `scope` subset). Do not modify the app or
   the specs to coax a pass (Hard rules).

5. **Record per scenario.** Update each scenario row's `Status` in the
   `## Feature smoke gate` table (`pass` / `fail`) and stamp the gate's
   `Last run` (date + target). Attach the failure trace/artifact path on any
   `fail` row so the human can open it.

6. **Verdict.**
   - **All green** (full run, not a `scope` subset) → stamp the `PLAN.md` header
     `Feature: complete (smoke green {YYYY-MM-DD}, target={env})`. This is the
     completion milestone.
   - **Any red** → set `Feature: smoke-failing`; do **not** stamp complete. List
     the failing scenarios + their User Story + the artifact path. **No silent
     retry** — a flaky run is the human's to re-run deliberately; a real failure
     is fixed via a new/re-opened subtask or `/afk:grill-solution`, not by
     patching here.

7. **Report the structured outcome.** End with one line, mirroring
   `/afk:execute`'s style so a human or orchestrator can read it at a glance:

   ```
   OUTCOME: <status> — <one-line summary> [target: <env>] [failing: <n>]
   ```

   - `smoke_green` — every scenario passed on a full run; the feature is stamped
     complete in `PLAN.md`. (MRs remain the human's to merge — see Boundary.)
   - `smoke_fail` — ≥1 scenario red. Name each + its User Story + artifact path;
     the feature is **not** complete.
   - `env_unreachable` — the `target` app was not up. No scenarios were run.
   - `preconditions_unmet` — not every subtask is `done`; name the laggards.
   - `no_gate` — `PLAN.md` has no `## Feature smoke gate`; this feature opted
     out. Nothing to run.
   - `other` — unexpected failure.

## Relationship to the rest of the chain

- **vs. the per-subtask `e2e/browser` tier** (`/afk:execute` Step 8): that
  proves one slice's UI in a dev worktree as the slice lands. This proves the
  **integrated** feature against a running app, after everything has landed. Both
  exist on purpose; neither replaces the other.
- **vs. the terminal `NNNN-smoke-e2e` subtask**: that subtask *writes* the specs
  (and runs them locally in its own `e2e` Verification tier to prove they pass in
  dev). This skill *runs the authored suite* against the real target as the gate.
  The local redundancy is intentional — "specs pass in dev" ≠ "feature works in
  the env with all subtasks integrated."
- **Reuse**: the authored specs are permanent residents of
  `11700-payable/e2e/<feature>`. CI pipelines and scheduled jobs run the same
  suite command directly; a human can run this skill (or the raw command) any
  time to re-check system sanity. The gate is one consumer of the suite, not its
  owner.

## Boundary (Hard rules)

- **Owns only the gate's surface in `PLAN.md`** — the `## Feature smoke gate`
  table `Status` cells, its `Last run` line, and the header `Feature:` line.
  Everything else in `PLAN.md` round-trips verbatim (the `## Progress tracker`
  status column stays `/afk:execute`'s).
- **Merges nothing, touches no Jira.** Like `/afk:execute`, it stops at the
  human's lane: a green gate does not merge the Draft MRs and does not write to
  the tracker. The human merges out of band.
- **Authors no specs.** Spec code is the terminal `NNNN-smoke-e2e` subtask's
  reviewed work. If a scenario needs a new/changed spec, that's a subtask edit
  (re-run `/afk:execute` on it), not an edit from inside the gate.
- **Never patches to green.** Do not touch app code or specs to make a red run
  pass — a red gate is a true signal about the feature or the spec. Fix it
  upstream (subtask or grill), then re-run the gate.
- **Right target for the purpose.** `local` for dev sanity; `staging` (or the
  release target) for acceptance gating. Don't release-gate against a dev server.

## Next

Feature green → it's complete. The subtask MRs are still **Draft** and the
human's to review + merge (`/afk:execute` left them that way on purpose). After
the merges, the smoke suite stays in `11700-payable/e2e/<feature>` and is picked
up by CI / scheduled verification / manual sanity runs from then on — re-run this
skill (or the raw suite) whenever you want to re-confirm the system is sane.

Feature red → fix the failing journey at its source (re-run `/afk:execute` on the
owning subtask, or `/afk:grill-solution` if a binding decision is wrong), then
re-run `/afk:smoke`.
