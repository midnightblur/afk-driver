# Ticket index format — `INDEX.md`

The read-this-first dashboard of a ticket's spec folder. A human/agent landing cold knows in one screen: what the feature is, which artifacts exist and in what state, what order to read them. One line per artifact, no content that lives elsewhere.

## Ownership

Created by PRD synthesis (owns the summary paragraph + seeds **every** row). After that each skill upserts **only its own row(s)** — never another's, never the summary. Rows for artifacts a feature never produces stay `—`. A skill finding no `INDEX.md` creates it from this template (all rows `—`), then fills its own.

| Row | Owner |
|---|---|
| Summary paragraph + `PRD` + `Requirement ADRs` | `/afk-toolkit:to-prd` |
| `PRD` status → `published to Jira {date}` | `/afk-toolkit:to-ticket` |
| `Prototype` | `/afk-toolkit:prototype` |
| `SDD` + `Design ADRs` | `/afk-toolkit:to-sdd` |
| `Design brief` | `/afk-toolkit:to-design-brief` |
| `Verification plan` | `/afk-toolkit:to-verification-plan` |
| `Plan` | `/afk-toolkit:to-subtasks` |
| `Smoke gate` | `/afk-toolkit:smoke-test` |
| `Understanding` | `/afk-toolkit:understand` (upserts only its own row) |
| `Demo plan` | `/afk-toolkit:to-demo-plan` |

## Template

```
# {TICKET-ID} — start here

{One-paragraph feature summary in plain domain language: the problem, the shape of the solution, the user it serves. No workflow vocabulary.}

## Artifacts

| Artifact | Where | State |
|---|---|---|
| PRD | PRD.md | draft | published to Jira {date} |
| Requirement ADRs | adr/requirements/ | {n} records | — |
| Prototype | PROTOTYPE.md | — | chosen {date} |
| SDD | SDD.md | — | draft | approved |
| Design ADRs | adr/design/ | {n} records | — |
| Design brief | DESIGN-BRIEF.md | — | present |
| Verification plan | VERIFICATION-PLAN.md | — | UI only (API deferred) | UI + API |
| Plan | plan/PLAN.md | — | {n} subtasks, {cited|uncited} — live status in the plan's progress tracker |
| Smoke gate | plan/PLAN.md | — | not run | red {date} | green {date} ({full|minimal} gate) |
| Understanding | understanding/index.html | — | generated {date} |
| Demo plan | DEMO-PLAN.md | — | {n} beats / {n} min, written {date} |

## Reading order

1. This file.
2. DESIGN-BRIEF.md if present — the 1–2 page digest; else PRD.md's Problem Statement + User Stories.
3. SDD.md §0 (locked vs free) + §1 (why this design) — full document only if implementing or reviewing design.
4. plan/PLAN.md — solution map + live progress tracker.
5. plan/JOURNAL.md (tail) — what happened lately, in order.
6. plan/review/INDEX.md — what the quality gates found.
7. understanding/index.html — the interactive explainer of what was actually built, once generated.
8. Later: plan/TRACE.md (which commit satisfied which criterion), adr/ (why it's shaped this way).
```

`State` cells show allowed values separated by `|` — a real index carries exactly one. The Reading order block is static boilerplate — copy verbatim; it deliberately lists files that may not exist yet (`—` in the table).
