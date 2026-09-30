# A refused fixed-folder agent inside herdr moves itself by typing /cd

> Status: Accepted
> Layer: Requirements
> Context ticket: protected-branch-guard (provisional, no ticket)

On a harness whose agent cannot change its session folder (PRD catalog H-2), the session starts in a new worktree through the plugin's launch command. A session that starts in the wrong place anyway is refused; inside herdr the agent types `/cd <worktree>` into its own pane, so no human step is needed; outside herdr the refusal prints the `/cd` line for the human. Only `/cd` moves such a session and keeps the conversation.

(unverified premise: an H-2 agent's keystrokes into its own herdr pane run `/cd` once its turn ends)

## Considered Options

- Start in a worktree; outside the plugin's launch command, the human types the printed `/cd` line: rejected; leaves a human step inside herdr.
- The harness's own worktree option: rejected; the worktree has no branch.
