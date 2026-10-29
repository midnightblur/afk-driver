# Core behaviors load from a plugin hook, never from user files

> Layer: Requirements
> Context ticket: GitHub #153

The core behaviors reach a session only through the afkv2 plugin's session-start hook, on Claude and on Codex. The hook prints one file, finishes in under 50 ms and parses no shell command. Setup writes nothing into the user instruction files. Why: the rules stay in one place and stop when the plugin is off, so there is nothing to maintain or clean up (owner, GRILL-LOG H-1: "clearly a superior solution").

## Considered Options

- Setup writes a rule block into the user instruction files (the v1 way). Rejected by the owner.
