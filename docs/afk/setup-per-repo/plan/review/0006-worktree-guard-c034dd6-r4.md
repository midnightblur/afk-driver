# Review round 4 — 0006-worktree-guard (c034dd6)

- Verdict: **blocking** — crit=0 high=1 med=7 low=2
- Diff: delta 062db01c..c034dd6e (the round 3 fix commit); the full slice 5b62663..c034dd6e given as context only. `plan/review/` left out of the reviewers' diff files.
- policy: lean · delta roster: delta-sweep, test-veracity (the delta touches tests); no round 3 finding was critical or high, so no fix-owner specialist · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: no design-level finding at medium or above, so no verify pass.
- Mutation probe: 6 hand-made Python mutants on the delta's changed lines; 3 survived (r-003, r-005, r-006), 3 killed.
- Ledger keys: r-001..r-010 = 0006-worktree-guard/f046..f055.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | high | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:149 | New ENV_TYPE gate lets a computed variable name through when the .NET type name is built from parts; the old code refused it. |
| r-002 | medium | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:76 | The delta rebuilds the item-call model and adds tests for cpi, mi, ren and rni, but the PowerShell aliases cp, copy, mv and move still bypass it. |
| r-003 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:100 | Mutant survived: the unknown-option fallback (`unknown = True`) is never exercised by a test. |
| r-004 | medium | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:114 | One unknown switch makes `_item_sets` judge every positional of Set-Content and Add-Content, so a harmless read of a rule variable is now refused. |
| r-005 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:118 | Mutant survived: destination positional of Copy/Move/Rename-Item given together with -Path is untested. |
| r-006 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:140 | Mutant survived: `-Command:<text>` colon form of Invoke-Expression/iex is untested. |
| r-007 | medium | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:365 | The create-worktree check behind an unreadable program no longer matches a backslash path, so PowerShell's native `.\scripts\create-worktree` form passes. |
| r-008 | medium | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:367 | The new substitution-as-program branch only fires when `worktree` is the first token, so git options before it still pass. |
| r-009 | low | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:121 | `_item_sets` matches only a lone `env:`-prefixed word, so a comma list or a prior `Set-Location env:` still sets the variable unseen. |
| r-010 | low | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:361 | The `-s` split rule lowercases the word, so `-S` (git pickaxe) followed by a quoted phrase is split into tokens and refused. |

## Detail

### r-001 — New ENV_TYPE gate lets a computed variable name through when the .NET type name is built from parts; the old code refused it.
- Why: A refusal that 062db01c made now passes: with a non-word first argument, `hidden` is true only when the literal text `[environment]` or `system.environment` appears, and a concatenated type name never matches. Probe on a scratch copy of c034dd6e (PowerShell tool, real hook): `$n='AFK_ALLOW_PROTECTED'; ([type]('System.Env'+'ironment'))::SetEnvironmentVariable($n,'1')` passes; `$n=...; $t=[type]::GetType('System.'+'Environment'); $t::SetEnvironmentVariable($n,'1')` passes; `$n=...; $t='Environment'; [System.$t]::SetEnvironmentVariable($n,'1')` passes. All three are denied on 062db01c. The literal `[Environment]::SetEnvironmentVariable($n,'1')` is still denied.
- Fix: Drop ENV_TYPE as a precondition for a computed name: refuse when SetEnvironmentVariable is called with a non-word first argument and a rule name appears in the command, and keep ENV_TYPE only to exempt quoted prose (for example `git commit -m` text).
- Evidence: hidden = ENV_TYPE.search(flat) and (SET_ENV_INDIRECT.search(flat) or any(
        not re.fullmatch(r"\w+", first) for first in firsts))

### r-002 — The delta rebuilds the item-call model and adds tests for cpi, mi, ren and rni, but the PowerShell aliases cp, copy, mv and move still bypass it.
- Why: Probe (PowerShell tool): `cp env:PATH env:AFK_ALLOW_PROTECTED`, `copy env:PATH env:AFK_ALLOW_PROTECTED`, `mv env:FOO env:AFK_ALLOW_PROTECTED` and `move env:FOO env:AFK_ALLOW_PROTECTED` all pass; `cpi` and `mi` forms are denied. Present before the delta (same result on 062db01c), but the delta dispatch line is where the alias table is consumed and it adds the sibling-alias tests.
- Fix: Add cp, copy, mv and move to ITEM_SETTERS (and a test per alias).
- Evidence: if prog in PATH_SETTERS or prog in ITEM_SETTERS:
        return _item_sets(prog, args, drive, name)

### r-003 — Mutant survived: the unknown-option fallback (`unknown = True`) is never exercised by a test.
- Why: Setting `unknown = False` left all 251 tests green (full file confirmed), so no test proves that an unrecognised option makes the guard judge every positional rather than only the first.
- Fix: Add a row with an unrecognised option before the target, e.g. `Set-Content -Bogus x Env:{n} 1` and `Copy-Item -Bogus env:PATH env:{n}`.
- Evidence: if role is None and not any(n.startswith(name) for n in VALUED):
    unknown = True  (mutant: `unknown = False`; 251 passed)

