# Every shell command is refused until the session moves

> Status: Accepted
> Audited: 2026-09-29
> Layer: Requirements
> Context ticket: protected-branch-guard (provisional, no ticket)

While a session sits on a protected branch or in the main checkout, the guard refuses every shell command, including read-only ones; only the harness's built-in read tools and its worktree tool pass. A shell command's effect cannot be read reliably from its text, so a list of "safe" commands would leak writes; the built-in read tools cover what an agent needs before it moves.

## Considered Options

- Refuse only commands that look like writes (the repository prototype's git-command pattern): rejected; redirects, scripts and tools write without matching any pattern.
