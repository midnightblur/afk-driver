# The guard refuses identified mutations of guarded resources, not shell syntax

> Status: Accepted; superseded in part by ADR-0014 (a shell command that runs in a guarded placement must be proven read-only)
> Supersedes: ADR-0009 (ADR-0003 stays as history, already superseded by ADR-0009)
> Layer: Requirements
> Context ticket: protected-branch-guard (provisional, no ticket)

The guard refuses a tool call only when it identifies a mutation whose resource is guarded. It judges the resource, never the shape of the command. Composition (`&&`, `||`, `;`, `|`, `&`, newline), `2>&1`, `>/dev/null`, executable paths, unknown programs, forge and herdr commands, and paths outside every repository all pass. This removes the read allowlist of ADR-0009, which refused common read commands (a pipe, a redirect to the null device) and trained agents to work around the guard.

A **guarded resource** is the main checkout on any branch, a linked worktree on a protected branch, or a linked worktree another live session uses ([ADR-0013](0013-linked-worktree-occupancy.md)).

## Decision

- **Edit tools** are judged at every resolved target, not at the session folder. A target outside every repository passes, even from a main-checkout session (scratchpad and memory files).
- **Shell commands** are judged at the literal paths a recognizer finds in high-confidence forms. The recognizer is not a shell parser; `hooks/lib/shell_mutations.py` and its tests own the exact forms. The classes are: git verbs that write the repository, file writers with a literal target (redirects, `tee`, `cp`, `mv`, `rm`, `touch`, `ln`, `sed -i`, PowerShell writers and their aliases), and wrappers that move the folder (`cd`, `git -C`, `env -C`, `--git-dir`, `--work-tree`). A target built from a variable, a substitution, or a glob is opaque and passes outside a guarded placement. Inside one, [ADR-0014](0014-refuse-unproven-shell-commands-before-they-run.md) refuses every segment it cannot prove read-only.
- **Other tools** (MCP, unknown built-ins) are judged at any top-level string value whose key contains `path` or `file`. A tool with no such key is an external service and passes.
- **A fault** fails closed only for an identified mutation, and only when any identified target lies inside a git work tree by file layout. Any other call passes when the guard cannot compute a verdict. A hint that cannot be built never changes a verdict.
- **The refusal names a runnable move.** A session in a guarded placement gets the move for its harness class. A session in an unprotected linked worktree that targets a path elsewhere is told to write inside its own worktree. The plugin's own `scripts/create-worktree` passes (it is an unrecognized program). A refused `git pull` that is not the allowed sync names the sync form ([ADR-0011](0011-main-checkout-fast-forward-sync.md)).
- `AFK_ALLOW_PROTECTED=1` at launch still passes every placement.

## Considered Options

- Keep the read allowlist and add forms to it: rejected. Every omission refuses a harmless command, and the list never ends.
- Parse the full shell grammar: rejected. The cost is large and a parser still cannot see inside a script or a tool.
- Refuse what looks like a write by pattern: rejected in ADR-0003 and again here as the sole defense. A pattern misses scripts; ADR-0014 refuses an unproven command in a guarded placement before it runs.
- Judge the resource and detect the rest after the call (chosen).

## Accepted gaps

The guard guards against forgetting, not intent ([ADR-0005](0005-guard-against-forgetting-not-intent.md)). These forms pass the recognizer by design:

- Opaque targets (variables, substitutions, globs).
- A failed `cd` followed by `||`: the later segment is judged in the folder the `cd` named.
- Only a `|` pipeline marks a subshell. A background `&` and a `$(...)` do not scope a folder change.
- An unquoted parenthesis inside a word splits the word (an unquoted `sed` group); quote it.
- A path-qualified program is recognized by its base name, so `/usr/bin/git commit` is refused.
- `git gc`, `prune` and `repack` pass. `git notes --ref <name> add` reads as a non-mutation.
- `--git-dir=<common>/worktrees/<id>` resolves to the outer repository, not the named linked worktree. The refusal errs to the safe side.
- `git branch` with `--set-upstream-to`, `-u`, `--unset-upstream` or `--edit-description` is a branch-config mutation, not a read.
- A literal `-WhatIf` (or `-WhatIf:$true`) makes a cmdlet (`Verb-Noun`) or a PowerShell-only alias (`ri`, `del`) a non-mutation in any shell; `-WhatIf:$false` does not. Names a Unix shell shares (`rm`, `cp`, `mv`, `mkdir`, `tee`) count only in the `PowerShell` tool. `touch`, any `.exe` name and any other program stay ordinary writers.
- A folder change inside `( )` ends at the `)` for a Bash-class tool and persists for the `PowerShell` tool. `sudo -D <dir>` and `--chdir` move the wrapped command's folder.
- The entry file refuses inside a work tree when the judge module cannot load (a broken install, not a computed verdict).

## Consequences

Agents read and compose in every placement. Build tools and other unlisted programs run in the main checkout only until [ADR-0014](0014-refuse-unproven-shell-commands-before-they-run.md): since then they need a linked worktree.
