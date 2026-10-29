# Review — 0006-worktree-guard, round 2

- Verdict: **blocking** — crit=0 high=1 med=8 low=3
- Diff: delta 7d970119..b00e47df (the round 1 fix commit); the full slice 5b62663..b00e47df given as context only. `INV-026-guard-worktree-rule/COVERAGE.json` and `plan/review/` left out of the reviewers' diff files.
- policy: lean · delta roster: delta-sweep, logic-correctness (owner of the round 1 high finding), test-veracity (the delta touches tests), scope-and-impact (the delta touches paths outside the contract's Scope list; D-73) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: no design-level finding at medium or above, so no verify pass.
- Mutation probe: 6 hand-made Python mutants on the delta's changed lines; all 6 survived (r-002, r-006, r-007, r-009, and two folded into r-001 and r-003).
- Dedup: r-001 joins the delta-sweep, logic-correctness and test-veracity findings on line 97; r-003 joins a logic-correctness and a test-veracity finding on line 53.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | high | correctness | delta-sweep+logic-correctness+test-veracity | hooks/lib/worktree_placement_rule.py:97 | New SET_ENV first-argument test lets a SetEnvironmentVariable call through that the old text test refused. |
| r-002 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:41 | Mutant SURVIVED: dropping the `sc` and `ac` aliases from DRIVE_SETTERS leaves all 150 tests green. |
| r-003 | medium | correctness | logic-correctness+test-veracity | hooks/lib/worktree_placement_rule.py:53 | The env-drive assignment forms still miss `??=` and the Copy-Item / Rename-Item setters, although this round widened the list for `+=`, `sc` and `ac`. |
| r-004 | medium | correctness | logic-correctness | hooks/lib/worktree_placement_rule.py:87 | `eval` is added for Bash but PowerShell's `iex` / `Invoke-Expression` is not re-parsed, so the same bypass stays open in the PowerShell tool. |
| r-005 | medium | correctness | logic-correctness | hooks/lib/worktree_placement_rule.py:88 | The new `eval` handling misses `eval -- "..."` and an escaped variable name, so both bypass the variable and worktree rules. |
| r-006 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:208 | Mutant SURVIVED: dropping the `re.search(r"\s", words[verb].text)` clause leaves the suite green. |
| r-007 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:222 | Mutant SURVIVED: dropping `+ list(git_env)` (git environment assignments carried from `_program` effects) leaves the suite green. |
| r-008 | medium | correctness | logic-correctness | hooks/lib/worktree_placement_rule.py:282 | `_program` still returns the wrapper when `strip_prefixes` cannot read the program behind it, so `env $X git worktree add <outside>` and `env -S "git worktree add <outside>"` pass. |
| r-009 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:292 | Mutant SURVIVED: replacing `if effects.get("chdir"):` with `if False:` leaves the suite green. |
| r-010 | low | scope | scope-and-impact | SAFETY.md:45 | New sentence 'a folder outside Git passes every rule but the variable refusal' is likely too broad for the worktree rule. |
| r-011 | low | correctness | logic-correctness | hooks/lib/worktree_placement_rule.py:67 | Adding `set-content` / `add-content` to DRIVE_SETTERS refuses commands that only read the variable. |
| r-012 | low | test | scope-and-impact | hooks/tests/bench-hooks.py:272 | bench-hooks now exits 1 with 'wrong path' when a scenario's answer lacks its expected text, but no test runs that path. |

## Detail

### r-001 — New SET_ENV first-argument test lets a SetEnvironmentVariable call through that the old text test refused.
- Why: The test treats any first argument not starting with `$`, `(` or empty as a literal other name, so `"AFK_ALLOW_PROTECTED".Trim()`, `[string]"AFK_ALLOW_PROTECTED"`, `@("AFK_ALLOW_PROTECTED")[0]`, `"AFK_ALLOW_PROTECTED"+""`, `[Environment]::SetEnvironmentVariable.Invoke("AFK_ALLOW_PROTECTED","1")` and `[Environment].GetMethod("SetEnvironmentVariable",...).Invoke($null,@("AFK_ALLOW_PROTECTED","1"))` all pass. The reflection and `.Invoke` forms never match `setenvironmentvariable\s*\(`. Probed with the commit 7d970119 module (all refused) and the real hook at b00e47df (PowerShell tool, `.Trim()` form: ALLOW).
- Fix: Refuse unless the first argument is a plain literal name (`[a-z0-9_]+` fully matched) other than the two names; also keep a bare `setenvironmentvariable` + name test for the non-call forms.
- Evidence: `for first in SET_ENV.findall(flat): ... if first == name.lower() or (first[:1] in ("$", "(", "") and name.lower() in flat):` replaced `if SET_ENV.search(flat) and name.lower() in flat:`

### r-002 — Mutant SURVIVED: dropping the `sc` and `ac` aliases from DRIVE_SETTERS leaves all 150 tests green.
- Why: Tests use only the full names `Set-Content`/`Add-Content`; with the aliases dropped, `sc env:AFK_WORKTREE_FOLDER 1` and `ac env:AFK_WORKTREE_FOLDER 1` pass the rule (the unmutated module refuses both; checked by a direct call).
- Fix: Add `sc Env:{n} 1` and `ac Env:{n} 1` rows to SETTING_FORMS in scripts/tests/test_worktree_placement_guard.py.
- Evidence: mutant: DRIVE_SETTERS = ("set-item", "si", "new-item", "ni", "set-content", "add-content"); pytest rc 0 (suite 150 passed)

### r-003 — The env-drive assignment forms still miss `??=` and the Copy-Item / Rename-Item setters, although this round widened the list for `+=`, `sc` and `ac`.
- Why: Verified on PowerShell 7 here: `$env:ZZ4 ??= 'q'`, `Copy-Item Env:PATH Env:ZZ1` and `Rename-Item Env:ZZ2 ZZ3` all set an environment variable. Real hook (PowerShell tool): `$env:AFK_ALLOW_PROTECTED ??= "1"` ALLOW; `Copy-Item env:PATH env:AFK_ALLOW_PROTECTED` ALLOW; `Rename-Item -Path env:FOO -NewName AFK_ALLOW_PROTECTED` also passes.
- Fix: Allow `[?+]*=` in `_env_drive`/`_sets` (`??=`), and add copy-item/cpi/ci/rename-item/rni/ren to the setter list, checking the destination operand.
- Evidence: `re.compile(r"^(?:\$\{env:" + name + r"\}|(?:\$env:|env:)" + name + r")(?:\s*\+?=.*)?$", re.I)` and `DRIVE_SETTERS = ("set-item", "si", "new-item", "ni", "set-content", "sc", "add-content", "ac")`

### r-004 — `eval` is added for Bash but PowerShell's `iex` / `Invoke-Expression` is not re-parsed, so the same bypass stays open in the PowerShell tool.
- Why: Real hook, PowerShell tool: `iex '$env:AFK_ALLOW_PROTECTED="1"'` ALLOW; `Invoke-Expression "git worktree add <outside>"` ALLOW; `iex "git worktree add <outside>"` ALLOW (the plain forms and `& { ... }` are denied).
- Fix: Add `invoke-expression` and `iex` to the programs whose joined arguments `_inner` recurses into.
- Evidence: `if program and not program[0].opaque and program_of(program[0]) == "eval":`

### r-005 — The new `eval` handling misses `eval -- "..."` and an escaped variable name, so both bypass the variable and worktree rules.
- Why: `_inner` joins the raw word texts: a leading `--` stays in the first word, and a backslash inside a name (`AFK_ALLOW_\PROTECTED=1`) is kept, so the inner parse sees no assignment although Bash's first parse removes the backslash and `eval` then assigns. Real hook: `eval -- "git worktree add <outside>"` ALLOW; `eval AFK_ALLOW_\PROTECTED=1 ls` ALLOW (while `eval AFK_ALLOW_PROTECTED=1 ls` is denied).
- Fix: Drop a leading `--` and strip backslashes from each joined word (as `_bare` does) before recursing.
- Evidence: `found.append(" ".join(w.text for w in program[1:]))`

### r-006 — Mutant SURVIVED: dropping the `re.search(r"\s", words[verb].text)` clause leaves the suite green.
- Why: No test passes a quoted git verb holding whitespace (`git 'worktree add' ../../out`). The unmutated module returns an unknown target for it (refused); the mutant returns no target (allowed), a bypass the suite would not catch.
- Fix: Add `git 'worktree add' ../../out` to the refused rows of test_a_target_that_cannot_be_worked_out_is_refused.
- Evidence: mutant: if verb < len(words) and (words[verb].opaque): ; pytest rc 0 (suite 150 passed)

### r-007 — Mutant SURVIVED: dropping `+ list(git_env)` (git environment assignments carried from `_program` effects) leaves the suite green.
- Why: The only GIT_DIR tests put the assignment in front of the git word on the same segment; none sets GIT_DIR through `env` behind `then`/`do`/`!`. In the unmutated module the effect reaches `_environ` (direct call: git_env populated, GIT_DIR applied); the mutant ignores it.
- Fix: Add a test with `if true; then env GIT_DIR=<unlisted repo>/.git git worktree add ../../out; fi` that expects the rule silent (mirror the same-segment unlisted-repository test).
- Evidence: mutant: environ = _environ(list(segment.git_env), folder, gitdir, workdir) ; pytest rc 0 (suite 150 passed)

### r-008 — `_program` still returns the wrapper when `strip_prefixes` cannot read the program behind it, so `env $X git worktree add <outside>` and `env -S "git worktree add <outside>"` pass.
- Why: The fallback pops only assignments and control words; `rest[0]` stays `env` (not opaque, not `git`), so `_targets` returns [] and no refusal is made, which contradicts the new docstring line 'A target or git verb the guard cannot work out ... counts as outside'. Also `sudo $X git worktree add ...` and `nice $X ...`. Real hook: `env $X git worktree add <outside>` ALLOW; `env -S "git worktree add <outside>"` ALLOW (same result with the old module, so not a regression, but this round rewrote the function and closed the sibling opaque-verb hole).
- Fix: When `effects["opaque"]` is set and the command mentions a worktree, return an unknown target `(None, spot, None)`.
- Evidence: `while rest and not rest[0].opaque and (ASSIGN.match(rest[0].text) or rest[0].text in KEYWORDS): rest.pop(0)`

### r-009 — Mutant SURVIVED: replacing `if effects.get("chdir"):` with `if False:` leaves the suite green.
- Why: No test runs `env -C <dir>` behind a control word; in the unmutated module the folder moves to `<dir>` (direct call: target resolved from /tmp/q), so a relative target is judged from the wrong folder under the mutant.
- Fix: Add a test with `if true; then env -C <outside dir> git worktree add ../x; fi` that expects a refusal naming the resolved target.
- Evidence: mutant: if False:  # an `env -C` behind a control word ; pytest rc 0 (suite 150 passed)

### r-010 — New sentence 'a folder outside Git passes every rule but the variable refusal' is likely too broad for the worktree rule.
- Why: Inferred from worktree_placement_rule.py:351-354 and :362: the rule judges the listed repository the command targets (`-C`, GIT_DIR, creator `--repo`), not the session folder, so `git -C <listed> worktree add <outside>` run from a non-Git folder is likely refused; no test covers a non-Git cwd (test_worktree_placement_guard.py:152 uses an agent worktree cwd), so unverified.
- Fix: Scope the sentence to commands that name no listed repository, or add a guard test from a non-Git cwd and state its result.
- Evidence: +folder outside Git passes every rule but the variable refusal above, and

### r-011 — Adding `set-content` / `add-content` to DRIVE_SETTERS refuses commands that only read the variable.
- Why: Every argument is tested against the drive pattern, so the value operand counts as a target: `Set-Content -Path out.txt -Value $env:AFK_ALLOW_PROTECTED`, `Add-Content log.txt "$env:AFK_ALLOW_PROTECTED"` and `Add-Content log.txt $env:AFK_ALLOW_PROTECTED` are refused (old module: pass).
- Fix: For the content setters match only the path operand (first positional, `-Path`, `-LiteralPath`), not the `-Value` operand.
- Evidence: `if prog in DRIVE_SETTERS:\n        return any(drive.match(a) for a in args)`

### r-012 — bench-hooks now exits 1 with 'wrong path' when a scenario's answer lacks its expected text, but no test runs that path.
- Why: scripts/tests/test_bench_hooks.py (loads the module, runs only --only read, worktree-create, worktree-remove, plus the budget check at :94) never runs the new bash-listed, bash-worktree-add or bash-worktree-move scenarios or the `expect` check, so a broken expectation reaches only the continue-on-error CI step (.github/workflows/tests.yml:103-106).
- Fix: Add a test that runs `--only bash-worktree-add bash-worktree-move --runs 1` and asserts exit 0 and the 'added over bash-listed' line, or a unit test of the `wrong` branch.
- Evidence: if wrong:  # the scenario timed some other path than the one it names
