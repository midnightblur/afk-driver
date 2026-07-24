# Journal format — `plan/JOURNAL.md`

A plan's append-only event log: one timestamped line per event, newest last. Lets a human who wasn't watching reconstruct exactly what happened, in order, without stitching together tracker cells, subtask notes, and git log. The tracker shows *current* state; the journal shows *history* — including states the tracker cannot hold (parked-by-inheritance, stranded rows, red runs that later went green).

## Rules

- **Append-only.** Writers add lines at the end; nobody edits or deletes a prior line. This is what makes multi-writer safe.
- Seeded with the header line below when the plan is emitted; any writer finding the file missing creates it with the header first, then appends.
- Timestamps local, to the minute.
- Every line's trailing clause follows the plain-terms rule of `REPORTING.md` (plugin root): a reader without workflow vocabulary can follow the story from the journal alone.

## Header (line 1 of the file)

```
# Journal — append-only event log (format: skills/afk/to-subtasks/JOURNAL-FORMAT.md). Newest last.
```

## Line grammar

```
{YYYY-MM-DD HH:mm} | {writer} | {subject} | {event} — {plain terms}
```

- `{writer}` — the skill appending: `execute`, `autopilot`, `smoke-test`, `preflight`, `understand`.
- `{subject}` — a subtask id (`NNNN-slug`), `run`, `gate`, or `understanding`.
- `{event}` — a short token from the writer's set below.
- `{plain terms}` — one clause; jargon-free; omit only when the event token is self-explanatory to a lay reader (almost never).

## Event sets per writer

| Writer | Events |
|---|---|
| `execute` | `designing`, `developing`, `verifying`, `reviewing`, `done`; `pushed {short-sha}..{short-sha} ({n} commits)`; `review {verdict} crit={n} high={n} med={n} low={n}`; `adversary {verdict} …`; `parked({status})` |
| `autopilot` | `run start ({n} runnable)`; `heartbeat {k}/{n} done, starting {NNNN-slug}`; `parked({status})`; `park-inherited(waiting on {ID})`; `stranded`; `run end ({k}/{n} done, {p} parked)` |
| `smoke-test` | `smoke {verdict} ({passed}/{run} scenarios{, k skipped env-limited})` |
| `understand` | `generated`; `failed({reason})` (subject token `understanding`; owned by `skills/afk/understand/SKILL.md`, the emitter — a token added or renamed there is a same-commit change here) |
| `preflight` | `refused(no_green_smoke)`; `PF-{n} green`; `PF-{n} parked({reason})`; `fix-cycle {k}/2 on PF-{n}`; `settle-round {k} on PF-3 — {verdict}`; `ci-wait launched (budget={s}s, interval={s}s)`; `ready`; `done` — full grammar: "### Preflight events" below |

### Preflight events

`/afk:preflight`'s event set (lockstep copy — owned jointly by
`skills/afk/preflight/SKILL.md`, the emitter, and this file; a token added or
renamed there is a same-commit change here):

- `refused(no_green_smoke)` — the Step-0 refusal guard fired; nothing else
  written this run (the one event a refused run still logs, appended before
  the guard's own "write nothing" rule takes effect — the guard never creates
  the `## Preflight` section, but the refusal is worth a JOURNAL line so a
  human scanning history sees the attempt).
- `PF-{n} green` — step `n` (1-7) completed; its `## Preflight` table row
  flipped to `green`.
- `PF-{n} parked({reason})` — step `n` could not proceed; `{reason}` is one
  of `merge_conflict`, `ancestry_guard_failed`, `semantic_red`,
  `review_stalemate`, `orphan_artifact`, `ci_test_red`, `secret_hit`,
  `budget_exhausted`, `glab_flake` (per `skills/afk/preflight/SKILL.md`'s
  PF-1..7 routing table).
- `fix-cycle {k}/2 on PF-{n}` — shared fix-cycle counter incremented (logged
  **before** the fix attempt, so a crash mid-fix still shows the spent cycle
  on resume).
- `settle-round {k} on PF-3 — {verdict}` — one line per review settle-loop
  round (round structure: `skills/afk/review/SETTLEMENT.md`).
- `ci-wait launched (budget={s}s, interval={s}s)` — PF-6's background task
  started.
- `ready` — PF-7 flipped the MR Draft → Ready on a green pipeline.
- `done` — every `## Preflight` row is `green`; the run is terminal.

Hypothetical shape:

```
2026-01-10 14:32 | execute | 0004-credit-api | developing — writing the failing test for the new endpoint first
2026-01-10 15:07 | execute | 0004-credit-api | parked(produces_drift) — the method this slice promised to deliver never landed under the promised name; dependents can't start until a human fixes the code or re-cuts the plan
2026-01-10 15:07 | autopilot | run | heartbeat 3/9 done, starting 0005-credit-ui — three slices landed, moving on while 0004 waits for a human
```
