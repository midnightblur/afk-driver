# Review round 8 — 0006-worktree-guard (c278c60)

- Verdict: **blocking** — crit=0 high=5 med=8 low=3
- Diff: delta 8cfc8d8c..c278c604 (the round 7 fix commit); the full slice 5b62663..c278c604 given as context only. `plan/review/` left out of the reviewers' diff files.
- policy: lean · delta roster: delta-sweep, logic-correctness (owners of the round 7 high finding), test-veracity (the delta touches tests) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: no design-level finding at medium or above, so no verify pass.
- Mutation probe: hand-made Python mutants on the delta's changed lines; 11 survived the whole file (r-001, r-002, r-004, r-005, r-006, r-007, r-008, r-009, r-010, r-012, r-013).
- Merged: r-003 = delta-sweep + logic-correctness at line 73; r-007 = delta-sweep 47 + logic-correctness 117 + test-veracity 47; r-009 = delta-sweep 76 + test-veracity 76; test-veracity's second line-63 finding (the `(?!\w)` lookahead) anchored at 62 to keep it apart.
- Ledger keys: r-001..r-016 = 0006-worktree-guard/f076..f091.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | high | test | test-veracity | hooks/lib/worktree_placement_rule.py:50 | Assignment operators `-=`, `/=`, `%=` are untested: removing any one from ASSIGNS survives the whole guard test file. |
| r-002 | high | test | test-veracity | hooks/lib/worktree_placement_rule.py:63 | Case-insensitivity of the env reference is untested: dropping `re.I` survives. |
| r-003 | high | correctness | delta-sweep+logic-correctness | hooks/lib/worktree_placement_rule.py:73 | PowerShell assignment test matches a rule variable only at the start of a word, so `$b,$env:AFK_ALLOW_PROTECTED = 1,2` and `[string]$env:AFK_ALLOW_PROTECTED = 1` pass. |
| r-004 | high | test | test-veracity | hooks/lib/worktree_placement_rule.py:75 | Decrement and spaced increment forms are untested: pre-decrement, post-decrement and `$env:NAME ++` mutants all survive. |
| r-005 | high | test | test-veracity | hooks/lib/worktree_placement_rule.py:358 | The creator-call half of the new `env -S` string check is untested: removing `or any(... == "create-worktree" ...)` survives. |
| r-006 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:46 | The ALIASES word boundaries are unproven: removing the `\w` lookbehind or the `\w` or `-` lookahead survives. |
| r-007 | medium | correctness | delta-sweep+logic-correctness+test-veracity | hooks/lib/worktree_placement_rule.py:47 | Alias check now needs the text `pwsh`/`powershell`; a Bash call through a backslash path to the executable no longer matches, so an alias write the old rule refused now passes. |
| r-008 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:62 | No pass case for a longer variable name: dropping `(?!\w)` survives. |
| r-009 | medium | test | delta-sweep+test-veracity | hooks/lib/worktree_placement_rule.py:76 | No pass case for a read on the right of an assignment: widening the later-word scan from `words[i + 1:]` to all words survives. Also, any later word that starts with an assignment operator or is `--` turns a plain read into a write (delta-sweep). |
| r-010 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:167 | Abbreviated `env` long options that take a value are untested: replacing `n.startswith(name)` with `n == name` survives, and so does dropping the `len(text) > 2` guard. |
| r-011 | medium | correctness | test-veracity | hooks/lib/worktree_placement_rule.py:168 | `env - -S '<worktree add outside>'` is not refused: `_split_string` stops at a bare `-`. |
| r-012 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:361 | The `program[:2]` limit on unreadable-program starts is untested in both directions: widening it and narrowing it both survive. |
| r-013 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:378 | The pair test in `_verb` is unpinned: changing `and` to `or` survives. |
| r-014 | low | compliance | delta-sweep | docs/afk/setup-per-repo/plan/DECISIONS.md:546 | D-77 'Supersedes' quotes a D-76 clause that D-76 does not contain. |
| r-015 | low | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:355 | The new `env -S` scan treats the word `env` anywhere in a segment as the env program, so an argument named `env` followed by -S and a worktree string is refused. |
| r-016 | low | correctness | logic-correctness | hooks/lib/worktree_placement_rule.py:357 | `env -S` as the last word raises IndexError in `_targets`, so any command that also mentions a worktree is refused as 'could not read this command'. |

