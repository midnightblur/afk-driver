---
name: todo
description: >
  Quick per-project todo list that survives sessions. Stored at
  `<cwd>/.claude/TODO.md`. Use when user invokes `/todo`, says "add a
  todo", "remind me later", "save for later", "don't forget", "note that
  down", "what's open", "any open todos", "what was I going to do", or
  starts a session in a project that has open todos.
---

Per-project scratchpad for "do this next, but not now". Plain markdown file. Dead simple.

## Storage

Path: `<cwd>/.claude/TODO.md` (relative to current working directory — works naturally per-worktree).

Create the `.claude/` dir if missing. Create the file with header `# TODO\n\n` if missing.

Format — markdown checklist, one item per line:

```
# TODO

- [ ] item text (2026-05-08)
- [ ] another item (2026-05-08)
- [x] finished item (2026-05-08)
```

Date in parens = date added. Keep done items in place (struck through by `[x]`) until user runs `clear`.

## Subcommands

Args parsed from skill invocation. First word = subcommand; rest = payload.

### `add <text>`
Append `- [ ] <text> (<today>)` to the file. Confirm with one line: `Added #<n>: <text>` where n is the new item's 1-based index among open items.

### `list` (default when no args)
Read the file. Print open items numbered 1..N, then a "Done:" section if any closed items exist. If file missing or empty → print `No todos.`

### `done <n>` or `done <text>`
- Numeric: flip the n-th open item to `[x]`.
- Text: fuzzy-match against open items; if exactly one match, flip it. If multiple, list candidates and ask which.
Confirm: `Done: <text>`.

### `clear`
Remove all `[x]` lines. Confirm count removed.

### `rm <n>`
Delete the n-th open item entirely (mistake / no longer relevant). Confirm.

## Auto-trigger behaviors

Beyond `/todo` slash invocation, recognize these intents and call this skill:

- User says "remind me to X later", "add todo X", "don't forget X", "note that down" → `add X`
- User says "what's open", "any todos", "what was I going to do", "open items" → `list`
- User finishes a task that matches an open todo → suggest `done <n>` (do not auto-mark; ask first).

## Session-start check

When this skill is invoked with no args at session start, also surface count of open todos so the user remembers they exist:

> 3 open todos in this project. Run `/todo list` to see them.

Do NOT proactively read TODO.md every session without invocation — only when the skill is called. Keep cost zero when unused.

## Don'ts

- No priorities, tags, due dates, assignees. If user wants those, tell them to use a real tracker.
- No syncing to Jira/GitHub. Local file only.
- No backups, no archives. `clear` deletes; user warned by the confirmation count.
- Don't reformat existing items. Preserve user's manual edits.
