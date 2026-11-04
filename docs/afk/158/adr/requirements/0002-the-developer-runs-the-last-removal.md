# The developer runs the last removal with gc's own command

> Layer: Requirements
> Context ticket: 158

The session process keeps the feature worktree as its working folder until it exits, and Windows refuses to remove a folder that a live process uses. So gc cannot remove the worktree of the session that runs it. gc removes everything else, then gives the developer one command of its own for the feature worktree and its local branch. The developer runs it after the session closes. The command uses the same in-use check as gc, because a plain git removal of a folder in use deletes its files part way.

## Considered Options

- A session-end hook removes them. Rejected by the developer in i-self, because the hook does not fire when the terminal is closed, and a session can end with the work not done.
- A background process waits for the session end, with a check at the next session start as a fallback. Rejected by the developer in i-self3: the human effort of one command is small, and the survival of such a process on Windows was not proved.
- A check at the next session start only. Rejected by the developer in i-self3: the folder stays until the next session starts.
