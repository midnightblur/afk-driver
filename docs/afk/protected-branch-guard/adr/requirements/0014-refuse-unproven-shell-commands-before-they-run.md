# In a guarded placement, a shell command runs only when the guard proves it read-only

> Status: Accepted
> Supersedes: ADR-0012; ADR-0010 in part (an unknown program, an opaque target or a composition that runs in a guarded placement no longer passes)
> Layer: Requirements
> Context ticket: protected-branch-guard (provisional, no ticket); GitHub issue #99

[ADR-0010](0010-refuse-mutations-not-syntax.md) let a command the recognizer could not read run in a guarded checkout, and [ADR-0012](0012-change-meter-and-quarantine.md) detected its change after the call and held the session. The hold refused read-only commands too, it was chosen from the session folder and not from the command's target, and its recovery list had no move command. A held session could neither inspect nor finish its task (issue #99). The guard now refuses before the change, never after it.

A **guarded placement** is the main checkout on any branch, or a linked worktree on a protected branch.

## Decision

- **The rule.** Each segment of a shell command runs in a folder: the session folder, moved by a literal `cd`, `pushd`, `popd`, `Set-Location`, `env -C` or `sudo -D`, and for `git` by `-C`, `--git-dir` or `--work-tree`. A segment whose folder lies in a guarded placement runs only when the allow-list proves it read-only. Otherwise the guard refuses the whole command before it runs. The refusal names the first unproven segment and the move for the session's harness class. A folder the text does not name literally counts as the session folder.
- **The allow-list** is `hooks/lib/read_only.py`; its tests own the exact forms. It lists file readers (`ls`, `cat`, `head`, `tail`, `wc`, `stat`, `grep`, `rg` without `--pre`, `jq`, `diff`, and similar), `find` without a write action, `sed` without `-i`, a script file, or a script that holds `w`, `W` or `e`, `curl` without an output, upload or method flag, read-only `git` verbs (no `-c`, no `--output`, `fetch` with no `:` refspec), forge reads (`gh` and `glab` `view`, `list`, `status`, `checks`, `diff`, `show`, `watch`, and `api` without a write flag), `docker` `ps`, `logs`, `inspect` and `images` with their `container`, `image` and `compose` forms, PowerShell `Get-*` and the listed cmdlets without a script block, shell control words, and `herdr`. A redirect into a file, a command substitution, a path-qualified program and an unlisted program are unproven.
- **A literal target decides.** A segment whose every word is literal, and which is a known file writer (redirect, `tee`, `cp`, `mv`, `rm`, `touch`, `mkdir`, `ln`, the PowerShell writers) or a proven read with file redirects, is judged at its targets by the resource rule of ADR-0010, not at its folder. A command aimed at a folder outside every guarded placement is not refused because the session sits in one. `sed -i` and `perl -i` are judged at their folder, because a script can run a program.
- **Also allowed in a guarded placement:** the plugin's `scripts/create-worktree`, by its literal path or under `$AFK_PLUGIN_ROOT`, and the sync of [ADR-0011](0011-main-checkout-fast-forward-sync.md).
- **Edit tools and other tools** are judged at their targets, as ADR-0010 decides.
- **Outside a guarded placement** ADR-0010 applies: an identified mutation of a guarded resource or of an occupied worktree ([ADR-0013](0013-linked-worktree-occupancy.md)) is refused, and an unknown program passes.
- **A fault** while the guard computes the placement of an unproven segment fails closed inside a git work tree.
- `AFK_ALLOW_PROTECTED=1` at launch passes every placement. The lavish rule still applies.
- **Retired:** the change meter, its snapshot, blob store, quarantine record and recovery text, and the `PostToolUse` handler `hooks/protected-branch-meter.py`.

## Considered Options

- Keep the meter and repair the hold (allow reads, judge by target, list move commands): rejected by the owner. Detection comes after the first write.
- Refuse every shell command in a guarded placement ([ADR-0003](0003-refuse-every-shell-command.md)): rejected. It blocks inspection.
- Prove read-only against a maintained allow-list and refuse the rest before the call (chosen).

## Accepted gaps

The guard guards against forgetting, not intent ([ADR-0005](0005-guard-against-forgetting-not-intent.md)):

- A listed program can act through its environment or configuration: the repository's git configuration (pager, file-system monitor, external diff), `PATH`, `LD_PRELOAD`.
- `herdr` stays listed. It changes no file itself; the text it types into another pane is judged by that pane's own guard, and not at all in a plain shell.
- A program that runs from a folder outside every guarded placement can write into one through a path inside its own code (a script, a build tool).
- A segment after a control word (`then rm x`) is judged at its folder, not at its targets.
- A `sed` script that holds `w`, `W` or `e` is refused even when the letter is part of a pattern.
- A PowerShell script block (`Where-Object { … }`) is unproven.
- An unproven segment in a linked worktree costs one forge protection lookup, reused for up to 5 minutes ([ADR-0004](0004-protected-list-asked-live.md)).

## Consequences

In the main checkout or on a protected branch, an agent runs builds, tests, scripts and every unlisted program only after it moves into a linked worktree. Reads, forge and git inspection, the move and the sync run in place. A session is never held.
