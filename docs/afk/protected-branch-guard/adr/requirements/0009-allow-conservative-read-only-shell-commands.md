# Allow conservative read-only shell commands before the session moves

> Status: Accepted
> Layer: Requirements
> Context ticket: protected-branch-guard (provisional, no ticket)

In the main checkout or on a protected branch, the guard allows one recognized read-only shell command. It refuses composition, redirection, unknown programs, and write-capable commands. This permits inspection before the first change without allowing a command that can change repository state.

## Considered Options

- Refuse every shell command: rejected because it blocks repository and forge inspection.
- Infer every command's effects: rejected because shell text cannot prove arbitrary programs are read-only.
