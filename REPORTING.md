# Reporting protocol

How every AFK skill reports to the human. Binding on any skill that emits a status line, a push notification, or a run report. Goal: a human who knows the *domain* but not the *workflow vocabulary* follows every report without opening another file.

## The layered report

Every terminal report has three layers, in this order:

1. **Headline** — the structured status line the skill already owns (`OUTCOME:`, `AUTOPILOT:`, `REVIEW:`, `ADVERSARY:`, `RETRO:`, `SETTLE:`). Grammar unchanged, machine-parseable; each skill's own file owns its grammar.
2. **Plain terms** — adjacent to the headline, one sentence starting `In plain terms:` naming what happened and its consequence for the reader, no workflow jargon. Must stand alone — a reader must not need `GLOSSARY.md` to act on it.
3. **Pointer** — where the full story lives, as paths: the report file, the journal, the MR.

Ordering: headline first. Exception — when an orchestrator parses the report's **trailing** line (driven mode), the plain-terms and pointer lines go immediately **before** the headline so the status line stays last.

Example shape (hypothetical):

```
OUTCOME: blocked(produces_drift) — anchor `applyCreditBatch` missing on branch [producer: 0004-credit-api]
In plain terms: this subtask was supposed to deliver a method later subtasks will call, but that method never landed under the promised name — a human must fix the code or re-cut the plan before dependents run.
Journal: plan/JOURNAL.md · Contract: plan/0004-credit-api.md
```

## Rules

- **The plain-terms sentence carries the consequence, not the code.** "The API changed and a later subtask still expects the old one" — never "produces drift occurred".
- **No workflow jargon in the plain-terms sentence.** Status tokens, layer codes (L1–L9), mode names live in `GLOSSARY.md` (plugin root) — the sentence must not need it.
- **Abbreviations expand at first use** per report or artifact — "Product Requirements Document (PRD)" once, then abbreviate freely. Domain abbreviations too.
- **Domain terms are canonical** per the target repo's glossaries (start at its `GLOSSARY-MAP.md`); workflow terms per the plugin `GLOSSARY.md`. Never coin a synonym for a term either glossary owns.
- **Push notifications** carry subject + status + the plain-terms sentence. Never a bare status token — the human reads these on a phone, away from the repo.
- **Numbers, not adjectives.** "3/9 done, 2 parked", never "most subtasks done".
- **Never invent a status token.** Statuses are owned by each skill's grammar; broadening one is a lockstep change in that skill's own file.
- **Findings lead with severity, ranked worst-first.** A findings list without severity counts in its headline is incomplete.
- **Every item id resolves without memory.** An enumerated-item id (scenario `U1`/`A2`, finding `r-003`, proposal `P2`, subtask `NNNN-slug`) is legal only if its catalogue is already persisted on disk (`VERIFICATION-PLAN.md`, the review/adversary report, `RETRO-*.md`, `plan/`). Never mint a conversation-only id — enumerate, persist the catalogue, then refer. First mention of an id per report carries a ≤6-word gloss — `r-003 (PATCH drops rollbackFor)` — and the pointer layer names the catalogue path (`path`, or `path:line` when citing one item) so the terminal renders it clickable. Later mentions in the same report may use the bare id.