## Detail

### r-001 — Assignment operators `-=`, `/=`, `%=` are untested: removing any one from ASSIGNS survives the whole guard test file.
- Why: Acceptance bullet 33 refuses every form that sets AFK_WORKTREE_FOLDER or AFK_ALLOW_PROTECTED, yet SETTING_FORMS covers only `=`, `+=`, `*=` and `??=`.
- Fix: Add SETTING_FORMS rows `$env:{n} -= 1`, `$env:{n} /= 1`, `$env:{n} %= 1`.
- Evidence: Hand mutation on scratch copy of c278c604, each of 3 mutants run on the whole file with a Windows pytest run: ASSIGNS minus "-=", minus "/=", minus "%=" each give `410 passed, 1 deselected`, as does the unmutated BASE run. Unmutated code refuses `$env:AFK_ALLOW_PROTECTED -= 1`, the mutant passes it.

### r-002 — Case-insensitivity of the env reference is untested: dropping `re.I` survives.
- Why: PowerShell env names ignore case, so `$Env:AFK_ALLOW_PROTECTED = '1'` sets the variable, and acceptance bullet 33 requires that form to be refused; every test row spells `$env:` in lower case.
- Fix: Add a SETTING_FORMS row `$Env:{n} = '1'` (and `${{ENV:{n}}} = '1'`).
- Evidence: Mutant `re.I | re.S` -> `re.S` in _env_ref: whole file `410 passed, 1 deselected`. Unmutated code refuses `$Env:AFK_ALLOW_PROTECTED = '1'`; the mutant returns no refusal for it (in-process variable_refusal probe).

### r-003 — PowerShell assignment test matches a rule variable only at the start of a word, so `$b,$env:AFK_ALLOW_PROTECTED = 1,2` and `[string]$env:AFK_ALLOW_PROTECTED = 1` pass.
- Why: `_env_ref` anchors with `^` and the parser does not split words on `,` or after a `[type]` cast, so the new `$env:NAME, $b = 1, 2` coverage misses the mirror spelling where the name is not word-initial.
- Fix: Search each word for the reference anywhere, then apply the same assignment-follows test.
- Evidence: Probe on c278c604 (variable_refusal, powershell=True): `$b, $env:AFK_ALLOW_PROTECTED = 1, 2` REFUSED but `$b,$env:AFK_ALLOW_PROTECTED = 1,2`, `$b,$env:AFK_ALLOW_PROTECTED=1,2`, `($b,$env:AFK_ALLOW_PROTECTED) = 1,2`, `$null,${env:AFK_ALLOW_PROTECTED} = 1,2`, `[int]$env:AFK_ALLOW_PROTECTED=1` all pass. unverified: PowerShell semantics not run by the reviewer.

### r-004 — Decrement and spaced increment forms are untested: pre-decrement, post-decrement and `$env:NAME ++` mutants all survive.
- Why: The changed condition names `--` and a later `++`/`--` word, but only `$env:{n}++` and `++$env:{n}` have rows, so each `--` and spaced-operator branch can be deleted unseen.
- Fix: Add SETTING_FORMS rows `--$env:{n}`, `$env:{n}--`, `$env:{n} ++`, `$env:{n} --`.
- Evidence: Whole-file runs, each `410 passed, 1 deselected`: (a) `(?:\+\+|--)?` -> `(?:\+\+)?` at line 63 (E-prefix-mm), (b) `rest.startswith(ASSIGNS + ("++", "--"))` -> `ASSIGNS + ("++",)` (S-rest-mm), (c) dropping `w.text in ("++", "--")` from the later-word test (S-later-incr). Unmutated code refuses `--$env:AFK_ALLOW_PROTECTED`, `$env:AFK_ALLOW_PROTECTED--`, `$env:AFK_ALLOW_PROTECTED ++`; each mutant passes its form.

