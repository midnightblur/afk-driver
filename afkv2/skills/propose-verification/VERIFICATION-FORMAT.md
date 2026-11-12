# VERIFICATION.md format

`scripts/verification_files.py write` writes `VERIFICATION.md` from a plan file (JSON). Never edit the file by hand: its readers parse it. This page gives the plan file, the written file, and each refusal.

## The plan file

```json
{
  "ticket": "<ticket key>",
  "app": "config",
  "rows": [{"id": "VR-001", "criteria": ["AC-001"], "story": "1", "given": "...", "when": "...", "then": "...",
            "level": "ui-e2e", "data": "...", "environment": "...", "status": "active"}],
  "internal": [{"criterion": "AC-004", "why": "..."}],
  "boundaries": [{"boundary": "...", "contract": false, "rows": ["VR-002"], "ticket": "..."}]
}
```

- `app`: `"config"`, the proven live block of the repository config, or `{"none": "<card id>"}`, a card that the developer settled with an `accept` mark.
- `internal`: each acceptance criterion with no user-visible outcome, with why. Every other active criterion of the PRD is user-visible.
- `boundaries`: each service boundary that the change crosses. `contract` true: the repository has contract tests there.

### The plan row (VR-NNN)

| Field | Value |
|-------|-------|
| `id` | `VR-NNN`, 3 digits. Never change or reuse an id. Retire a row in place. |
| `criteria` | a list of PRD ids `AC-NNN`. Empty only on a low-level row with no user-visible outcome. |
| `story` | the story number or the journey name, or null; a number is written as text |
| `given`, `when`, `then` | 1 sentence each. `then` is what you should see; the judge compares to it. |
| `level` | `static`, `unit`, `integration`, `contract` (tier low); `api`, `ui-e2e`, `acceptance` (tier high) |
| `tier` | optional; derived from `level`. A mismatch refuses. |
| `data`, `environment` | the test data and the environment, or null |
| `status` | `active`, `retired: <why>`, or `lower: <from> to <to> · <card id>` |

A row has no owner: the plan cut gives each row its subtask.

The level of a row is its highest-value level ([LEVELS.md](LEVELS.md)). A row that repeats a cheaper row just as faithfully is a critique point.

`lower: <from> to <to> · <card id>`: the developer accepted the lower level `<to>` in place of `<from>`, by an `accept` mark on that card; an option letter accepts nothing. `level` is `<to>`. A `lower:` row counts as live, as an `active` row does.

## The written file

```markdown
# Verification plan — <ticket key>

> Parent PRD: PRD.md
> Parent SDD: SDD.md
> App: config · proven at <proven_head> on <proven_at>
> Last updated: <date>

## Plan rows

| Id | Criteria | Story | Given | When | Then | Level | Tier | Data | Environment | Status |
|----|----------|-------|-------|------|------|-------|------|------|-------------|--------|

## Criteria with no user-visible outcome

| Criterion | Why |
|-----------|-----|

## Boundaries

| Boundary | Contract test | Rows | Ticket |
|----------|---------------|------|--------|
```

`> App: none · <card id>` replaces the config line when the build has no live app. An empty cell holds `—`. A `|` inside a cell is `\|`. Readers read the columns by header name, so a new column goes at the right end.

## Refusals of write

| Code | Cause |
|------|-------|
| `bad-payload` | the plan file is not the shape above |
| `bad-row` | a row field breaks the plan row table, or an id repeats |
| `tier-mismatch` | `tier` does not match `level` |
| `row-dropped` | a row id of the current file is missing; retire it instead |
| `criterion-unknown` | a criterion is not in the PRD |
| `criterion-retired` | an active row names a retired criterion |
| `ac-no-high-row` | a user-visible criterion has no active high-level row; a `lower:` row from a high level counts |
| `lower-level-unmarked` | a `lower:` card is not settled by the developer's mark |
| `boundary-uncovered` | a boundary with a contract test has no live contract row; one with none has no ticket or no live high-level row (the API level is the floor) |
| `live-unproven` | `app` is `config` and the live block was not proven at a commit of this feature, or `app` is `none` and its card has no `accept` mark of the developer |
| `bad-index` | `INDEX.md` exists and has no artifact table: `/afkv2:to-prd` writes it |
| `no-target` | no default target branch exists: pass `--target` with the branch the feature merges into |
| `git-failed`, `unreadable`, `bad-verification` | git failed, or the current VERIFICATION.md cannot be read or has no plan rows table: report the reason |
