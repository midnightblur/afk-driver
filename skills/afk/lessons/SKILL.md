---
name: lessons
description: Steward of the workflow lesson ledger — status/apply/audit. Use on /afk:lessons, to see open workflow lessons, or to review and apply drafted edits.
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# afk:lessons — apply what the workflow already learned

Detection points across the chain capture **lessons** — classified workflow
mistakes with a drafted durable edit — into the lesson ledger the moment they
conclude (protocol: [CAPTURE.md](CAPTURE.md); grammar, class enum, statuses,
escalation ladder: [LEDGER-FORMAT.md](LEDGER-FORMAT.md)). This skill is the
ledger's steward: it reports the ledger's state, walks `open` drafts through
propose → approve → write, and keeps the ledger hygienic. It never captures —
capture belongs to the detection points.

## Subcommands (default `status`)

### `status`

Run `bash <main-checkout>/tools/payable/ai-agents/plugins/workflow/hooks/lesson-digest.sh --all`
(`<main-checkout>` = first entry of `git worktree list` — `GLOSSARY.md` "Main
checkout")
from the repo root and report per `REPORTING.md` (plugin root):

```
In plain terms: <one jargon-free sentence — what the workflow has learned and not yet absorbed>
Ledger: <resolved LEDGER.jsonl path>
LESSONS: <n> open, <m> applied, <k> verified — top open: <L-NNNN> (<≤6-word gloss>)
```

### `apply`

Walk `open` lessons newest-first; for each, route by `target`:

- **CLAUDE.md tree / role sidecars / `.claude/rules` / `STAPLES.md`** →
  delegate to `/afk:claude-md` with the draft; its propose → approve → write
  protocol and write boundary govern.
- **Domain `GLOSSARY.md`** → delegate to `/afk:glossary` — same shape.
- **Plugin file (skill, checklist, doctrine, hook)** → propose → approve →
  write **here**: load `/afk:writing-great-skills` first and hold the edit to
  its bar; honour the plugin `CLAUDE.md` "Lockstep" partners and the
  `FRESHNESS.md` same-commit obligations of every file touched.

Per outcome, append the transition via
`bash <main-checkout>/tools/payable/ai-agents/plugins/workflow/hooks/lesson-append.sh`:
`applied --id <id> --note "<file / commit>"` on a written edit,
`rejected --id <id> --note "<reason>"` on a decline. A lesson the human defers
stays `open` — no event. Approval is per-lesson (apply-all / by-number also
fine); **never write unapproved**.

Applying a ladder escalation (a retro proposed the next rung): append the new
`opened` lesson at that rung and a `superseded` event (note = successor id) on
the old one — per LEDGER-FORMAT.md's ladder rule.

### Bind (closes every applied edit, whoever applied it)

A durable edit that is not loaded is not in force. After any write, tell the
human what it takes for that edit to bind:

| Written | Binds |
|---|---|
| Plugin file (skill, checklist, doctrine, hook) | `/reload-plugins` — say so explicitly; until then the old text is what runs |
| CLAUDE.md tree, role sidecar, `.claude/rules`, `STAPLES.md` | immediately — already in the session's context |
| Domain `GLOSSARY.md` | on next read; no action |

### `audit`

Read-only hygiene report: malformed ledger lines, `applied` lessons whose
`note`-named target edit no longer exists on disk, `open` lessons older than
the newest applied one by feature-count (stall candidates), duplicate drafts
against the same `target`. Findings route to `apply` (or a human decision) —
this subcommand writes nothing.

## Hard rules

- **Ledger writes only through `hooks/lesson-append.sh`** — never hand-append,
  never edit or delete a prior line (append-only, multi-writer).
- **Never write a durable edit without approval** — propose → approve → write,
  every target, every time.
- **Plugin-file edits only in an interactive session.** Invoked hands-off
  (driven/autopilot), `apply` refuses; `status`/`audit` remain available.
- **Never commits or pushes target-repo code** — durable-edit commits ride the
  session's normal commit lane.
