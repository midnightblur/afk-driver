# Lesson ledger format — `.claude/lessons/LEDGER.jsonl`

The **one home** for the workflow lesson ledger: location + resolution rule,
JSONL event grammar, class enum, miss-class mapping, status model, and the
escalation ladder. Every other file points here and restates nothing.

The ledger's only emitting site is `hooks/lesson-append.sh`; its only parsing
site is `hooks/lesson-digest.sh` — both lockstep with this grammar (change one →
same commit on all three; declared in the plugin `CLAUDE.md` "Lockstep").

## Location (worktree-safe)

The ledger lives in the **main checkout** of the target repo — shared across
every feature worktree, so lessons recorded in one worktree are visible in all:

```
<main-checkout>/.claude/lessons/LEDGER.jsonl
```

Resolution: `git rev-parse --path-format=absolute --git-common-dir` → the
ledger root is that path's parent directory. Override with `LESSON_LEDGER_FILE`.
A gitignored **runtime artifact of the target repo** (same standing as
`.claude/bugs/` and `.claude/metrics/`) — never committed, never a plugin file.

## Event model

Append-only, event-sourced, multi-writer safe: writers add lines at the end via
the appender; **nobody edits or deletes a prior line**. The first event for an
id is `opened` and carries the full payload; later events are transitions
carrying only `ts`/`id`/`event`/`writer` (+ optional `note`). A reader folds
**last event per id wins**: the latest event is the lesson's current status,
`opened`-payload fields persist underneath.

## Line grammar

Opening event:

```json
{"ts":"<ISO-8601 UTC>","id":"L-NNNN","event":"opened","writer":"<skill>","class":"<enum below>","target":"<repo-relative home of the durable edit>","summary":"<one plain-terms line>","draft":"<the concrete proposed edit — self-contained>","miss":"<escape-analysis class, when one exists>","source":"<ticket / subtask / finding id>","evidence":"<path:line>"}
```

`class`, `target`, `summary` are required; `draft` is required unless the edit
already shipped (an `applied` follows immediately); `miss`/`source`/`evidence`
optional. `draft` must stand alone — never a pointer to a temp file.

Transition event:

```json
{"ts":"<ISO-8601 UTC>","id":"L-NNNN","event":"<applied|verified|rejected|superseded>","writer":"<skill>","note":"<reason / commit / successor id>"}
```

## Status model (= last event)

| Event | Meaning |
|---|---|
| `opened` | Detected, classified, edit drafted — not yet applied. The only status the feed-forward digest shows. |
| `applied` | The durable edit was written after human approval; `note` names the edited file (and commit when there is one). |
| `verified` | A later retro found the signal gone — the loop closed. |
| `rejected` | A human declined the draft; `note` carries the reason. |
| `superseded` | Replaced by a stronger lesson (escalation); `note` names the successor `L-NNNN`. |

## Class enum

| `class` | When | Durable-edit home |
|---|---|---|
| `missed-instruction` | An instruction existed (CLAUDE.md / skill / checklist) and was demonstrably not followed | harden the existing line per the ladder below |
| `missing-instruction` | Nothing documented the rule the mistake violated | new line at the right home (CLAUDE.md tree, sidecar, skill step) |
| `wrong-term` | A human had to clarify terminology the agent misread | the owning domain `GLOSSARY.md` |
| `weak-checklist` | A review-checklist criterion proved noisy, toothless, or absent | `skills/afk/review/checklists/*.md` |
| `test-dodge` | A test was shaped to avoid a real failure instead of surfacing it | verification doctrine (AUTHORING guides, subtask contract, TESTING.md) |
| `wrong-design` | A grill/design stage accepted a wrong premise a later stage disproved | the owning grill/synthesis skill |

## Miss-class mapping

`/afk:fix`'s escape analysis names a **miss class** (set owned by
`skills/afk/fix/ESCAPE-ANALYSIS.md` — lockstep with this table). It rides the
`miss` field verbatim; the lesson `class` derives from it:

| Escape-analysis miss class | Lesson `class` |
|---|---|
| `no-scenario` / `weak-assertion` / `wrong-path` | `missing-instruction` |
| `excluded` | `wrong-design` |
| `disabled/flaky` | `missed-instruction` |
| `dodged-failure` | `test-dodge` |

## Escalation ladder

An `applied` lesson whose signal recurs means the edit didn't stick. Escalate
**one rung per recurrence**, as a **new** `opened` lesson naming the next rung
plus a `superseded` event on the old one — never by rewriting history:

1. **Reword** — stronger leading word, checkable completion criterion
   (`/afk:writing-for-agents` levers).
2. **Relocate** — move the line to where the acting agent demonstrably reads at
   the moment of the mistake.
3. **Checklist criterion** — add it to the owning review checklist so the gate
   catches what prose didn't prevent.
4. **Stop-hook gate** — mechanical enforcement in `hooks/`; prose has failed
   three times.
