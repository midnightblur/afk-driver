# The page shows its git state and warns about secrets in tracked files; neither blocks

> Layer: Requirements
> Context ticket: #163

A human may expect every page to be tracked, and a secret committed to a public repository cannot be fully removed. On each show, the engine reads the page's git state and shows one of 4 lines: committed, in the repository but not committed yet, ignored by git, outside the repository. For each file the round writes inside the repository and not ignored (the page document and the skill's log, which copies notes word for word), the engine scans for a fixed list of about 10 secret shapes and warns on the page and in chat. The agent watches for content with no shape. Neither blocks a round or a commit; the scan costs about 5 ms on a 182 KB page.

## Considered Options

- The agent writes the notice, with no engine part. Rejected by the owner in i-r3-untracked, because a busy agent can forget it.
- The agent alone watches for secrets. Rejected by the owner in i-r5-secret, because a missed token in a pasted log is the irreversible leak, and the scan costs milliseconds.
- Test the page's place in place of its git state. Rejected by the agent, with the owner's accept, in i-r7-d-tracked, because a page in a spec folder is not tracked until committed, and git can ignore a path.
- Scan the page only. Rejected by the agent, with the owner's accept, in i-r7-d-secret, because the log holds the same words and is committed too.
