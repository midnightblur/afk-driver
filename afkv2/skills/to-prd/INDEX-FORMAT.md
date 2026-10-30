# INDEX.md format

The read-first page of a ticket's spec folder: what the feature is, which artifacts exist, in what state, and in what order to read them. One line per artifact. Nothing here repeats content of another file.

Each skill writes only its own rows, with `prd_files.set_row`. A row for an artifact the feature never makes stays `—`. to-prd writes the summary paragraph, and seeds every row from the template below through `prd_files.py index`, so the template is the one copy.

| Row | Writer |
|-----|--------|
| summary, `PRD`, `Requirement ADRs` | `/afkv2:to-prd` |
| `SDD`, `Design ADRs` | `/afkv2:propose-solution` |
| `Plan` | `/afkv2:to-subtasks` |

## Template

```markdown index-template
# {TICKET-ID} — start here

## Artifacts

| Artifact | Where | State |
|---|---|---|
| PRD | PRD.md | — |
| Requirement ADRs | adr/requirements/ | — |
| Prototype | PROTOTYPE.md | — |
| SDD | SDD.md | — |
| Design ADRs | adr/design/ | — |
| Design brief | DESIGN-BRIEF.md | — |
| Verification plan | VERIFICATION-PLAN.md | — |
| Plan | plan/PLAN.md | — |
| Smoke gate | plan/PLAN.md | — |
| Understanding | understanding/index.html | — |
| Design review plan | DESIGN-REVIEW-PLAN.md | — |
| Demo plan | DEMO-PLAN.md | — |

## Reading order

1. This file.
2. DESIGN-BRIEF.md if present, else the Problem Statement and User Stories of PRD.md.
3. SDD.md §0 and §1; the full document only to implement or review the design.
4. plan/PLAN.md: solution map and live progress.
5. plan/JOURNAL.md (tail): what happened lately.
6. plan/review/INDEX.md: what the quality checks found.
```

State values: `PRD` is `draft` or `published to Jira <date>`. `Requirement ADRs` is `<n> records`.