### r-005 — The creator-call half of the new `env -S` string check is untested: removing `or any(... == "create-worktree" ...)` survives.
- Why: Acceptance bullet 32 refuses a creator call outside the root; `env -S './scripts/create-worktree --parent .. --dir x'` is refused only by this clause and no test runs it.
- Fix: Add an `env -S` creator row (with `--parent` outside the root) to test_a_target_that_cannot_be_worked_out_is_refused.
- Evidence: Mutant `if _verb(split) or any(program_of(Word(t, False)) == "create-worktree" for t in split):` -> `if _verb(split):`: whole file `410 passed, 1 deselected`. Unmutated code flags `env -S 'create-worktree --parent out --dir x'` as an unworkable target; the mutant does not.

### r-006 — The ALIASES word boundaries are unproven: removing the `\w` lookbehind or the `\w` or `-` lookahead survives.
- Why: The only pass rows beside an alias are Bash `cp`, `mv`, `sc` with the whole alias as a word; no PowerShell row holds alias letters inside a longer word or option.
- Fix: Add passing PowerShell rows such as `Write-Output $env:{n} xcp`, `... cpx`, `... cp-x`, `... $cp`.
- Evidence: Whole-file `410 passed, 1 deselected` for A-lb-word (`(?<![\w$:.-])` -> `(?<![$:.-])`), A-lb-dollar (drop `$`), A-la-word (drop `\w` in the lookahead), A-la-dash (drop `-` in the lookahead). Unmutated code passes `Write-Output $env:AFK_ALLOW_PROTECTED xcp`; each mutant refuses its form. Lookbehind `:`/`.`/`-` and lookahead `:`/`.` mutants also survived the in-process run over the guard test file's command lists; those five were not repeated on the whole file (unverified at full-file level).

### r-007 — Alias check now needs the text `pwsh`/`powershell`; a Bash call through a backslash path to the executable no longer matches, so an alias write the old rule refused now passes.
- Why: The bare `pwsh` test runs on text where UNQUOTE removed the backslashes, so `C:\Users\x\PowerShell\7\pwsh.exe` becomes `...powershell7pwsh.exe` and the `(?<![\w-])` lookbehind fails; the nested call is re-checked with powershell=False and the inner text has no `pwsh`, so nothing catches it.
- Fix: Run PWSH on the command with only quotes removed (keep backslashes, or turn them into `/`), allow `-preview`, or treat a nested `pwsh -c`/`powershell -Command` program as proof that PowerShell reads the text. Also pin the name test: Add a passing row `cp a b; grep -n {n} pwsh-notes.md` and a refused row naming `powershell` beside `cp env:..{n}`.
- Evidence: Probed on c278c604 with Bash tool: `'C:\Users\x\PowerShell\7\pwsh.exe' -c 'sc env:AFK_ALLOW_PROTECTED 1'` passes; on 8cfc8d8c REFUSED; `"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -Command "ni env:AFK_ALLOW_PROTECTED -Value 1"` also passes now. PWSH = re.compile(r"(?<![\w-])(?:pwsh|powershell)(?![\w-])")

### r-008 — No pass case for a longer variable name: dropping `(?!\w)` survives.
- Why: `$env:AFK_ALLOW_PROTECTED_OLD = '1'` sets a different variable and must pass; without the lookahead the rule over-refuses it, and no test pins that.
- Fix: Add a passing row `$env:{n}_OLD = '1'` to test_reading_or_removing_a_rule_variable_passes.
- Evidence: Mutant `)(?!\w)(.*)$` -> `)(.*)$`: whole file `410 passed, 1 deselected`. Unmutated code passes `$env:AFK_ALLOW_PROTECTED_OLD = '1'`; the mutant refuses it.

### r-009 — No pass case for a read on the right of an assignment: widening the later-word scan from `words[i + 1:]` to all words survives. Also, any later word that starts with an assignment operator or is `--` turns a plain read into a write (delta-sweep).
- Why: `$x = $env:AFK_ALLOW_PROTECTED` only reads the variable and must pass; with the wider scan the earlier `=` word makes it a refusal, and the pass list has no assignment-target row.
- Fix: Add a passing row `$x = $env:{n}` (PowerShell).
- Evidence: Mutant `for w in words[i + 1:])` -> `for w in words)`: whole file `410 passed, 1 deselected`. Unmutated code passes `$x = $env:AFK_ALLOW_PROTECTED`; the mutant refuses it.

