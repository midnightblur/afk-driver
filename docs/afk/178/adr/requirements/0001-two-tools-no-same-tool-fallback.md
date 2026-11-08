# Claude and Codex as the 2 solution proposers, with no same-tool fallback

> Layer: Requirements
> Context ticket: 178

A design is drafted by 2 solution proposers, 1 Claude and 1 Codex, in parallel. When the other tool or herdr is not available, 1 solution proposer drafts alone; a design session never starts several agents of the same tool. The developer wants a second voice from a different tool, not a second model of the same one.

## Considered Options

- 1 solution proposer, as before. Rejected by the developer in i-parallel, because one voice leaves a better design unseen.
- 2 or 3 agents of the same tool. Rejected by the developer in i-parallel ("do not fallback to multi models from same provider").
- A same-tool critic, off by default and turned on by a repository setting. Rejected by the developer in i-same-tool.
