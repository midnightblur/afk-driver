midnightblur/afk-driver@2e934894cd49ae1aa0a9d3ecf37de2ae2d2e20e3 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-007-guard-setup-walk/COVERAGE.json

## Answer

Session in repository X's linked worktree; Y is another repository's main checkout. The guard judges each literal target path, not the program.

| Step | Decision | Deciding site |
|---|---|---|
| `cd <Y> && afk-python .../developer_values.py set ...` | allow | `hooks/lib/protected_branch_guard.py:599-601` |
| `bash .../hooks/install-git-hooks.sh` (in Y) | allow | same |
| `afk-python .../background_git_hooks.py` (in Y) | allow | same |
| shell write to `<Y>/.git/afk/config.yaml` | refuse: "this is the main checkout" | `protected_branch_guard.py:289-290` |
| write to `~/.afk/` | allow (no `.git` above home) | `protected_branch_guard.py:219-220`, `:286-287` |
| Write/Edit `file_path` under `<Y>/.git/` | refuse: "this is the main checkout" | `protected_branch_guard.py:374-383`, `:209-227`, `:162-167` |

- `cd` only moves the folder (`hooks/lib/shell_mutations.py:548-556`); `writer_targets` returns no target for `afk-python` or `bash` (`shell_mutations.py:486-512`). No target → allow. Same with cwd=Y (lab case g).
- Only the direct write into `<Y>/.git` is a mutation of a guarded resource, and it is classed as Y's main checkout. No separate git-common-directory rule exists. A common directory outside every work tree (`--separate-git-dir`, bare) is not guarded.
- The scripts write where the guard cannot see: `developer_values.py:191` → `<Y common dir>/afk/config.yaml`; `install-git-hooks.sh:53-55,88-97` → Y's common hooks folder.
- Change meter: `change_meter.py:130` compares `git status` output, which lists nothing under `.git`, so no quarantine. A script change to a `git status`-listed file in Y quarantines later calls with cwd=Y only (`protected_branch_guard.py:579-591`).
- Git backstop: the 3 scripts run only `git rev-parse` / `git config --get`; after `install-git-hooks.sh`, later agent commits and ref moves in Y are refused by `hooks/git-backstop.py:33-36,87-90`.
- Starting fact refuted: commit b3a2bb6 changed `hooks/plugin-source-gates.sh`, not the PreToolUse guard (`git show --stat b3a2bb6`).
- Lab: 77 envelopes, Bash and PowerShell agree; guard tests 431 passed.

## Sites

`hooks/protected-branch-guard.py:41`; `hooks/lib/protected_branch_guard.py:162-167,209-227,286-290,374-383,428,567,579-601,654,689-690,696,722,728,736-753`; `hooks/lib/shell_mutations.py:205,486-512,538-564`; `hooks/lib/change_meter.py:65,130,221`; `hooks/lib/occupancy.py:99,128`; `hooks/git-backstop.py:33-36,87-90`; `hooks/hooks.json:73`; `hooks/hooks.codex.json`; `scripts/afk-launch.py:31`.

## Frontier

- B14: which cwd each harness reports after a `cd` in an earlier call; real repository layouts (separate-git-dir, bare, `core.hooksPath`, a `.git` above home); live forge answers.

## Unverified

- `c-0b6eb05d` (not load-bearing): seed completeness claim over searched name forms.
- Gap: no test covers a Write/Edit or redirect target under a `.git` directory, or an unmetered opaque-script write inside `.git` (`unguarded`).
- Docs possibly stale (inferred): `docs/afk/protected-branch-guard/adr/requirements/0005-guard-against-forgetting-not-intent.md:7` vs `0010-refuse-mutations-not-syntax.md:15`; `CAPABILITIES.md:22`.
