# Solution proposers always run with full auto-approval, in a throwaway worktree

> Layer: Requirements
> Context ticket: 178

Each solution proposer starts with full auto-approval, Claude with `--dangerously-skip-permissions` and Codex with `--yolo`, in its own throwaway worktree, and only its draft is read back. The page states that the worktree fences only the working folder and is not a sandbox. Where full auto-approval is forbidden, 1 solution proposer drafts alone.

## Considered Options

- Full auto-approval in the session's own worktree, bounded by the brief alone. Rejected by the developer in i-yolo, because a stray write would mix with the session's work.
- The tool's read-only mode. Rejected by the developer in i-yolo, because the draft would come back only through pane output.
- Full auto-approval as a default that a repository setting may lower. Rejected by the developer in i-fence.
