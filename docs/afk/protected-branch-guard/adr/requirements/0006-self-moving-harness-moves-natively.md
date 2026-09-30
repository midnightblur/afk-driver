# A self-moving harness moves with its native worktree tool

> Status: Accepted
> Audited: 2026-09-29
> Layer: Requirements
> Context ticket: protected-branch-guard (provisional, no ticket)

A refused session on a harness whose agent can move itself (PRD catalog H-1) moves by calling that harness's native worktree tool with a new name; the plugin's worktree-creation hook makes the worktree, and the session continues there. No launch wrapper. The native tool reaches every way the harness starts (terminal, IDE, desktop, herdr) and does not prompt for a new name (live run, 2026-09-29).

## Considered Options

- A launch wrapper that starts each session in a new worktree: rejected; misses IDE and desktop starts and changes the developer's PATH.
- Ask the human to type a folder-switch command: rejected; a human step.