### r-004 — One unknown switch makes `_item_sets` judge every positional of Set-Content and Add-Content, so a harmless read of a rule variable is now refused.
- Why: Probe: `Set-Content -NoNewline out.txt $env:AFK_WORKTREE_FOLDER`, `Add-Content -Force log.txt "$env:AFK_ALLOW_PROTECTED"`, and `Set-Content out.txt $env:AFK_WORKTREE_FOLDER -NoNewline` are all denied on c034dd6e; all pass on 062db01c. The same command without the switch passes, so the delta's own read tests (`Add-Content log.txt $env:{n}`) do not reach this path. Common switches (-Force, -NoNewline, -PassThru, -WhatIf, -Confirm, -Append, -Recurse) are all treated as unknown.
- Fix: Add a SWITCHES tuple of the known value-less parameters so only a truly unknown option falls back to judging every positional.
- Evidence: written = paths or (positionals if unknown else positionals[:1])

### r-005 — Mutant survived: destination positional of Copy/Move/Rename-Item given together with -Path is untested.
- Why: Replacing `positionals if paths` with `positionals[1:] if paths` left all 251 tests green (full file confirmed), so `Copy-Item -Path src env:NAME` (dest is the first positional) could be missed unnoticed.
- Fix: Add rows like `Copy-Item -Path env:PATH env:{n}` and `Move-Item -Path env:PATH env:{n}` to SETTING_FORMS.
- Evidence: rest = positionals if paths else positionals[1:]  (mutant: `positionals[1:] if paths else positionals[1:]`; 251 passed)

### r-006 — Mutant survived: `-Command:<text>` colon form of Invoke-Expression/iex is untested.
- Why: Changing `len(head[0]) + 1` to `+ 0` (keeps the colon in the script text) left all 251 tests green (full file confirmed), so the colon branch of the new `-Command` unwrap is unproven.
- Fix: Add SETTING_FORMS rows such as `Invoke-Expression -Command:'$env:{n}=1'` and `iex -c:'$env:{n}=1'`.
- Evidence: args = ([Word(args[0].text[len(head[0]) + 1:], False)] if head[1] else []) + args[1:]  (mutant: `+ 1:` -> `+ 0:`; 251 passed)

### r-007 — The create-worktree check behind an unreadable program no longer matches a backslash path, so PowerShell's native `.\scripts\create-worktree` form passes.
- Why: `plain` is built from `_bare(word)`, which deletes backslashes, so `.\scripts\create-worktree` becomes `.scriptscreate-worktree` and `program_of` never returns `create-worktree`; the old substring test caught it. Probe (PowerShell tool): `& $X .\scripts\create-worktree --parent ..\out --dir x` passes on c034dd6e and is denied on 062db01c; the same command with `scripts/create-worktree` is still denied.
- Fix: Test the unmodified lowered word text for the creator name (split on both `/` and `\`), not the backslash-stripped text.
- Evidence: if verb or any(program_of(Word(p, False)) == "create-worktree" for p in plain):

### r-008 — The new substitution-as-program branch only fires when `worktree` is the first token, so git options before it still pass.
- Why: A fix applied at one shape while a sibling shape keeps the old behaviour. Probe (Bash tool): `$(which git) worktree add ../../out` is denied, but `$(which git) -C . worktree add ../../out`, `$(which git) --no-pager worktree add ../../out` and `$(which git) -c core.x=1 worktree add ../../out` all pass. The `which git` backtick form and the quoted `"$(which git)"` form with `-C .` are denied.
- Fix: Fire when the first plain token is `worktree` or starts with `-` (a git option) and `verb` holds; keep `echo worktree add` passing.
- Evidence: elif verb and plain[0] == "worktree":  # a substitution's output as the program: `$(which git) worktree add`

### r-009 — `_item_sets` matches only a lone `env:`-prefixed word, so a comma list or a prior `Set-Location env:` still sets the variable unseen.
- Why: Probe (PowerShell tool): `Set-Content -Path env:OTHER,env:AFK_ALLOW_PROTECTED 1`, `Set-Location env:; Set-Content AFK_ALLOW_PROTECTED 1` and `cd env:; ni AFK_WORKTREE_FOLDER -Value x` all pass on c034dd6e (same on 062db01c). The delta rewrote this check and did not close them.
- Fix: Split each written operand on commas before matching, and treat a prior `Set-Location`/`cd`/`Push-Location` to `env:` as `under_env` for later segments.
- Evidence: return any(drive.match(a) or (under_env and a.upper() == name) for a in written)

### r-010 — The `-s` split rule lowercases the word, so `-S` (git pickaxe) followed by a quoted phrase is split into tokens and refused.
- Why: Probe (Bash tool): `$GIT log -S 'worktree add'` is denied on c034dd6e. `$GIT log --grep 'worktree add'` passes (the fix works for that flag). Harmless history search refused; the old regex refused it too, so this is the delta's new tokenizer not fully fixing the case it was added for.
- Fix: Split a word only after the exact, case-sensitive `env -S` / `--split-string` option, and only when the program word is `env`.
- Evidence: plain += text.split() if split or text.startswith(("-s", "--split-string")) else [text]  # `env -S` splits
