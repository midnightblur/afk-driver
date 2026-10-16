# In a guarded placement, a shell command runs only when the guard proves it read-only

> Status: Accepted
> Supersedes: ADR-0012; ADR-0010 in part (an unknown program, an opaque target or a composition that runs in a guarded placement no longer passes, and its detection after the call)
> Layer: Requirements
> Context ticket: protected-branch-guard (provisional, no ticket); GitHub issue #99

[ADR-0010](0010-refuse-mutations-not-syntax.md) let a command the recognizer could not read run in a guarded checkout, and [ADR-0012](0012-change-meter-and-quarantine.md) detected its change after the call and held the session. The hold refused read-only commands too, it was chosen from the session folder and not from the command's target, and its recovery list had no move command. A held session could neither inspect nor finish its task (issue #99). The guard now refuses before the change, never after it.

A **guarded placement** is the main checkout on any branch, or a linked worktree on a protected branch.

## Decision

- **The rule.** Each segment of a shell command runs in a folder: the session folder, moved by a literal `cd`, `pushd`, `popd`, `Set-Location`, `env -C` or `sudo -D`, and for `git` by `-C`, `--git-dir` or `--work-tree`. A segment whose folder lies in a guarded placement runs only when the allow-list proves it read-only. Otherwise the guard refuses the whole command before it runs. The refusal names the first unproven segment and the move for the session's harness class.
- **An unknown folder stays unknown.** An opaque `cd`, `pushd`, `Set-Location` or `env -C` target, `cd -`, and a `pushd` or `popd` that moves only the stack (`-n`, `+N`, `-N`) leave the folder unknown. In every placement, each later unproven segment is refused until a literal folder change restores a known one. One substitution is known: a `cd` target of exactly `$(git rev-parse --show-toplevel)` or `` `git rev-parse --show-toplevel` ``, with an optional suffix of letters, digits, `.`, `_`, `-` and path separators and no git variable set, is the current folder's work-tree root as the guard's own git lookup finds it. Any other suffix leaves the folder unknown; a second, literal `cd` reaches a folder whose name holds a space.
- **Git variables aim git.** `GIT_DIR`, `GIT_WORK_TREE` and `GIT_COMMON_DIR`, set as a prefix, through `env`, by `export NAME=value`, by `NAME=value` then `export NAME`, or by PowerShell `$env:`, add their value to the segment's folders until `unset [-v|--] NAME…` or `export -n NAME…` with plain names removes it; `unset -f NAME…` with plain names leaves them as they were. Any other `unset` or `export -n` shape leaves every git variable unknown until a plain `unset` names it. A relative value under `git -C` resolves against the `-C` folder, as git 2.53 does. A literal value is judged there; an opaque value, an exported name with no known value, or two values for one name leaves the folder unknown.
- **Links resolve.** A target or folder with a symbolic link or junction on its path is judged at its resolved path.
- **The allow-list** is `hooks/lib/read_only.py`; its tests own the exact forms. It lists file readers (`ls`, `cat`, `head`, `tail`, `wc`, `stat`, `grep`, `rg` without `--pre`, `jq`, `diff`, and similar), `find` without a write action, `sed` without `-i`, a script file, or a script that holds `w`, `W` or `e`, `curl` without an output, upload or method flag, read-only `git` verbs (no `-c`, no `--output`, `fetch` with no `:` refspec), forge reads (`gh` and `glab` `view`, `list`, `status`, `checks`, `diff`, `show`, `watch`, and `api` without a write flag), `docker` `ps`, `logs`, `inspect` and `images` with their `container`, `image` and `compose` forms, listed built-in PowerShell read cmdlets (`Get-ChildItem`, `Get-Content`, `Get-Item` and the others the tests own) without a script block, shell control words, and the `herdr` read forms checked against `herdr --help` (`status`, the `list` and `get` forms, `pane read`, `agent read`, `worktree list` without `--trust-repository`, and the others the tests own). A redirect reaches no file only at a literal `/dev/null`, `/dev/stdout`, `/dev/stderr`, `/dev/tty` or `nul`, or, in PowerShell, at the unquoted `$null`; a quoted `$null` and a Bash `$null` are files. A redirect into a file, a command substitution (`$(` or a backtick outside single quotes and escapes, also as an input redirect's target), a path-qualified program and an unlisted program are unproven. So are an opaque argument to a form whose flags decide whether it writes or runs a program (only the plain readers keep opaque paths), except in a value-only position: the operand of `find -name`, `-iname`, `-path`, `-ipath` or `-type` when the expansion is quoted, and any word after the literal `--` of a literal `gh pr|issue|run|release|repo view` or `glab mr|issue|release|repo view`, which the forge takes as the operand, never as a flag. A proven `view` may start a browser through `-w` or `--web`; it writes nothing in a repository. An unquoted heredoc whose body holds `$(`, a backtick or `<(`, and `env -S`.
- **A literal target decides.** A segment whose every word is literal, and which is a known file writer (redirect, `tee`, `cp`, `mv`, `rm`, `touch`, `mkdir`, `ln`, the PowerShell writers) or a proven read with file redirects, is judged at its targets by the resource rule of ADR-0010, not at its folder. A command aimed at a folder outside every guarded placement is not refused because the session sits in one. `sed -i` and `perl -i` are judged at their folder, because a script can run a program.
- **Also allowed in a guarded placement:** the plugin's `scripts/create-worktree` at a proven plugin path, the sync of [ADR-0011](0011-main-checkout-fast-forward-sync.md), a `git [-C <folder>] worktree move|remove` or `git [-C <folder>] branch -d` written wholly in literal words, with no prefix, git variable or redirect into a file, and with exactly the operands its parsed operation holds, judged at each of them, and the plugin script forms below.
- **A proven plugin path** is a literal path, or `$AFK_PLUGIN_ROOT` (or a harness's own plugin-root variable) plus a literal rest, that resolves under the guard's own plugin root: the folder the guard runs from. The variable reads as that root, whatever any environment holds, and counts only when the command names it nowhere else (no prefix, `env`, `export`, assignment or `${NAME:=…}`). After a segment that creates a link (`ln`, `mklink`, or a `New-Item` whose one type option is not literally `Directory` or `File`, since it takes abbreviated link types), writes inside or above that root, or writes a target the guard cannot resolve, no later segment of the command runs at a proven plugin path.
- **Plugin script forms.** A plugin script at a proven plugin path, in an exact mode with literal arguments and no file redirect, is judged at the paths that mode writes. Each mode was read for its writes:

  | Form | Writes | Proof |
  |---|---|---|
  | `afk-python …/mission_control.py <spec> --check-digests` | nothing | `mission_control.py` returns after the digest check; `mc/digests.py` reads only |
  | `afk-python …/mission_control.py <spec>` (`--once`, `--port N`) | `<spec>/plan/mission-control/index.html`: judged at `<spec>` | `mission_control.py` render path; `mc/server.py` writes only that page |
  | `afk-python …/scripts/lavish_show.py <page>` (`--no-open`, `--reopen`), `poll <page>` (`--agent-reply`) | the page and a temporary file beside it: judged at the page | `scripts/lavish/inject.py` atomic replace; `lavish-axi` writes only under its state directory (`~/.lavish-axi`) |
  | `afk-python …/scripts/lavish_show.py stop`, `playbook [id]`, `end <page>` | nothing in a repository | the wrapper passes through; `lavish-axi` writes only its state directory |
  | `afk-python …/scripts/glossary_usage.py [root]`, `root` literal or exactly the proven `"$AFK_PLUGIN_ROOT"` | nothing | reads and prints |
  | `afk-python …/skills/afk/setup/scripts/python_runtime.py check` (`--test`) | nothing | `check` reads; `--test` adds the test extra to `uv sync --check --offline` and the test imports to the probe; only `install` writes |
  | `afk-python …/scripts/behavior_registry.py validate` or `audit` | nothing | both read; only `render --output` writes |
  | `bash …/hooks/lesson-digest.sh` (`--count`, `--all`) | nothing | reads the ledger and runs `git rev-parse` |
  | `bash …/hooks/gate-metrics-report.sh [file]` | nothing | reads the metrics file |

  Every other plugin script needs a linked worktree in a guarded placement: `native-contract-gate.sh` writes git's gate cache, `lesson-append.sh` the main checkout's ledger, the setup fixes and `developer_values.py set` git's configuration directory, and `gc` commits. The skills that run them say to move first, pointing at `SAFETY.md` "Worktree per session".
- **Edit tools and other tools** are judged at their targets, as ADR-0010 decides.
- **Outside a guarded placement** ADR-0010 applies: an identified mutation of a guarded resource or of an occupied worktree ([ADR-0013](0013-linked-worktree-occupancy.md)) is refused, and an unknown program passes.
- **A fault** while the guard computes the placement of an unproven segment fails closed inside a git work tree.
- `AFK_ALLOW_PROTECTED=1` at launch passes every placement. The lavish rule still applies.
- **Retired:** the change meter, its snapshot, blob store, quarantine record and recovery text, and the `PostToolUse` handler `hooks/protected-branch-meter.py`.

## Considered Options

- Keep the meter and repair the hold (allow reads, judge by target, list move commands): rejected by the owner. Detection comes after the first write.
- Refuse every shell command in a guarded placement ([ADR-0003](0003-refuse-every-shell-command.md)): rejected. It blocks inspection.
- Prove read-only against a maintained allow-list and refuse the rest before the call (chosen).
- Plugin scripts: require a worktree for every one (rejected: status, digest and render checks would stop in the main checkout), or allow each mode whose writes a reading of the script bounds, judged at those writes (chosen).

## Accepted gaps

The guard guards against forgetting, not intent ([ADR-0005](0005-guard-against-forgetting-not-intent.md)):

- A listed program can act through its environment or configuration: the repository's git configuration (pager, file-system monitor, external diff), `PATH`, `LD_PRELOAD`.
- Git's optional index refresh and stat-cache writes during a listed read (`git status`, `git diff`), and `git fetch` without a destination refspec, which writes only `FETCH_HEAD`, objects and remote-tracking refs. No local branch, index entry or work-tree file changes.
- A git variable set by `declare -x`, `typeset -x` or `set -a`, or inherited from the session, is not seen.
- A plugin script form acts through its environment: `LAVISH_AXI_STATE_DIR` pointed into a repository moves the lavish state there.
- The guard reads a plugin-root variable as its own root. A shell whose variable names another folder runs that folder's script.
- The guard reads `unset`, `export` and `cd` as the shell builtins. A function or alias of that name defined earlier in the command changes what the word does.
- A program that runs from a folder outside every guarded placement can write into one through a path inside its own code (a script, a build tool).
- A segment after a control word (`then rm x`) is judged at its folder, not at its targets.
- A `sed` script that holds `w`, `W` or `e` is refused even when the letter is part of a pattern.
- A PowerShell script block (`Where-Object { … }`) is unproven.
- An unproven segment in a linked worktree costs one forge protection lookup, reused for up to 5 minutes ([ADR-0004](0004-protected-list-asked-live.md)).

## Consequences

In the main checkout or on a protected branch, an agent runs builds, tests, scripts and every unlisted program only after it moves into a linked worktree. Reads, forge and git inspection, the move and the sync run in place. A session is never held.
