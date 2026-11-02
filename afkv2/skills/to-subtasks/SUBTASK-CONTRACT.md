# Subtask contract (`plan/NNNN-<slug>.md`)

`/afkv2:autopilot` and `/afkv2:execute` parse these headings exactly. `check_plan.py` reads the heading list from the template below, so a heading changes here and in `plan_contract.py` of `/afkv2:autopilot` in one commit. Text in `<...>` is guidance: replace it. The subtask id is the file name without `.md`.

```markdown contract-template
## Goal
<one paragraph: what this subtask delivers>

## Complexity
<one word: mechanical (rename, config, doc; no design judgment), standard (the default) or complex (several seams, concurrency, wide effect of a fault)>

## Review
<optional: one line for the reviewer about this slice; omit the section by default>

## Design refs
- SDD: SDD.md#§<N> <heading words> — <what it binds>
- ADR: adr/design/NNNN-<name>.md — <what it binds>

## Scope
- <glob>

## Seams
<each SDD §9b or §14 seam this subtask touches, or `(none)`>
- implement: <seam row> — this subtask owns the code and the seam test
- use: <seam row> — this subtask calls across it and keeps its contract

## Acceptance
<each bullet is a pass or fail statement a reader understands without the cited document, and ends with a citation>
- [ ] <criterion> (PRD §AC-NNN)
- [ ] <criterion> (SDD §<N> row "<row name>"; ADR-NNNN design)

## Produces
<one bullet for each artifact a consumer can see>
- <file>#<grep anchor> — <one-line contract>

## Consumes
<optional: one bullet for each artifact of an earlier subtask this one reads>
- <producer id> <file>#<grep anchor> — <what this subtask expects>

## Verification
<one row per tier; `static` is always present>
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `<compile or lint command>`; grep each `## Produces` anchor | the code builds; the declared symbols exist |
| unit | `<test command>` | <behavior> |
| api | not applicable: <why the repository cannot run this gate> | <what a run would prove> |

## Context excerpts
<word-for-word quotes the executor works from, each with its citation>
> (PRD §AC-NNN) <quote>
> (SDD §<N> row "<row name>") <quote>

## Parent PRD
<the `parent_prd` path that `start` answered>

## Parent SDD
<the `parent_sdd` path that `start` answered>

## Blocked by
<one bullet per subtask id, or `(none)`>
- <subtask id>

## Conflict procedure
If a binding decision in the SDD or an ADR is wrong, cannot be built or contradicts the code, classify it by `DOORS.md` of `/afkv2:autopilot`. A two-way door: `decide`, then implement the recorded call. A one-way door or a tie: `park`, quoting the SDD section and the conflict; the decision goes back to `/afkv2:propose-solution` for a new ADR. Never override a binding decision off the record.
```

## Rules for the fields

| Field | Rule | Checked by |
|-------|------|------------|
| `Produces`, `Consumes` | A `Consumes` line names a `Produces` bullet of a subtask with a lower number, word for word. Two subtasks never produce one anchor. | `check_plan.py` (a) |
| grep anchor | At least 12 characters, not a bare keyword, and at most 1 match in its file. | `check_plan.py` (b) |
| `Verification` check cell | A command in a code span, a method, or `not applicable: <reason>`. | `check_plan.py` |
| a gate the repository cannot run | Write its check cell as `not applicable: <reason>`, with these exact words and a reason. `/afkv2:execute` does not run that row. A live tier (`api`, `e2e`, `browser`, `e2e/browser`, `ui-e2e`) cannot run when the `> App:` line of PLAN.md reads `none`. A command cannot run when its program is not on the PATH. | `check_plan.py`; lockstep copy of `NOT_APPLICABLE` and `LIVE_TIERS` in `start_gate.py` of `/afkv2:autopilot` |
| a path in a check cell | The Scope of this subtask or of a subtask it waits on owns the path, or the file is already on the feature branch. | `check_plan.py` |
| `Acceptance` citation | Each bullet ends with a citation that resolves: `PRD §<id>`, `SDD §<N>` with optional `row "<text>"`, `ADR-NNNN design` or `ADR-NNNN requirements`. Parts are separated by `;`. `PLAN.md decision <id>` may stand beside one of these. | `plan_files.py citations` |
| `Context excerpts` | Quotes only, selected while the sources are open. | you |
