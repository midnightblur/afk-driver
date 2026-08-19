---
name: autopilot
description: Hands-off driver — walks a local plan subtask-by-subtask to a green smoke gate, then chains /afk:preflight. Use when the user runs /afk:autopilot on the parent branch.
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# afk:autopilot — drive the whole plan hands-off

One invocation runs every runnable subtask of a local plan to `done`, sequentially, then the feature smoke gate.

## Argument

`plan_path` *(or ticket id)* — locates `…/{TICKET-ID}/plan/PLAN.md`. Optional `from:{NNNN-slug}` resumes mid-plan (earlier `done` rows skipped anyway — re-running is always safe).

## Preconditions (refuse to start otherwise)

1. cwd is a worktree on the parent branch, working tree **clean** (uncommitted human changes → refuse; they'd be swept into subtask commits).
2. `plan/PLAN.md` + every subtask contract present; re-run the tier-mandate check (`skills/afk/to-subtasks/VALIDATION.md` item (e)) against the plan — a plan violating a mandate does not start.
3. Local infra up: probe the DB/broker the service needs (else boot classification blames code). One `app-start-gate.sh` run of the target service must exit `0` before subtask 1 — the env baseline. Exit `3` → `env_unreachable`; exit `4` → treat as env (timeout); exit `2` → refuse with "baseline broken before subtask 1: the parent branch itself doesn't boot" — all three stop the run before touching anything.

## Authorization boundary

Starting this skill **is** the standing authorization for per-subtask `git commit` + `git push` on the feature branch and Draft-MR checklist updates — nothing else: no merge, no push to any other branch, no Jira. Outside an autopilot run the no-auto-commit rule stands.

## Run loop

**Journal as you go.** Append one line to `plan/JOURNAL.md` (format: `skills/afk/to-subtasks/JOURNAL-FORMAT.md`; create with its header if missing) for: run start (how many subtasks runnable), each subtask completion (heartbeat — `k/N done, starting {next}`), every park (with plain-terms reason), every parked-by-inheritance row, every stranded row, run end. The journal is the durable record of the run — the tracker can't carry parked-by-inheritance or stranded truth; the journal does.

Walk the `## Progress tracker` in rank order. For each subtask not `done`:

1. **Blocked-by check.** Any prerequisite not `done` (including parked ones) → the subtask is **parked by inheritance**: skip it, record `parked(waiting on {ID})` in the run report **and append its journal line**. Do not write to PLAN.md — the tracker's Status column belongs to the executor; parked-by-inheritance rows never start.
2. **Spawn a fresh subagent** for the subtask using [SUBAGENT-PROMPT.md](SUBAGENT-PROMPT.md). One subtask per subagent — no context bleed between slices. The subagent runs the execute contract in **driven mode** and must end with its structured `OUTCOME:` line.

   **Size the subagent by the contract's `## Complexity`** (token owned by `skills/afk/to-subtasks/SUBTASK-CONTRACT.md` — lockstep copy here because this step routes on it; absent → `standard`): `mechanical` → a general-purpose child at the digest-tier model (per-provider names: `PROVIDERS.md` "Model tiers") at low reasoning effort; `standard` → the **`afk-implementor`** agent type (the default — when unsure, this); `complex` → `afk-implementor` at high reasoning effort — never the frontier model: the frontier intelligence is already in the contract (`DELEGATION.md` "Model selection"). The implementation tier travels as an *agent type*, not a model argument — a pinned model reaches a child only through its definition's frontmatter (`PROVIDERS.md` "Pin delivery"). Routing applies to the subtask's executing subagent only — the review/adversary gates it spawns keep their own defaults. A `mechanical` subtask that parks is re-run once at `standard` sizing before the park stands (misclassification, not code, may be the cause — journal the resize).
3. **The subtask subagent provisions its own app.** The orchestrator only reserves the side port and boots the baseline before the run (Preconditions item 3) — no per-slice provisioning. The subagent, which holds the reboot command, self-provisions **after implementing** — so the instance serves this slice's code — via `<main-checkout>/tools/payable/ai-agents/plugins/workflow/hooks/app-start-gate.sh {leaf-module}` (`<main-checkout>` = first entry of `git worktree list`; plugin files always run from the main checkout, never a worktree's stale copy — `GLOSSARY.md` "Main checkout". cwd stays the worktree root) in provisioning mode: `APP_START_KEEP=1` (leaves the instance running), `APP_START_PORT={side port}`, `APP_START_SKIP_UI=false` for UI-touching slices so the jar serves the rebuilt UI; the spawn prompt hands it the port + command. **The instance is per-run, not per-slice**: a slice whose changes touched nothing the app loads (no file under a Maven module's `src/`, no UI file when the instance serves the UI) reuses the prior slice's instance via `APP_START_REUSE=1` instead of rebuilding; a slice that did touch loaded code re-runs the command plain — the gate kills the recorded prior instance itself (state file `.claude/hooks/.app-instance-{port}`). Subagents leave the instance running when their slice finishes; never point verification at a developer's own running instance.
4. **Read the OUTCOME.**
   - `success` → next subtask.
   - Anything else → **park** this subtask and continue with subtasks not downstream of it. A structured outcome means the executor already left the row `blocked(…)`; a killed/vanished subagent leaves its row at an in-flight status — leave it (re-runs skip only `done`), flag the stranded row in the report, **and journal it as `stranded`** so the stale in-flight cell can't be mistaken for live work. On **every** park, send a push notification per `REPORTING.md` (plugin root): subtask + status + one plain-terms sentence — the human may want to intervene while independent work still burns wall-clock. Every park also lands in the final report.
5. **Wall-clock guard — armed, never assumed.** With each spawn, arm the stall watchdog per `DELEGATION.md` "Stall watchdog", watching the worktree's `.git` dir, the plan dir, and the module's build output; disarm when the `OUTCOME:` arrives. Watchdog fires and the probe finds the subagent silent → mark it `parked(timeout)` — step 4's park handling applies (journal line, push notification, dependents parked) — clean the side port's leftover processes per the same doctrine, then continue with independent subtasks. Its tracker row stays in-flight (see above); if the stale subagent reports later, discard the report.

Sequential by design: one subtask, one worktree, one app instance at a time. Do not parallelize independent subtasks.

## Finish

- Every non-parked subtask `done` (including terminal `NNNN-smoke-*` / `NNNN-sync-harness` build subtasks) → run `/afk:smoke-test` against the self-provisioned instance. A parked terminal `NNNN-smoke-*` build subtask parks the feature gate too — the smoke suite is not run half-suited; report `smoke: not_run` with the park.
- **On smoke-green** (`PLAN.md`'s `Feature:` header reads `complete (smoke green …)` or `complete (minimal gate, …)`) → invoke /afk:preflight `{plan-dir}`. The one added chain step (SDD §8 row "M2 autopilot chain edit", §14 row "autopilot skill chain") — the per-subtask `/afk:execute` tail (tiers → review → adversary → commit → push → Draft-MR checklist) stays untouched, and a human can still run `/afk:preflight {plan-dir}` by hand later (e.g. to resume a `parked(PF-n: …)` feature) — chaining it here doesn't retire the standalone entry point. Preflight's outcome (`success` / `refused(no_green_smoke)` / `parked(PF-n: …)` / `other`) folds into this run's report and, on `parked(PF-n: …)`, gets the same push notification + report treatment as a subtask park (per `REPORTING.md`) — smoke-red or smoke-`not_run` skips this step entirely (nothing to chain onto).
- **Stop the warm instance.** At run end — green, red, or parked — read `.claude/hooks/.app-instance-{side port}` and kill the recorded pid tree (the stop command the gate printed); the instance never outlives the run. No state file or dead pid → nothing to do.
- Send the end-of-run notification and report. Driven subtask runs draft workflow lessons nobody has approved yet (`skills/afk/lessons/CAPTURE.md`); read the open count via `bash <main-checkout>/tools/payable/ai-agents/plugins/workflow/hooks/lesson-digest.sh --count` from the worktree root — a non-zero count tells the human `/afk:lessons apply` is worth a stop.

```
AUTOPILOT: <n_done>/<n_total> done, <n_parked> parked — smoke: <verdict|not_run> — preflight: <verdict|not_run>
In plain terms: <one jargon-free sentence — what the human comes back to and what needs their decision first>
parked: {NNNN-slug}(status — <plain-terms clause>), … [+ dependents by inheritance] [+ preflight: parked(PF-n: reason) if applicable]
Journal: plan/JOURNAL.md · Reviews: plan/review/INDEX.md · Lessons: <n> open
```

The report follows `REPORTING.md` (plugin root). Any park, any red smoke row, any waived scenario is in the report explicitly — the human must never discover state the report omitted. The journal carries the same events in order, so the report stays terse: the report is the triage view, the journal the reconstruction view.

## Hard rules

- **Never merge, never touch Jira, never push outside the feature branch.**
- **Mandated tiers are hard** — per the execute contract's Driven mode (the owning statement of the no-new-waivers rule); a subtask that can't satisfy one parks.
- **Single writer preserved.** This skill writes no PLAN.md cell, no subtask file, no MR text — the per-subtask executor owns those. It owns only the run report, notifications, and its own appended `plan/JOURNAL.md` lines (append-only; never edit a prior line).
- **No patching to green at the gate.** A red smoke run ends the run red; fixes belong to a re-run after the human (or a new subtask) addresses the cause.
