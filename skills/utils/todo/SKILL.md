---
name: todo
description: Per-project todo list that survives sessions. Use for /todo, adding/remembering a task for later, or listing what's open.
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

Per-project scratchpad for "do this next, but not now". Plain markdown file. Dead simple.

## Storage

Path: `<cwd>/.claude/TODO.md` (relative to cwd — works per-worktree).

Create `.claude/` dir if missing. Create the file with header `# TODO\n\n` if missing.

Format — markdown checklist, one item per line:

```
# TODO

- [ ] item text (2026-05-08)
- [ ] another item (2026-05-08)
- [x] finished item (2026-05-08)
```

Date in parens = date added. Keep done items in place (checked `[x]`) until user runs `clear`.

## Subcommands

Args parsed from skill invocation. First word = subcommand; rest = payload.

### `add <text>`
Append `- [ ] <text> (<today>)`. Confirm one line: `Added #<n>: <text>`, n = new item's 1-based index among open items.

### `list` (default when no args)
Read the file. Print open items numbered 1..N, then a "Done:" section if any closed items exist. File missing or empty → print `No todos.`

### `done <n>` or `done <text>`
- Numeric: flip n-th open item to `[x]`.
- Text: fuzzy-match against open items; exactly one match → flip. Multiple → list candidates and ask which.
Confirm: `Done: <text>`.

### `clear`
Remove all `[x]` lines. Confirm count removed.

### `rm <n>`
Delete the n-th open item entirely (mistake / no longer relevant). Confirm.

## Intent → subcommand

- Add-shaped intent (remember/save for later) → `add X`
- List-shaped intent (what's open) → `list`
- User finishes a task matching an open todo → suggest `done <n>` (don't auto-mark; ask first).

## Session-start check

No-args invocation always means `list` (see Subcommands). Do NOT proactively read TODO.md without invocation — zero cost when unused.

## Don'ts

- No priorities, tags, due dates, assignees. User wants those → tell them to use a real tracker.
- No syncing to Jira/GitHub. Local file only.
- No backups, no archives. `clear` deletes; user warned by the confirmation count.
- Don't reformat existing items. Preserve user's manual edits.
