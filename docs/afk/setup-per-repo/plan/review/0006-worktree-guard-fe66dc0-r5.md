# Review round 5 — 0006-worktree-guard (fe66dc0)

- Verdict: **blocking** — crit=0 high=1 med=5 low=3
- Diff: delta c034dd6e..fe66dc08 (the round 4 fix commit); the full slice 5b62663..fe66dc08 given as context only. `plan/review/` left out of the reviewers' diff files.
- policy: lean · delta roster: delta-sweep (also the owner of the round 4 high finding), test-veracity (the delta touches tests) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: no design-level finding at medium or above, so no verify pass.
- Mutation probe: 6 hand-made Python mutants on the delta's changed lines; 4 survived (r-002, r-004, r-007, r-009), 2 killed.
- Ledger keys: r-001..r-009 = 0006-worktree-guard/f056..f064.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | high | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:157 | An indirect .NET call is now ignored whenever the same command also has one direct SetEnvironmentVariable( call, so the variable rule is lifted. |
| r-002 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:104 | Mutant survives: PowerShell unknown-option flag is sticky only by `unknown or`; no test pins it. |
| r-003 | medium | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:125 | The comma split of an array operand misses the usual `a, b` form, so a rule variable listed after the first array element is not judged. |
| r-004 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:169 | Mutant survives: `in_env` reset when a later location command leaves `env:` is untested. |
| r-005 | medium | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:170 | The `env:` location tracker misses the colon-attached parameter form, so `Set-Location -Path:env:` does not make later bare names count as env items. |
| r-006 | medium | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:372 | `env -S` splitting now needs a readable `env` word, so an unreadable program that is `env` no longer has its split string read. |
| r-007 | low | test | test-veracity | hooks/lib/worktree_placement_rule.py:126 | Mutant survives: the `,` split inside the `under_env` test is untested (likely near-equivalent; inferred). |
| r-008 | low | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:155 | A search whose regex has `.` after the call name now counts as a call, so `rg 'SetEnvironmentVariable.*AFK_ALLOW_PROTECTED' hooks` is refused. |
| r-009 | low | test | test-veracity | hooks/lib/worktree_placement_rule.py:373 | Mutant survives: the case-sensitivity of the `env -S` split detection is untested (likely near-equivalent; inferred). |

## Detail

### r-001 — An indirect .NET call is now ignored whenever the same command also has one direct SetEnvironmentVariable( call, so the variable rule is lifted.
- Why: `not firsts` makes the `.Invoke`/reflection signal count only when no direct call exists. The previous `hidden` test ORed `SET_ENV_INDIRECT.search(flat)` with the direct-call test, so round 3 refused this and round 4 passes it. Probe: variable_refusal on `[Environment]::SetEnvironmentVariable('X','1'); [Environment].GetMethod('SetEnvironmentVariable').Invoke($null,@('AFK_ALLOW_PROTECTED','1'))` returns refuse at c034dd6e and None at fe66dc08. Same for `...('X','1'); [Environment]::SetEnvironmentVariable.Invoke('AFK_ALLOW_PROTECTED','1')` and for `$m=...GetMethod(...); ...SetEnvironmentVariable('X','1'); $m.Invoke(...)`.
- Fix: Refuse when the indirect form is present and the name is in the text, whatever the direct calls name: `(SET_ENV_INDIRECT.search(flat) or not firsts or any(...))`, and add one mixed direct-plus-indirect row to SETTING_FORMS.
- Evidence: if called and name.lower() in flat and (not firsts or any(name.lower() in first or not re.fullmatch(r"\w+", first) for first in firsts)):

### r-002 — Mutant survives: PowerShell unknown-option flag is sticky only by `unknown or`; no test pins it.
- Why: Changing it to `unknown = not any(...)` (a later known switch clears an earlier unknown option) leaves all 296 tests green, so `Set-Content -Bogus x Env:<NAME> 1 -Force` would be wrongly passed (written = positionals[:1] = `x`).
- Fix: Add a SETTING_FORMS case with an unknown option followed by a known switch, e.g. `Set-Content -Bogus x Env:{n} 1 -Force`.
- Evidence: line 104: `unknown = unknown or not any(n.startswith(name) for n in SWITCHES)` mutated to `unknown = not any(n.startswith(name) for n in SWITCHES)`; full file on scratch copy of fe66dc08: `296 passed`. Existing case `Set-Content -Bogus x Env:{n} 1` has only one option, so it cannot tell the two forms apart.

### r-003 — The comma split of an array operand misses the usual `a, b` form, so a rule variable listed after the first array element is not judged.
- Why: PowerShell parses `Env:OTHER, Env:NAME` as one array, but the shell parser gives separate words (`Env:OTHER,` and `Env:NAME`). `_item_sets` reads only `positionals[:1]` or `-Path`, so the later element is dropped. Probe: variable_refusal returns None for `Set-Content Env:OTHER, Env:AFK_ALLOW_PROTECTED 1`, `Set-Content -Path env:OTHER, env:AFK_ALLOW_PROTECTED 1`, `Add-Content Env:OTHER, Env:AFK_ALLOW_PROTECTED 1`, `Set-Item Env:OTHER, Env:AFK_ALLOW_PROTECTED 1`, `Set-Content 'Env:OTHER', 'Env:AFK_ALLOW_PROTECTED' 1` and `Set-Content @('Env:OTHER','Env:AFK_ALLOW_PROTECTED') 1`. The tested forms (`Env:NAME, Env:OTHER` and the no-space `a,b`) pass only because the rule name comes first or has no space.
- Fix: Treat a positional (or role value) that ends in a comma, or a positional that follows one, as part of the same array: join the words on commas before the `split(",")`, and add the flipped-order rows to SETTING_FORMS.
- Evidence: written = [part for a in written for part in a.split(",")]  # a PowerShell array names several items

### r-004 — Mutant survives: `in_env` reset when a later location command leaves `env:` is untested.
- Why: Changing it to `in_env = in_env or any(...)` (flag never clears) leaves all 296 tests green, so the over-refusal `Set-Location env:; Set-Location C:\; Set-Content <NAME> 1` has no pinning test.
- Fix: Add a reading/passes case where `Set-Location env:` is followed by a `Set-Location`/`cd` to a non-env path, then a write of a bare file named like the variable.
- Evidence: line 170: `in_env = any(w.text.lower().startswith("env:") for w in program[1:])` mutated to `in_env = in_env or any(...)`; full file on scratch copy: `296 passed`. Only added cases are `Set-Location env:; Set-Content {n} 1` and `cd env:; ni {n} -Value x`.

### r-005 — The `env:` location tracker misses the colon-attached parameter form, so `Set-Location -Path:env:` does not make later bare names count as env items.
- Why: `in_env` is true only when a word itself starts with `env:`; `-Path:env:` and `-LiteralPath:env:\` start with `-`. Probe: variable_refusal returns None for `Set-Location -Path:env:; Set-Content AFK_ALLOW_PROTECTED 1` and `Set-Location -LiteralPath:env:\; Set-Content AFK_ALLOW_PROTECTED 1`, while the space form `Set-Location -Path env:; ...` is refused. The same file already handles colon forms for `-Command:`.
- Fix: Take the part after the first `:` of a `-Xxx:value` word before testing `startswith("env:")`, and add a `-Path:env:` row to SETTING_FORMS.
- Evidence: in_env = any(w.text.lower().startswith("env:") for w in program[1:])  # later names live in env:

### r-006 — `env -S` splitting now needs a readable `env` word, so an unreadable program that is `env` no longer has its split string read.
- Why: `envish` looks only at readable words, but the opaque-program branch exists for the case where the program (`$ENV`, `${ENV}`, `$X`) cannot be read. Probe through `_targets`: `$ENV -S 'git worktree add /tmp/x'`, `${ENV} --split-string='git worktree add /tmp/x'`, `$X -S "git worktree add /tmp/x"` and `& $X -S 'git worktree add /tmp/x'` give target None (refused for a listed repository) at c034dd6e and no target at fe66dc08. The old lowercase `-s` test split for any unreadable program.
- Fix: Treat an opaque program[0] (or `effects.get("opaque")`) as possibly env: `envish = program[0].opaque or effects.get("opaque") or any(...)`; the `$X log -S 'worktree add'` row stays passing because only the quoted-argument form is split by that branch.
- Evidence: envish = any(program_of(w) == "env" for w in readable)

### r-007 — Mutant survives: the `,` split inside the `under_env` test is untested (likely near-equivalent; inferred).
- Why: Replacing `a.split(",")` with `[a]` in the `under_env` expression only is green (296 passed) because the split on line 125 already catches `env:OTHER,env:<NAME>`; it differs only for an input like `-Path <NAME>,env:`, whose intended result is unclear.
- Fix: Either drop the second split if it is not needed, or add a case where a later array element carries the `env:` prefix and the first does not.
- Evidence: line 126: `for part in a.split(","))` mutated to `for part in [a])`; full file on scratch copy: `296 passed`.

### r-008 — A search whose regex has `.` after the call name now counts as a call, so `rg 'SetEnvironmentVariable.*AFK_ALLOW_PROTECTED' hooks` is refused.
- Why: `SET_ENV_INDIRECT` matches `[.,)]` right after the name, and the new `called` no longer needs `[Environment]`; a regex wildcard is not a call. Probe: refuse at fe66dc08, pass at c034dd6e. D-74 settles prose with call punctuation such as `(` or `.Invoke`, not a bare `.*`; the cost is a reworded search, so low.
- Fix: Narrow the indirect pattern to `\.\s*invoke` or a closing `)` / `,` after the name, or record `.*` as accepted in D-74.
- Evidence: called = firsts or SET_ENV_INDIRECT.search(flat)  # `.Invoke(` or a reflection lookup names no argument

### r-009 — Mutant survives: the case-sensitivity of the `env -S` split detection is untested (likely near-equivalent; inferred).
- Why: Changing `text.startswith(("-S", "--split-string"))` to `text.lower().startswith(("-s", "--split-string"))` is green (296 passed); the only observable difference is a single quoted word starting with `-s` and holding spaces behind `env`.
- Fix: Add a case such as `env $X git log "-s worktree add"` expecting a pass, or accept the gap.
- Evidence: line 372: `splits = envish and (split or text.startswith(("-S", "--split-string")))`; full file on scratch copy: `296 passed`. Killed mutants for contrast: dropping `in_env or` at line 126 and dropping `plain[0].startswith("-")` at line 379 both fail existing tests.
