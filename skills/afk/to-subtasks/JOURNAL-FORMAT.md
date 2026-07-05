# Journal format — `plan/JOURNAL.md`

The append-only event log of a plan: one timestamped line per event, newest last. It exists so a human who wasn't watching can reconstruct exactly what happened, in order, without stitching together tracker cells, subtask notes, and git log. The tracker shows *current* state; the journal shows *history* — including states the tracker cannot hold (parked-by-inheritance, stranded rows, red runs that later went green).

## Rules

- **Append-only.** Writers add lines at the end; nobody edits or deletes a prior line. This is what makes multi-writer safe.
- Seeded with the header line below when the plan is emitted; any writer finding the file missing creates it with the header first, then appends.
- Timestamps are local, to the minute.
- Every line's trailing clause follows the plain-terms rule of `REPORTING.md` (plugin root): a reader without workflow vocabulary can follow the story from the journal alone.

## Header (line 1 of the file)

```
# Journal — append-only event log (format: skills/afk/to-subtasks/JOURNAL-FORMAT.md). Newest last.
```

## Line grammar

```
{YYYY-MM-DD HH:mm} | {writer} | {subject} | {event} — {plain terms}
```

- `{writer}` — the skill appending: `execute`, `autopilot`, `smoke-test`.
- `{subject}` — a subtask id (`NNNN-slug`), `run`, or `gate`.
- `{event}` — a short token from the writer's set below.
- `{plain terms}` — one clause; jargon-free; may be omitted only when the event token is self-explanatory to a lay reader (it almost never is).

## Event sets per writer

| Writer | Events |
|---|---|
| `execute` | `designing`, `developing`, `verifying`, `reviewing`, `done`; `pushed {short-sha}..{short-sha} ({n} commits)`; `review {verdict} crit={n} high={n} med={n} low={n}`; `adversary {verdict} …`; `parked({status})` |
| `autopilot` | `run start ({n} runnable)`; `heartbeat {k}/{n} done, starting {NNNN-slug}`; `parked({status})`; `park-inherited(waiting on {ID})`; `stranded`; `run end ({k}/{n} done, {p} parked)` |
| `smoke-test` | `smoke {verdict} ({passed}/{run} scenarios{, k skipped env-limited})` |

Hypothetical shape:

```
2026-01-10 14:32 | execute | 0004-credit-api | developing — writing the failing test for the new endpoint first
2026-01-10 15:07 | execute | 0004-credit-api | parked(produces_drift) — the method this slice promised to deliver never landed under the promised name; dependents can't start until a human fixes the code or re-cuts the plan
2026-01-10 15:07 | autopilot | run | heartbeat 3/9 done, starting 0005-credit-ui — three slices landed, moving on while 0004 waits for a human
```
