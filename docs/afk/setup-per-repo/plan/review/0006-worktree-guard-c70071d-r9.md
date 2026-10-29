# Review round 9 — 0006-worktree-guard (c70071d)

- Verdict: **blocking** — crit=0 high=2 med=6 low=0
- Diff: delta c278c604..c70071de (the round 8 fix commit); the full slice 5b62663..c70071de given as context only. `plan/review/` left out of the reviewers' diff files.
- policy: lean · delta roster: delta-sweep, logic-correctness (owners of the round 8 high finding at line 73), test-veracity (the delta touches tests; owner of four round 8 high findings) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: no design-level finding at medium or above, so no verify pass.
- Mutation probe: hand-made Python mutants on the delta's changed lines; survivors behind r-001, r-002, r-003, r-006, r-008.
- Merged: r-001 = logic-correctness + test-veracity at line 375; r-005 = delta-sweep 110 + logic-correctness 110 (the slash spelling, folded into the same line); r-007 = delta-sweep + logic-correctness at line 348.
- Ledger keys: r-001..r-008 = 0006-worktree-guard/f092..f099.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | high | correctness | logic-correctness+test-veracity | hooks/lib/worktree_placement_rule.py:375 | New _in_chain makes `env -S` behind an unreadable word or an unlisted wrapper pass; c278c604 refused all of these. |
| r-002 | high | test | test-veracity | hooks/lib/worktree_placement_rule.py:377 | SURVIVED mutants: dropping `ASSIGN.match(text)` or `text in KEYWORDS` from _in_chain leaves every test green. |
| r-003 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:106 | SURVIVED mutants: removing `.lower()` or `UNQUOTE.sub` from the new `paths` line passes the whole file. |
| r-004 | medium | correctness | logic-correctness | hooks/lib/worktree_placement_rule.py:108 | A drive alias made with `New-PSDrive -PSProvider Environment` sets a rule variable with no `env:` text and no WRITERS word. |
| r-005 | medium | spec | delta-sweep+logic-correctness | hooks/lib/worktree_placement_rule.py:110 | Deleting `_env_ref` from `_sets` makes `$env:NAME=1` unseen unless the text names pwsh/powershell, so a PowerShell host reached under another name now sets the rule variable unrefused. Also (logic-correctness): the slash spelling `${env:/NAME} = '1'` still sets the variable and passes. |
| r-006 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:161 | SURVIVED mutant: dropping `and text != "--"` from the short-cluster branch passes the whole file. |
| r-007 | medium | correctness | delta-sweep+logic-correctness | hooks/lib/worktree_placement_rule.py:348 | `_in_chain` limits `env -S` scanning to wrappers in shell_mutations.WRAPPERS, so `env -S` behind `nice`, `timeout`, `setsid` or `stdbuf` is no longer refused. |
| r-008 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:380 | SURVIVED mutants: `after_option = False` (value branch) changed to True, and `after_option = text[:1] == "-"` changed to True, both pass the whole file. |

## Detail

### r-001 — New _in_chain makes `env -S` behind an unreadable word or an unlisted wrapper pass; c278c604 refused all of these.
- Why: Probe of refusal() on the c70071de module (agent worktree, listed repo) returned None for `FOO=$X env -S 'git worktree add ../../out'`, `sudo -u $U env -S '...'`, `sudo $U env -S '...'` and `nice -n 5 env -S '...'`, while the c278c604 module refused each; no test pins them and removing the `if word.opaque: return False` line (mutant chain_opaque) survived the whole file (481 passed, only the bench test failed).
- Fix: Treat an opaque or unknown word before `env` as 'cannot be worked out' (refuse), or add these four rows to the refused list; then keep only the pass rows that are provably plain words like `echo`.
- Evidence: `        if word.opaque:
            return False` and `        else:
            return False` in _in_chain; test rows only cover `sudo env -S`, `sudo -u root env -S`, `echo env -S`.

### r-002 — SURVIVED mutants: dropping `ASSIGN.match(text)` or `text in KEYWORDS` from _in_chain leaves every test green.
- Why: Whole-file run of each mutant passed 481 tests (only the bench test fails, as expected); mutated behaviour: `FOO=1 env -S 'git worktree add ../../out'`, `FOO=1 BAR=2 env -S ...`, `! env -S ...` and `if true; then env -S ...; fi` go from refused to None (probe of refusal()), so the refusal of an out-of-root worktree add (Acceptance: outside the root or cannot be worked out is refused) is unpinned for assignment and control-word prefixes.
- Fix: Add refused rows to test_a_target_that_cannot_be_worked_out_is_refused: `FOO=1 env -S 'git worktree add ../../out'`, `! env -S '...'`, `if true; then env -S '...'; fi`.
- Evidence: `if program_of(word) in shell_mutations.WRAPPERS or text in KEYWORDS or ASSIGN.match(text) or text[:1] == "-":`

### r-003 — SURVIVED mutants: removing `.lower()` or `UNQUOTE.sub` from the new `paths` line passes the whole file.
- Why: Probe: `PowerShell -c 'sc AFK_WORKTREE_FOLDER 1'` and `PWSH -c 'cd env:; ni AFK_ALLOW_PROTECTED -Value 1'` pass without `.lower()`, and `p'w'sh -c 'sc AFK_WORKTREE_FOLDER 1'` passes without `UNQUOTE.sub`; all are refused today, but every new Bash pwsh row is lowercase and unquoted-name.
- Fix: Add SETTING_FORMS rows `PowerShell -c 'sc {n} 1'`, `PWSH.EXE -c 'sc {n} 1'` and `p'w'sh -c 'sc {n} 1'`.
- Evidence: `paths = UNQUOTE.sub("", command.lower().replace("\\", "/"))  # `C:\...\pwsh.exe` keeps its folder marks`

