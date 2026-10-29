# Review round 10 — 0006-worktree-guard (7abc8bc)

- Verdict: **blocking** — crit=0 high=1 med=3 low=1
- Diff: delta c70071de..7abc8bc1 (the round 9 fix commit); the full slice 5b62663..7abc8bc1 given as context only. `plan/review/` left out of the reviewers' diff files.
- policy: lean · delta roster: delta-sweep, logic-correctness and test-veracity (owners of the round 9 high findings; the delta touches tests) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: no design-level finding at medium or above, so no verify pass.
- Mutation probe: hand-made Python mutants on the delta's changed lines; survivors behind r-003, r-004, r-005.
- Merged: r-001 = delta-sweep + logic-correctness at line 376.
- Ledger keys: r-001..r-005 = 0006-worktree-guard/f100..f104.
- Round 10 is the settle loop's cap: stalemate, no remediation this run (`SETTLEMENT.md` "Termination").

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | high | correctness | delta-sweep+logic-correctness | hooks/lib/worktree_placement_rule.py:376 | New _in_chain skips env -S whenever any reader name appears in the words before env, even as an option value, so a worktree command that was caught before now passes. |
| r-002 | medium | correctness | logic-correctness | hooks/lib/worktree_placement_rule.py:46 | Possible gap: PowerShell `Start-Process ... -Environment @{AFK_ALLOW_PROTECTED='1'}` sets a rule variable and the variable rule does not see it; the worktree rule also does not see `Start-Process git -ArgumentList 'worktree add ...'`. |
| r-003 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:48 | The `mount` alias added to ALIASES is untested: removing it leaves every test green. |
| r-004 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:51 | Five READERS entries (egrep, fgrep, rg, cat, ls) are unpinned: dropping any one leaves every test green. |
| r-005 | low | test | test-veracity | hooks/lib/worktree_placement_rule.py:50 | The `[\w.]*` prefix in DRIVE is not exercised by the provider-qualified test row. |

## Detail

### r-001 — New _in_chain skips env -S whenever any reader name appears in the words before env, even as an option value, so a worktree command that was caught before now passes.
- Why: The rewrite treats any earlier word whose program_of is in READERS as the program that runs. It does not check that the word is a program at all. An option value such as `-u ls`, `-C ls` or `-g grep` is therefore read as a reader, and the old allow-list consumed those values. Probed on scratch copies of 7abc8bc1 and c70071de: `env -u ls env -S 'git worktree add ../../out'`, `env -C ls env -S ...`, `sudo -u cat env -S ...` and `sudo -g grep env -S ...` all return no target at 7abc8bc1 and a target at c70071de.
- Fix: Exclude a reader only when it is the program of the command (first non-wrapper, non-option, non-assignment word), or skip option values as the old loop did; add rows for `env -u ls`, `env -C ls`, `sudo -u cat` to the refused list.
- Evidence: def _in_chain(before): """No readable word in `before` names a program that only prints or searches its operands (D-79).""" return not any(not w.opaque and program_of(w) in READERS for w in before)

### r-002 — Possible gap: PowerShell `Start-Process ... -Environment @{AFK_ALLOW_PROTECTED='1'}` sets a rule variable and the variable rule does not see it; the worktree rule also does not see `Start-Process git -ArgumentList 'worktree add ...'`.
- Why: `Start-Process` has an `-Environment` parameter (listed by pwsh 7.6.6 `(Get-Command Start-Process).Parameters.Keys`). It is the PowerShell form of the refused inline assignment `NAME=1 cmd`, but WRITERS, DRIVE and _sets match none of it. Probe: `variable_refusal("Start-Process x -Environment @{AFK_ALLOW_PROTECTED='1'}", True)` returns None. Separately, `_targets` returns no target for `Start-Process git -ArgumentList 'worktree','add','../../out'` and for `saps ...`. The module docstring's known frontier lists neither. Hook-level end-to-end behaviour was not run (unverified); the module-level probe is the evidence.
- Fix: Treat `start-process`/`saps` (and `ProcessStartInfo` environment writes) as a writer when a rule variable is named, and give `_targets` the `-ArgumentList` words of `Start-Process` as a program, or record the gap in the module docstring's frontier.
- Evidence: WRITERS = re.compile(r"set-item|set-content|add-content|new-item|copy-item|(?<!re)move-item|rename-item|invokeprovider|" r"psvariable|psdrive")  -- no start-process entry; module docstring frontier names only git aliases, script files, xargs/find -exec

### r-003 — The `mount` alias added to ALIASES is untested: removing it leaves every test green.
- Why: D-79 adds `mount` (PowerShell's New-PSDrive alias) as a writer, but the only test naming it is the Bash negative `mount | grep {n}`, which passes with or without the alias because ALIASES applies only when PowerShell reads the text.
- Fix: Add a PowerShell SETTING_FORMS row such as `mount e9 Environment ''; $e9:{n} = '1'`, so a PowerShell host that spells the alias `mount` is proven refused.
- Evidence: ALIASES = re.compile(r"...|rni|ren|ndr|mount)..."). Manual mutation on a scratch copy of 7abc8bc1: removing `|mount` gave 384 passed, 0 failed over every rule-variable test (-k 'rule_variable or item_writer or env_drive'). Removing `ndr` fails the `ndr e9 Environment ''` row, and removing `psdrive` fails the `New-PSDrive` row.

### r-004 — Five READERS entries (egrep, fgrep, rg, cat, ls) are unpinned: dropping any one leaves every test green.
- Why: The only passing cases for `env -S` behind a print/search program use echo, printf and grep; the other 5 names can be deleted (so `rg env -S 'git worktree add x'` would be refused) with 0 test failures.
- Fix: Parametrize test_a_quoted_worktree_phrase_behind_an_unreadable_program_passes over every READERS entry, e.g. "egrep env -S 'worktree add x'", "fgrep ...", "rg ...", "cat ...", "ls ...".
- Evidence: READERS = ("echo", "printf", "grep", "egrep", "fgrep", "rg", "cat", "ls"). Manual mutation on a scratch copy of 7abc8bc1: deleting each of egrep, fgrep, rg, cat, ls in turn, 83 passed, 0 failed, run over every test that runs `env -S` (-k 'cannot_be_worked or quoted_worktree_phrase or unreadable'; grep found no other test with `env -S`). Deleting echo, printf or grep each fails a test.

### r-005 — The `[\w.]*` prefix in DRIVE is not exercised by the provider-qualified test row.
- Why: The row `${Microsoft.PowerShell.Core\Environment::{n}}` is caught by the PowerShell branch's unanchored re.search on the bare `environment::NAME` suffix, because the unconverted backslash stops `[\w.]*` from matching; replacing the prefix with `environment::` leaves all tests green, so the row does not prove a qualified spelling is handled (this is likely an equivalent mutant for realistic input; inferred, not proved).
- Fix: Drop the dead `[\w.]*` prefix, or add a Bash row whose provider qualifier the prefix can match, e.g. `${Microsoft.PowerShell.Core.Environment::{n}}`.
- Evidence: DRIVE = r"(?:env:|[\w.]*environment::)[/.]*". Mutation `[\w.]*environment::` to `environment::`: 332 passed, 0 failed (-k 'setting_a_rule_variable_is_refused or env_drive_spelling or item_writer').
