# Review round 7 — 0006-worktree-guard (8cfc8d8)

- Verdict: **blocking** — crit=0 high=1 med=5 low=0
- Diff: delta 8b8cad05..8cfc8d8c (the round 6 fix commit); the full slice 5b62663..8cfc8d8c given as context only. `plan/review/` left out of the reviewers' diff files.
- policy: lean · delta roster: delta-sweep (also the owner of the round 6 high finding), test-veracity (the delta touches tests), logic-correctness (the delta passes ~150 changed lines; the slice meets the lean trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: no design-level finding at medium or above, so no verify pass.
- Mutation probe: hand-made Python mutants on the delta's changed lines; 4 survived the whole file (r-002, r-003, r-004, r-005).
- Merged: r-001 = delta-sweep + logic-correctness at line 118; r-004 = delta-sweep line 120 + test-veracity (reported at 118, anchored at 120); r-006 = delta-sweep 157 + logic-correctness 155 + test-veracity 157.
- Ledger keys: r-001..r-006 = 0006-worktree-guard/f070..f075.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | high | correctness | delta-sweep+logic-correctness | hooks/lib/worktree_placement_rule.py:118 | Item-writer test reads only program[0], so `$null = New-Item env:AFK_ALLOW_PROTECTED -Value 1` is not refused |
| r-002 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:44 | Mutation survivor: the `si` alias (Set-Item) in `ITEM_WRITERS` has no test row; every other alias has one. |
| r-003 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:46 | Mutation survivor: `ENV_VALUED` entries `--unset`, `-C` and `--chdir` are never exercised before an env split-string; only `-u` is. |
| r-004 | medium | correctness | delta-sweep+test-veracity | hooks/lib/worktree_placement_rule.py:120 | Bash `cp`/`mv`/`sc`/`ac` plus a rule-variable name anywhere in the command is now refused, though only PowerShell can write `env:` |
| r-005 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:153 | Mutation survivor: the separate-word spelling `--split-string 'cmd'` and the attached short spelling `-S'cmd'` of `env` split-string have no test row. |
| r-006 | medium | correctness | delta-sweep+logic-correctness+test-veracity | hooks/lib/worktree_placement_rule.py:157 | `_split_string` still misses `env -S` behind a value-taking or combined option: `env -a x -S`, `env -P /bin -S`, `env -iS '...'`, `env -vS '...'` |

## Detail

### r-001 — Item-writer test reads only program[0], so `$null = New-Item env:AFK_ALLOW_PROTECTED -Value 1` is not refused
- Why: D-76 says no positional rule is complete and refuses writer plus name, yet a writer behind a PowerShell assignment (`$x = Set-Item env:NAME 1`, `$null = New-Item env:NAME -Value 1`) is not program[0], so `writer` stays False and the command passes (probe on a 8cfc8d8c copy: variable_refusal False in both shell modes; the 8b8cad05 copy gives the same).
- Fix: Set `writer` when any non-opaque word of the segment (not only program[0]) has program_of in ITEM_WRITERS, so an assignment prefix cannot hide it.
- Evidence: writer = bool(program) and not program[0].opaque and program_of(program[0]) in ITEM_WRITERS  /  if _sets(words, program, name) or writer and name.lower() in flat

### r-002 — Mutation survivor: the `si` alias (Set-Item) in `ITEM_WRITERS` has no test row; every other alias has one.
- Why: Removing `"si"` leaves the whole guard test file green, so `si env:AFK_ALLOW_PROTECTED 1` could be allowed by a later edit unseen.
- Fix: Add `("PowerShell", "si env:{n} 1")` to SETTING_FORMS beside the `sc`/`ac`/`ni` rows.
- Evidence: Mutant `"set-item", "si", ` -> `"set-item", ` SURVIVED the whole file. The other 11 aliases were each KILLED by an existing row; grep for `"si ` in scripts/tests finds no use.

### r-003 — Mutation survivor: `ENV_VALUED` entries `--unset`, `-C` and `--chdir` are never exercised before an env split-string; only `-u` is.
- Why: Removing those three entries (mutant ijk, and each alone) leaves every test green, so skipping the value word of those options is unpinned.
- Fix: Add rows such as `$ENV -C d -S 'git worktree add ../../out'`, `$ENV --unset A -S '...'` and `$ENV --chdir=d -S '...'` next to the new `-u A` rows.
- Evidence: Mutant `ENV_VALUED = ("-u", "--unset", "-C", "--chdir")` -> `("-u",)` SURVIVED on the whole guard file (338 passed, only the scratch-incompatible bench test failed). Single-entry mutants for `--unset`, `-C`, `--chdir` each SURVIVED the 303-test subset; dropping `-u` was killed by the new row `$ENV -u A -S ...`.

### r-004 — Bash `cp`/`mv`/`sc`/`ac` plus a rule-variable name anywhere in the command is now refused, though only PowerShell can write `env:`
- Why: ITEM_WRITERS holds PowerShell aliases that are also Bash or Windows commands and the check ignores the shell mode, so under powershell=False `cp a b; grep -n AFK_WORKTREE_FOLDER README.md`, `mv notes/AFK_ALLOW_PROTECTED.md notes/old.md` and `sc query AFK_ALLOW_PROTECTED` are refused (probe: new True, 8b8cad05 False); a plugin whose docs name these variables hits it in ordinary file moves and greps, and D-76 and the new tests cover PowerShell only.
- Fix: Count the Bash-spelled aliases (cp, mv, copy, move, sc, si, ac, ni, mi, ren) as writers only when the command is read as PowerShell, and pass powershell=True when recursing into `pwsh -Command` bodies.
- Evidence: if _sets(words, program, name) or writer and name.lower() in flat:  # an item writer beside the name

### r-005 — Mutation survivor: the separate-word spelling `--split-string 'cmd'` and the attached short spelling `-S'cmd'` of `env` split-string have no test row.
- Why: Dropping `"--split-string"` from line 153 (mutant c) or the `"-S"` prefix from line 155 (mutant f) leaves the whole guard test file green, so a regression in those two env spellings would ship unseen.
- Fix: Add rows `$ENV --split-string 'git worktree add ../../out'` and `$ENV -S'git worktree add ../../out'` to the list of commands the guard cannot work out (test_a_target_that_cannot_be_worked_out_is_refused).
- Evidence: Hand mutation on a scratch copy of 8cfc8d8c: `if text in ("-S", "--split-string"):` -> `if text in ("-S",):` and `startswith(("-S", "--split-string="))` -> `startswith(("--split-string=",))`; both SURVIVED on a 303-test subset and on the whole file apart from the bench test. Existing rows cover only `-S 'cmd'` and the attached `--split-string='cmd'`.

### r-006 — `_split_string` still misses `env -S` behind a value-taking or combined option: `env -a x -S`, `env -P /bin -S`, `env -iS '...'`, `env -vS '...'`
- Why: The rewrite fixed `-u A -S` and `$ENV -u A -S` but ENV_VALUED lists only -u/--unset/-C/--chdir, so `-a x` is skipped one word, the string word then ends the loop, and `git worktree add ../../out` stays one unsplit word: `_targets` returns [] (probe: `env -a x -S 'git worktree add ../../out'`, `env -iS ...`, `env -vS ...`, `env --split ...` all give [], i.e. allowed); the module docstring does not list these as frontier.
- Fix: Add `-a`/`--argv0` to ENV_VALUED, treat any short-option cluster ending in S and any `--split*` prefix as -S, and return an unknown target for an unrecognised option instead of ending the scan.
- Evidence: j += 2 if text in ENV_VALUED else 1 if text.startswith("-") or ASSIGN.match(text) else len(program)
