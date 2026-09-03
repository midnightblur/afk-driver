# Lesson capture — conclude at detection

The protocol every detection point follows the moment a workflow lesson
concludes. Capture happens **right there, while context is fresh on both
sides** — never deferred to a retro. Detection points carry one pointer
sentence to this file and restate nothing.

## What qualifies

A **concluded** workflow lesson — the gap is confirmed, not suspected:

- a human confirms a review/adversary/MR finding real (or dismisses it) and the
  conclusion exposes a doctrine gap — an instruction that existed but was
  ignored, or one that should exist;
- a human corrects the agent's misunderstanding of an established pattern or
  instruction;
- a human clarifies a term the agent misread;
- escape analysis names a miss class;
- a documented instruction was demonstrably not followed.

One-off, obvious-from-code, or this-session-only → **not a lesson** (same bar
as `/afk-toolkit:claude-md`'s inclusion bar). When unsure, don't capture.

## Conclude it now

1. **Classify** — pick the `class` (enum: [LEDGER-FORMAT.md](LEDGER-FORMAT.md)).
2. **Name the target** — the repo-relative file where the durable edit belongs.
3. **Draft the edit** — the concrete line/wording change, self-contained in the
   `draft` field (never a pointer to a temp file).
4. **Measure any worked example.** A worked example citing round numbers,
   counts, or commits names the artifact it was measured from, and the
   measurement is re-run when the lesson is applied. A worked example is the
   part a later reader trusts most and verifies least.

## Route — eager when possible, drafted when not

| Condition | Do |
|---|---|
| Human present **and** target is CLAUDE.md / role sidecars / `.claude/rules` / `STAPLES.md` | Delegate to `/afk-toolkit:claude-md` (its propose → approve → write). On approved write: append `opened` then `applied`. Declined: append `opened` then `rejected`. |
| Human present **and** target is a domain `GLOSSARY.md` | Delegate to `/afk-toolkit:glossary` — same handling. |
| Human present **and** target is a plugin file (skill, checklist, doctrine, hook) | **Self-contained** → delegate to a writer subagent that loads `/afk-toolkit:writing-for-agents`, makes the edit, and closes its FRESHNESS obligations; append `opened` then `applied`/`rejected`. Delegating keeps the invoking task's own context intact. **Not self-contained** → append `opened` alone; applied in a dedicated `/afk-toolkit:lessons apply` session. |
| No human (driven / hands-off) | Append `opened` with the full draft — the drafts surface at the ship gate's advisory row and via `/afk-toolkit:lessons`. |

**Self-contained** = one file, no `CLAUDE.md` "Lockstep" partner, no row in
`FRESHNESS.md`'s registry. The bar exists because a half-written lockstep set
ships a plugin that contradicts itself — worse than a lesson applied a day late.

The detecting skill **never writes a durable edit itself** — eager application
goes through the target's owning steward; the only thing a detection point
writes directly is a ledger event.

## The append

From the target repo root (`<main-checkout>` = first entry of `git worktree
list` — plugin scripts always run from the main checkout, never a worktree's
stale copy; `GLOSSARY.md` "Main checkout"):

```
bash <main-checkout>/tools/payable/ai-agents/plugins/workflow/hooks/lesson-append.sh opened \
  --class <class> --target <path> --summary "<one line>" \
  --draft "<the edit>" --writer <skill> \
  [--miss <class>] [--source <id>] [--evidence <path:line>]
```

The script prints the minted `L-NNNN` id; transitions reuse it
(`… applied --id L-NNNN --note "<file / commit>" --writer <skill>`).
**Best-effort:** the appender always exits 0 — a failed append is a stderr
note, never a reason to block the capturing task.

## Reporting

Mention captured ids in the terminal report as `[lesson: L-NNNN]` within the
invoking skill's own grammar — the id resolves against the ledger on disk, per
`REPORTING.md`'s id rule.
