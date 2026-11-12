# PLAN.md format

The index of a plan. Each contract has its row in the tracker, and `/afkv2:autopilot` reads the tracker, the `> Division:` line and the `> App:` line. Write the template below; fill each `<...>`.

```markdown plan-template
# Execution plan — <ticket key> — <feature>

> Parent ticket: <ticket key>
> Sources: <path of PRD.md> · <path of SDD.md> · <path of the adr folder>
> Branch: <feature branch>
> App: config
> Rules: 2
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
| `> App:` | `config`: the live block of `.afkv2/config.json`, proven by `/afkv2:propose-verification`; the start gate starts it once. `none` when the repository has no running app. An older plan may name an address. |
| `> Rules:` | `2` on every plan you cut. It selects the plan row rules of [SUBTASK-CONTRACT.md](SUBTASK-CONTRACT.md). A plan with no line keeps the older rules. |
| `> Division:` | Written only by `plan_files.py approve`, after the developer's approval. Without this line the plan is not approved. |
| `Status` | `pending` for each row when you cut the plan. `/afkv2:execute` owns the column after that. |
