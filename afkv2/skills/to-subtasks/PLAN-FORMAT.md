# PLAN.md format

The index of a plan. Each contract has its row in the tracker, and `/afkv2:autopilot` reads the tracker, the `> Division:` line and the `> App:` line. Write the template below; fill each `<...>`.

```markdown plan-template
# Execution plan — <ticket key> — <feature>

> Parent ticket: <ticket key>
> Sources: <path of PRD.md> · <path of SDD.md> · <path of the adr folder>
> Branch: <feature branch>
> App: <address or start command of the running app, or none>
> Last updated: <YYYY-MM-DD>

## Solution map

<one Mermaid flowchart: the components, the subtask that builds each, and the seams>

## Seam register

| § | Seam (SDD row) | Implemented by | Used by |
|---|----------------|----------------|---------|

## Progress tracker

| # | Subtask | Title | Status | Blocked by | Tiers | Seams |
|---|---------|-------|--------|------------|-------|-------|
| 1 | <subtask id> | <title> | pending | <ids or —> | <tiers> | <seams or —> |
```

| Field | Rule |
|-------|------|
| `> App:` | `none` when the repository has no running app. Each live tier of a plan with `none` must read `not applicable: <reason>` ([SUBTASK-CONTRACT.md](SUBTASK-CONTRACT.md)). |
| `> Division:` | Written only by `plan_files.py approve`, after the developer's approval. Without this line the plan is not approved. |
| `Status` | `pending` for each row when you cut the plan. `/afkv2:execute` owns the column after that. |
