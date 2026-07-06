---
name: autopilot
description: Hands-off driver that walks a local plan subtask by subtask with a fresh subagent per subtask, provisions the live app for verification, parks failures and their dependents, and finishes at the feature smoke gate. Use when the user runs `/afk:autopilot` on the parent branch once a local plan exists.
---

# afk:autopilot — drive the whole plan hands-off

One invocation runs every runnable subtask of a local plan to `done`, sequentially, then the feature smoke gate. The human returns to either a green feature or a precise parked-state report — never to "done" that doesn't compile, boot, or pass its tiers.

## Argument

`plan_path` *(or ticket id)* — locates `…/{TICKET-ID}/plan/PLAN.md`. Optional `from:{NNNN-slug}` resumes mid-plan (earlier `done` rows are skipped anyway — re-running the skill is always safe).

## Preconditions (refuse to start otherwise)

1. cwd is a worktree on the parent branch, working tree **clean** (uncommitted human changes → refuse; they'd be swept into subtask commits).
2. `plan/PLAN.md` + every subtask contract present; re-run the tier-mandate check (`skills/afk/to-subtasks/VALIDATION.md` item (e)) against the plan — a plan violating a mandate does not start.
3. Local infra up: probe the DB/broker the service needs (boot classification would otherwise blame code). One `app-start-gate.sh` run of the target service must exit `0` before subtask 1 — this is the env baseline. Exit `3` → `env_unreachable`, exit `4` → treat as env (timeout), exit `2` → refuse with "baseline broken before subtask 1: the parent branch itself doesn't boot" — all three stop the run before touching anything.

## Authorization boundary

Starting this skill **is** the standing authorization for per-subtask `git commit` + `git push` on the feature branch and Draft-MR checklist updates — nothing else: no merge, no push to any other branch, no Jira. Outside an autopilot run the no-auto-commit rule stands.

## Run loop

**Journal as you go.** Append one line to `plan/JOURNAL.md` (format: `skills/afk/to-subtasks/JOURNAL-FORMAT.md`; create with its header if missing) for: run start (how many subtasks runnable), each subtask completion (a heartbeat — `k/N done, starting {next}`), every park (with the plain-terms reason), every parked-by-inheritance row, every stranded row, and run end. The journal is the durable record of the run — the tracker can't carry parked-by-inheritance or stranded truth; the journal does.

Walk the `## Progress tracker` in rank order. For each subtask not `done`:

1. **Blocked-by check.** Any prerequisite not `done` (including parked ones) → the subtask is **parked by inheritance**: skip it, record `parked(waiting on {ID})` in the run report **and append its journal line**. Do not write to PLAN.md — the tracker's Status column belongs to the executor; parked-by-inheritance rows simply never start.
2. **Spawn a fresh subagent** for the subtask using [SUBAGENT-PROMPT.md](SUBAGENT-PROMPT.md). One subtask per subagent — no context bleed between slices. The subagent runs the execute contract in **driven mode** and must end with its structured `OUTCOME:` line.
3. **The subtask subagent provisions its own app.** The orchestrator only reserves the side port and boots the baseline before the run (Preconditions item 3) — it does not provision per slice. The subagent, which holds the reboot command, self-provisions **after implementing** — so the instance serves this slice's code — via `.claude/hooks/app-start-gate.sh {leaf-module}` in provisioning mode: `APP_START_KEEP=1` (leaves the instance running), `APP_START_PORT={side port}`, and `APP_START_SKIP_UI=false` for UI-touching slices so the jar serves the rebuilt UI; the spawn prompt hands it the port + command. When the slice finishes, kill any instance left running (the pid the gate printed); never point verification at a developer's own running instance.
4. **Read the OUTCOME.**
   - `success` → next subtask.
   - Anything else → **park** this subtask and continue with subtasks not downstream of it. A structured outcome means the executor already left the row `blocked(…)`; a killed/vanished subagent leaves its row at an in-flight status — leave it (re-runs skip only `done`), flag the stranded row in the report, **and journal it as `stranded`** so the stale in-flight cell can't be mistaken for live work. On **every** park, send a push notification per `REPORTING.md` (plugin root): subtask + status + one plain-terms sentence — the human may want to intervene while independent work is still burning wall-clock. Every park also lands in the final report.
5. **Wall-clock guard.** A subagent silent past the per-subtask cap (default 90 min): stop waiting — mark the subtask `parked(timeout)` in the journal, park its dependents, and continue with independent subtasks. Its tracker row stays in-flight (see above); if the stale subagent reports later, discard the report.

Sequential by design: one subtask, one worktree, one app instance at a time. Do not parallelize independent subtasks.

## Finish

- Every non-parked subtask `done` (including terminal `NNNN-smoke-*` / `NNNN-sync-harness` build subtasks) → run `/afk:smoke-test` against the self-provisioned instance. A parked terminal `NNNN-smoke-*` build subtask parks the feature gate too — the smoke suite is not run half-suited; report `smoke: not_run` with the park.
- Send the end-of-run notification and report:

```
AUTOPILOT: <n_done>/<n_total> done, <n_parked> parked — smoke: <verdict|not_run>
In plain terms: <one jargon-free sentence — what the human comes back to and what needs their decision first>
parked: {NNNN-slug}(status — <plain-terms clause>), … [+ dependents by inheritance]
Journal: plan/JOURNAL.md · Reviews: plan/review/INDEX.md
```

The report follows `REPORTING.md` (plugin root). Any park, any red smoke row, any waived scenario is in the report explicitly — the human must never discover state the report omitted. The journal carries the same events in order, so the report can be terse: the report is the triage view, the journal is the reconstruction view.

## Hard rules

- **Never merge, never touch Jira, never push outside the feature branch.**
- **Mandated tiers are hard** — per the execute contract's Driven mode (the owning statement of the no-new-waivers rule); a subtask that can't satisfy one parks.
- **Single writer preserved.** This skill writes no PLAN.md cell, no subtask file, no MR text — the per-subtask executor owns those. This skill owns only the run report, notifications, and its own appended `plan/JOURNAL.md` lines (append-only; never edit a prior line).
- **No patching to green at the gate.** A red smoke run ends the run red; fixes belong to a re-run after the human (or a new subtask) addresses the cause.