### r-010 — Abbreviated `env` long options that take a value are untested: replacing `n.startswith(name)` with `n == name` survives, and so does dropping the `len(text) > 2` guard.
- Why: The delta adds unique-prefix handling (`--ch d -S ...`); tests use only full names, so the prefix branch and the bare `--` branch can regress unseen.
- Fix: Add rows `env --ch d -S '<worktree add outside>'`, `env --un A -S '...'`, and a passing `env -- '<quoted text>'` row.
- Evidence: Whole-file `410 passed, 1 deselected` for SS-long-adv-any (`any(n.startswith(name) ...)` -> `any(n == name ...)`) and SS-long-len (`and len(text) > 2` removed). Unmutated code refuses `env --ch d -S 'git worktree add x/out'`; the first mutant does not.

### r-011 — `env - -S '<worktree add outside>'` is not refused: `_split_string` stops at a bare `-`.
- Why: GNU env reads a lone `-` as `-i`, so the string split still runs git outside the root, while the new cluster tests never use a bare `-`.
- Fix: Treat a lone `-` like `-i` (advance one word) in `_split_string` and add the row to the unreadable-target test.
- Evidence: Real guard run (Windows, scratch copy of c278c604, listed repository, agent worktree): `env - -S 'git worktree add ../../out'` -> deny reason None, while `env -i -S '...'` is refused. Mutant `len(text) > 1` removed (the lone `-` then advances) refuses it, and the whole file still gives `410 passed, 1 deselected`.

### r-012 — The `program[:2]` limit on unreadable-program starts is untested in both directions: widening it and narrowing it both survive.
- Why: No row has an unreadable word at index 1 before `-S`, and none has a later unreadable word that must not start a split.
- Fix: Add a refused row `$X $Y -S '<worktree add outside>'` and a passing row `$GIT log "$X" -S 'worktree add'`.
- Evidence: Whole file `410 passed, 1 deselected` for T-starts (`enumerate(program[:2])` -> `enumerate(program)`) and T-starts2 (`program[:2]` -> `program[:1]`). Unmutated code passes `$GIT log "$X" -S 'worktree add'` and refuses `$X $Y -S 'git worktree add x/out'`; the first mutant refuses the former, the second passes the latter.

### r-013 — The pair test in `_verb` is unpinned: changing `and` to `or` survives.
- Why: No pass row has an unreadable program followed by `worktree list` or another `add` word, so a loosened pair test over-refuses unseen.
- Fix: Add passing rows `$GIT worktree list` and `$GIT remote add origin worktree`.
- Evidence: Mutant `a == "worktree" and b in ("add", "move")` -> `a == "worktree" or b in ("add", "move")`: whole file `410 passed, 1 deselected`. Unmutated code passes `$GIT worktree list`; the mutant refuses it.

### r-014 — D-77 'Supersedes' quotes a D-76 clause that D-76 does not contain.
- Why: The plugin DECISIONS.md protocol says Supersedes holds a quoted passage that it overrides exactly; D-76 says 'refuse a command whose segment runs an item writer (or its alias)', and the phrase "as a segment's program" occurs nowhere in the file.
- Fix: Quote D-76's real wording, e.g. 'whose segment runs an item writer (or its alias)'.
- Evidence: - Supersedes: D-76 (its "as a segment's program" clause)

### r-015 — The new `env -S` scan treats the word `env` anywhere in a segment as the env program, so an argument named `env` followed by -S and a worktree string is refused.
- Why: Probed on c278c604: `echo env -S 'worktree add'` and `grep env -S 'worktree add x'` now return target None (refused as unreadable); on 8cfc8d8c both returned [].
- Fix: Start the scan only from `env` words that sit in the program/prefix chain, not from arguments.
- Evidence: for start in (i for i, w in enumerate(full) if not w.opaque and program_of(w) == "env"):

### r-016 — `env -S` as the last word raises IndexError in `_targets`, so any command that also mentions a worktree is refused as 'could not read this command'.
- Why: `_split_string` returns `{j + 1}` for a trailing `-S`, and the new loop indexes `full[j]` without a bound check.
- Fix: Skip indexes `>= len(full)` before `_bare(full[j])`.
- Evidence: Probe: `_targets` on `env -S` and on `ls worktree; env -S` raises `IndexError('list index out of range')`; refusal() turns it into 'the guard could not read this command'.