### r-004 — A drive alias made with `New-PSDrive -PSProvider Environment` sets a rule variable with no `env:` text and no WRITERS word.
- Why: Confirmed in a pwsh child process (made-up name) that `New-PSDrive -Name e9 -PSProvider Environment -Root ''; $e9:ZZ_P9C = '1'` sets the variable; `variable_refusal("New-PSDrive -Name e9 -PSProvider Environment -Root '' | Out-Null; $e9:AFK_ALLOW_PROTECTED = '1'", True)` returns None because WRITERS lists `psvariable` but not `psdrive`.
- Fix: Add `psdrive` (and its aliases `ndr`, `mount` under PowerShell) to WRITERS/ALIASES so the command is refused beside a rule-variable name.
- Evidence: `writes = WRITERS.search(flat) or pwsh and ALIASES.search(flat)` with WRITERS = `set-item|set-content|add-content|new-item|copy-item|(?<!re)move-item|rename-item|invokeprovider|psvariable`

### r-005 — Deleting `_env_ref` from `_sets` makes `$env:NAME=1` unseen unless the text names pwsh/powershell, so a PowerShell host reached under another name now sets the rule variable unrefused. Also (logic-correctness): the slash spelling `${env:/NAME} = '1'` still sets the variable and passes.
- Why: The old word test refused `$env:NAME=1` under any program in any shell; probe on scratch copies (refusal() with the placement verdict stubbed): `$SHELLX -c '$env:AFK_ALLOW_PROTECTED=1'`, `"$SHELLX" -Command '...'`, `./ps.cmd '...'`, `ps -c '...'` and `pw -c '...'` were REFUSED at c278c604 and all pass at c70071de. D-78 limits itself to 'text PowerShell reads' and does not list this loss.
- Fix: Refuse the `$env:NAME` and `${env:NAME}` spellings in any shell (they hold no meaning in Bash) and gate only the bare `env:NAME` form on `pwsh`; add a row such as `$P -c '$env:NAME=1'` to the refused tests. Also: Allow path separators after the colon: `re.search(r"env:[\\/]*" + name.lower() + r"(?!\w)", UNQUOTE.sub('', command.lower()))`, searching text that still has `/`.
- Evidence: if pwsh and re.search(r"env:" + name.lower() + r"(?!\w)", flat):  # the env: drive, reads too (D-78) | Confirmed in a pwsh child process with a made-up name that `${env:/ZZ_P9A} = "1"` sets `$env:ZZ_P9A`; `variable_refusal("${env:/AFK_ALLOW_PROTECTED} = '1'", True)` returns None (the backslash form is caught only because UNQUOTE strips `\`), contradicting D-78's 'in any position / any spelling'.

### r-006 — SURVIVED mutant: dropping `and text != "--"` from the short-cluster branch passes the whole file.
- Why: With the mutant `env -- -S 'git worktree add ../../out'` and `env -i -- -S '...'` go from None to refused (probe); the added row `env -- 'worktree add x'` does not reach the `--` then `-S` case.
- Fix: Add pass rows `env -- -S 'worktree add x'` and `env -i -- -S 'git worktree add ../../out'` (after `--` the word is the program, not an option).
- Evidence: `elif text.startswith("-") and text != "--":  # a short cluster such as -iS or -uA, or `-` (`-i`)`

### r-007 — `_in_chain` limits `env -S` scanning to wrappers in shell_mutations.WRAPPERS, so `env -S` behind `nice`, `timeout`, `setsid` or `stdbuf` is no longer refused.
- Why: Probe on scratch copies: `nice -n 5 env -S 'git worktree add ../../out'`, `timeout 5 env -S ...`, `setsid env -S ...`, `stdbuf -o0 env -S ...` returned a refusal at c278c604 and pass at c70071de (sudo, nohup, command, exec, time, env, braces, subshell, redirections, pipes all still refused). The change was made to stop false positives (`echo env -S 'worktree add'`) and no decision records the lost coverage; the same wrappers already pass for a direct `timeout 5 git worktree add ../../out`, so this widens a known gap rather than opening a new one.
- Fix: Record the trade-off in the decision ledger, or keep the scan for any program word that is not a known reader (`echo`, `grep`…), or add the common exec wrappers (nice, timeout, setsid, stdbuf) to the chain test and tests.
- Evidence: for start in (i for i, w in enumerate(full) if not w.opaque and program_of(w) == "env" and _in_chain(full[:i])):

### r-008 — SURVIVED mutants: `after_option = False` (value branch) changed to True, and `after_option = text[:1] == "-"` changed to True, both pass the whole file.
- Why: Mutant chain_ao_stays turns `sudo -u root echo env -S 'worktree add'` from None to refused (probe), and chain_ao_true also survived (no distinguishing command probed; unverified which input differs); the option-value logic has no pass row beyond `echo env -S`.
- Fix: Add pass rows such as `sudo -u root echo env -S 'worktree add'` and `sudo echo env -S 'worktree add x'`, and a refused row `sudo -u root -g wheel env -S '...'`.
- Evidence: `after_option = False  # the value of an option such as `sudo -u root``
