# The note format

The afkv2 agent writes each note to this format. `scripts/dogfood_note.py` checks the note when it is sent and again when it is received; a note that fails a rule is not sent or not applied.

## The grammar

```grammar
afkv2-note v1
kind: milestone | wrap
ask: <ask title, 1 line>
purpose: <the 1 named purpose it is usable for>          (milestone)
changed:                                                  (milestone: 1 row or more)
- <worktree path> | CK-1|CK-2|CK-3|CK-4 | added|changed|removed | <what changed, 1 line>
use: <how to try it, 1 to 5 lines>                        (milestone)
best-effort: <path> - <what may not apply this session>   (1 per CK-4 row)
redo: none | <the delta of earlier work to redo>          (milestone)
changes:                                                  (wrap: 1 row per Draft change)
- <change url> | <branch> | <asks in it>
open-asks: none | <list>                                  (wrap)
```

- Line 1 is the header, exactly. Each other field starts its line with its key and a colon. Blank lines are ignored.
- A `<worktree path>` is the absolute path of the file in its worktree. Write it without ` - `, so that the best-effort line can name it.
- A row of `changed` or `changes` starts with `- ` and separates its columns with ` | `.
- A field with more than 1 line, such as `use`, continues on the next lines, each indented by 2 spaces. A key that comes twice keeps its first value; only `best-effort` repeats.
- A `removed` row names a path that no longer exists. Every other row names a path that exists.
- The change kinds CK-1 to CK-4 are in `APPLY.md`.

## The rule codes

| Rule code | Fails when |
|-----------|------------|
| N-HEADER | line 1 is not the header `afkv2-note v1` |
| N-KIND | the kind is not milestone or wrap |
| N-NO-PATH | a milestone has 0 changed rows |
| N-PATH-OUTSIDE | a path is not absolute and under a worktree that the session state lists |
| N-PATH-MISSING | the path of a row that is not `removed` does not exist |
| N-CK | a change kind is not CK-1 to CK-4 |
| N-NO-USE | a milestone has no use line |
| N-NO-BEST-EFFORT | a CK-4 row has no best-effort line for its path |
| N-NO-REDO | a milestone has no redo line (`redo: none` is valid) |
| N-NO-CHANGES | a wrap has 0 changes rows |

Each failure names its code, its line (`line N`) and a reason. A wrong header or kind is the only failure of its note. A missing field fails on the line of its key, or on the `kind` line when the key is absent.

## Examples

`<worktree>` stands for the absolute path of the worktree.

A milestone with a CK-4 row:

```note
afkv2-note v1
kind: milestone
ask: Show the run link in the report
purpose: open the run from its report
changed:
- <worktree>/skills/report/SKILL.md | CK-1 | changed | the report names the run link
- <worktree>/skills/report/scripts/report.py | CK-2 | added | writes the run link
- <worktree>/hooks/hooks.json | CK-4 | changed | the session hook loads the report
use: Run the report skill on any finished run.
  The report shows the run link in its first line.
best-effort: <worktree>/hooks/hooks.json - the hook may not load until the next session
redo: none
```

A wrap:

```note
afkv2-note v1
kind: wrap
ask: Show the run link in the report
changes:
- https://forge.example/owner/repo/pull/12 | feat/report-link | Show the run link in the report
open-asks: none
```
