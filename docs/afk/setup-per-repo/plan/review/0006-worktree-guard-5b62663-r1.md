# Review — 0006-worktree-guard, round 1

- Verdict: **blocking** — crit=0 high=1 med=13 low=8
- Diff: the whole slice 5b62663..7d970119 (one commit); `INV-026-guard-worktree-rule/COVERAGE.json` left out of the reviewers' diff file for size.
- policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (complexity complex), refactor-safety (pre-existing lines changed) · skipped: api-contract, domain-alignment (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: no design-level finding at medium or above, so no verify pass.
- Mutation probe: hand-made Python mutants on `hooks/lib/worktree_placement_rule.py` (the Maven probe does not apply); 9 survivors, folded into r-005 to r-012.
- Dedup: r-002 and r-003 each join one refactor-safety and one scope-and-impact finding on the same stale sentence.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | high | correctness | logic-correctness | hooks/lib/worktree_placement_rule.py:272 | A `then`/`do`/`!` keyword before `git worktree add` or the creator call skips the whole add/move/creator rule. |
| r-002 | medium | spec | refactor-safety+scope-and-impact | AGENTS.md:201 | Convention line still says the guard refuses only identified mutations of guarded resources and 'everything else passes'; the slice edited :230 but not :201. |
| r-003 | medium | spec | refactor-safety+scope-and-impact | PROVIDERS.md:58 | 'Protected-branch guard' mechanics say an opaque target and an unknown program pass elsewhere; the new rule refuses an opaque or unreadable worktree target in a listed repo. |
| r-004 | medium | correctness | logic-correctness | hooks/lib/worktree_placement_rule.py:60 | Inference: three PowerShell forms that set the guarded variables pass: `${env:NAME} = 1`, `Set-Content Env:NAME 1` and `$env:NAME += 1`. |
| r-005 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:67 | SURVIVED: the cmd `set NAME=value` form is untested. |
| r-006 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:114 | SURVIVED: three option-parser edges are untested (`no-` option forms, `--end-of-options`, a flag given a value it does not take). |
| r-007 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:188 | SURVIVED: an unreadable GIT_DIR / GIT_WORK_TREE value is untested. |
| r-008 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:196 | SURVIVED: the `-c alias.*=worktree` branch is untested. |
| r-009 | medium | correctness | logic-correctness | hooks/lib/worktree_placement_rule.py:197 | Possible bypass: a git verb held in a variable, or `eval '...'`, passes although the rule says a command it cannot read counts as outside. |
| r-010 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:245 | SURVIVED: creator-call branches for a variable `--name` with `--parent`/`--dir`, and for `--repo`, are untested. |
| r-011 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:312 | SURVIVED: the PlacementError refusal is untested, and the root-rule refusal on line 316 too. |
| r-012 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:360 | SURVIVED: the fail-closed refusal for a worktree command the rule could not read has no test. |
| r-013 | medium | test | refactor-safety | scripts/tests/test_existing_worktree_outside_root.py:409 | Possible masked pin: the shell_mutations move case now ends in the new rule's refusal for both twins, so it no longer reaches the old move-destination verdict. |
| r-014 | medium | test | test-veracity | scripts/tests/test_worktree_placement_guard.py:235 | test_the_developer_runs_a_plain_add_anywhere never runs the guard. |
| r-015 | low | spec | refactor-safety | SAFETY.md:44 | The paragraph after the new sentence still says a folder outside Git passes everywhere, but the inline-variable refusal applies in every placement. |
| r-016 | low | scope | scope-and-impact | docs/afk/setup-per-repo/investigations/INV-026-guard-worktree-rule/REPORT.md:1 | The ledger for the changed `decide()` caller set has verdict `partial`, so the caller set is not proven closed. |
| r-017 | low | scope | scope-and-impact | docs/afk/setup-per-repo/plan/DECISIONS.md:504 | Six non-run-artifact files outside the contract's ## Scope were edited, and the Scope list was not amended. |
| r-018 | low | design | refactor-safety | hooks/lib/worktree_placement_rule.py:23 | The new rule imports private `_nested` and the constants DECLARE, PRINT_ONLY, MAX_DEPTH from `lavish_direct`, but FRESHNESS and the lavish_direct change trigger do not name this dependent. |
| r-019 | low | correctness | scope-and-impact | hooks/lib/worktree_placement_rule.py:86 | Possible false refusal: any agent command whose text contains `SetEnvironmentVariable` and either variable name anywhere is refused as a setter. |
| r-020 | low | test | refactor-safety | hooks/tests/bench-hooks.py:91 | The new `bash-worktree-add` scenario writes a hand-built repository list but no test checks that it reaches the deny path. |
| r-021 | low | spec | spec-fidelity | hooks/tests/bench-hooks.py:92 | The bench times only `git worktree add`; `git worktree move` has no scenario, and no 50 ms figure appears in the bench output. |
| r-022 | low | test | test-veracity | scripts/tests/test_worktree_placement_guard.py:136 | Every worktree-target case runs through the Bash tool only; none uses the PowerShell tool or another provider's shell tool. |

## Detail

### r-001 — A `then`/`do`/`!` keyword before `git worktree add` or the creator call skips the whole add/move/creator rule.
- Why: `worktree_refusal` reads `steps()` words, which strip prefixes without `keywords=True` (`shell_mutations.py:836`), so `_targets` sees program `then`/`do`/`!` and returns no target, while `variable_refusal` (line 314) does pass `keywords=True`.
- Fix: In `_program` re-run `strip_prefixes(segment.words, keywords=True)` instead of trusting `words`, and add loop/if/`!` cases to the placement tests.
- Evidence: Probe on a scratch copy at the plugin's real hook (agent in a worktree of a listed repo, outside target /tmp/xx): `if true; then git worktree add /tmp/xx; fi`, `for n in a b; do git worktree add /tmp/$n; done`, `while true; do git worktree add /tmp/xx; done`, `! git worktree add /tmp/xx` and `for n in a; do create-worktree --branch b --dir x --parent /tmp; done` all returned no deny; `true; git worktree add /tmp/xx` and `true && { git worktree add /tmp/xx; }` were denied. Contract: "an agent's `git worktree add` whose target resolves outside `<root>/<short name>` is refused".

### r-002 — Convention line still says the guard refuses only identified mutations of guarded resources and 'everything else passes'; the slice edited :230 but not :201.
- Why: The guard now also refuses a worktree add/move/creator target outside the root (listed repos) and an inline AFK_WORKTREE_FOLDER/AFK_ALLOW_PROTECTED (every repo) for an agent, so an auto-loaded rule states a verdict that is no longer true. INV-026 REPORT.md listed AFK_WORKTREE_FOLDER-stale lines `AGENTS.md:201,230`; D-71 does not list :201 as left.
- Fix: Add one clause for the placement rule and the inline-variable refusal to the 'One linked worktree per session or team' bullet, or record :201 in D-71 as left for 0013.
- Evidence: AGENTS.md:201 `...a worktree another live session holds, and, in the first two, any shell command it cannot prove read-only; everything else passes.`

### r-003 — 'Protected-branch guard' mechanics say an opaque target and an unknown program pass elsewhere; the new rule refuses an opaque or unreadable worktree target in a listed repo.
- Why: FRESHNESS.md row for the guard requires PROVIDERS.md 'Protected-branch guard' to move with a verdict-rule change. D-71 left it on the grounds that the 'lifts every refusal' sentence stays true, but lines 58-63 now contradict `git worktree add $T` (refused: 'cannot work out ... may be outside').
- Fix: Add the placement rule and inline-variable refusal to that paragraph, or amend D-71 to record this paragraph as stale for a later subtask.
- Evidence: PROVIDERS.md:58-61 `Elsewhere the guard judges the resource a call mutates, not the command's shape (ADR-0010): ... an opaque target (variable, substitution, glob) and an unknown program pass.`

### r-004 — Inference: three PowerShell forms that set the guarded variables pass: `${env:NAME} = 1`, `Set-Content Env:NAME 1` and `$env:NAME += 1`.
- Why: `_env_drive` only matches a bare `$env:NAME`/`env:NAME` word followed by `=`, and `Set-Content` is not in the setter list, yet each form sets the process variable that child processes read (ADR-0004: no agent-settable bypass).
- Fix: Accept the braced `${env:NAME}` word, `+=` and the `set-content`/`sc`/`sv`-style setters in `_sets`, or refuse any PowerShell word naming `env:<NAME>` outside a read position.
- Evidence: Probe with tool `PowerShell` on a scratch copy: `${env:AFK_ALLOW_PROTECTED} = 1`, `Set-Content Env:AFK_ALLOW_PROTECTED 1` and `$env:AFK_ALLOW_PROTECTED += 1` returned no deny, while `$env:AFK_ALLOW_PROTECTED='1'`, `Set-Item Env:AFK_ALLOW_PROTECTED 1` were denied. Line 60: `if drive.match(words[0].text) and ("=" in words[0].text or words[1:2] and words[1].text.startswith("=")):`. Unverified: that the harness's PowerShell session carries the variable into a later child process.

### r-005 — SURVIVED: the cmd `set NAME=value` form is untested.
- Why: Disabling the `prog == "set"` branch left all 97 tests green; SETTING_FORMS has no `set` form, though D-70 adds it as a refused form. The bare `export NAME` branch (line 74, `not (set(options) & PRINT_ONLY ...)` -> `False`) also survived.
- Fix: Add `set {n}=1` (Bash and PowerShell) and a bare `export {n}` standing alone to SETTING_FORMS.
- Evidence: line 67 `if prog == "set":` -> `if False and prog == "set":`: 97 passed; line 74 option test -> `False`: 97 passed

### r-006 — SURVIVED: three option-parser edges are untested (`no-` option forms, `--end-of-options`, a flag given a value it does not take).
- Why: Each of `names = list(table)` (line 114), `elif text in ("--",)` (line 136) and `elif False and "=" in text` (line 142) left 97 tests green, so a mis-parsed target could pass the rule.
- Fix: Add ADD_FORMS entries `--no-checkout`, `--end-of-options {t}` and a `--detach=x {t}` case asserting the refusal text.
- Evidence: line 114 `names = list(table) + [f"no-{n}" for n in table]` -> `names = list(table)`: 97 passed; line 136 `elif text in ("--", "--end-of-options"):` -> `("--",)`: 97 passed; line 142 `elif not value and "=" in text:` -> `elif False and ...`: 97 passed

### r-007 — SURVIVED: an unreadable GIT_DIR / GIT_WORK_TREE value is untested.
- Why: Replacing `raise Unknown(...)` with `continue` (so the target is judged against the wrong repository) left 97 tests green; no case sets those variables.
- Fix: Add cases `GIT_DIR=$X git worktree add ../../o` and a literal `GIT_DIR=<path> git worktree add ...` asserting the refusal.
- Evidence: line 188 `raise Unknown(f"${name}")` -> `continue`: 97 passed

### r-008 — SURVIVED: the `-c alias.*=worktree` branch is untested.
- Why: Setting `aliased = False and any(...)` left all 97 tests green, so the alias route to `git worktree add` that D-68 says is refused has no pin.
- Fix: Add a case such as `git -c alias.wt=worktree wt add ../../out` that asserts the unknown-target refusal.
- Evidence: line 196 `aliased = any(re.match(r"^alias\.", w.text, re.I) and "worktree" in w.text.lower() for w in words[1:verb])` -> `aliased = False and any(...)`: 97 passed

### r-009 — Possible bypass: a git verb held in a variable, or `eval '...'`, passes although the rule says a command it cannot read counts as outside.
- Why: `_git_targets` returns `[]` when `words[verb]` is not literally `worktree` (an opaque `$V` is just a non-worktree verb) and `_nested` never expands `eval`, so neither reaches the 'cannot work out' refusal.
- Fix: Return `[(None, folder, None)]` when `words[verb].opaque`, and add `eval` (its joined arguments) to the nested scripts the rule re-parses.
- Evidence: Probe on a scratch copy, agent in a listed repo's worktree: `V='worktree add /tmp/xx'; git $V` and `eval 'git worktree add /tmp/xx'` both returned no deny; line 197 reads `if verb >= len(words) or _bare(words[verb]) != "worktree":`. Module docstring and D-68 say a variable or opaque word counts as outside; `xargs`/`find -exec`/aliases are the only listed frontier.

### r-010 — SURVIVED: creator-call branches for a variable `--name` with `--parent`/`--dir`, and for `--repo`, are untested.
- Why: Disabling the opaque-name check (line 245) and ignoring `--repo` (line 252) each left 97 tests green, so a creator call can be judged against the wrong repository or let a variable name hide an outside `--parent`.
- Fix: Add creator cases `--name "$N" --parent <outside>` and `--repo <listed> --dir <outside>` run from an unlisted folder.
- Evidence: line 245 `if name.opaque and ("--parent" in given or "--dir" in given):` -> `if False and (...)`: 97 passed; line 252 `folder = _path(given["--repo"], spot) if "--repo" in given else spot` -> `folder = spot`: 97 passed

### r-011 — SURVIVED: the PlacementError refusal is untested, and the root-rule refusal on line 316 too.
- Why: Changing the PlacementError handler to `return None` (fail open), and separately disabling the `REFUSED and rule != OUTSIDE` branch, each left 97 tests green; no test drives an unsound root or a placement error through the guard.
- Fix: Add guard tests with a broken or relative worktreeRoot in the sandbox home and a placement error, asserting the 'worktree root: ...' and 'placement has no answer' deny texts (D-68).
- Evidence: line 312 `except placement.PlacementError as problem:` body -> `return None`: 97 passed; line 316 `if verdict.state == placement.REFUSED and verdict.rule != placement.OUTSIDE:` -> `if False and ...`: 97 passed

### r-012 — SURVIVED: the fail-closed refusal for a worktree command the rule could not read has no test.
- Why: Replacing the refusal return with `return None` left all 97 tests of test_worktree_placement_guard.py green (baseline 97 passed; control mutant on line 'if target.is_dir()' was killed), so the rule could fail open on an internal fault unnoticed.
- Fix: Add a test that forces an exception inside worktree_refusal for a worktree-naming command and asserts the 'could not read this command' deny text.
- Evidence: line 360: return f"{HEAD}. Cause: the guard could not read this command ({problem}). Move: ask the developer." -> `return None`: 97 passed

### r-013 — Possible masked pin: the shell_mutations move case now ends in the new rule's refusal for both twins, so it no longer reaches the old move-destination verdict.
- Why: The env sets AFK_PROVIDER=claude (:137) and the main repo is listed (:224). `away` is `f.base/moved-<label>`, which lies outside the root `f.base/r`. The new rule in `decide` therefore denies both twins with the same normalised text before `unproven`/`worktree_target` run, so the twin comparison stays green while it stops covering the protected-branch/occupant verdict for `git worktree move` (inferred from reading; not run).
- Fix: Put `away` inside `<root>/proj` for this case, or add a case that still reaches the old verdict, so the pre-existing pin keeps exercising `shell_mutations` and `decide`'s move branch.
- Evidence: `away = (f.base / f"moved-{s.label}").as_posix()`; `guard(f, s, "Bash", {"command": f"git worktree move {here} {away}"}, cwd=f.main)`; new block at hooks/lib/protected_branch_guard.py:833-839 returns before `unproven` (:841).

### r-014 — test_the_developer_runs_a_plain_add_anywhere never runs the guard.
- Why: It calls git directly and asserts the folder exists, so it proves nothing about the rule and cannot fail on a guard bug; the 'developer passes' case is only covered by the detector-off test.
- Fix: Drop it, or run the guard with detector=False on a plain add and assert reason is None.
- Evidence: def test_the_developer_runs_a_plain_add_anywhere(world): target = ...; git(world["a"], "worktree", "add", "-q", "-b", "devown", str(target)); assert target.is_dir()

### r-015 — The paragraph after the new sentence still says a folder outside Git passes everywhere, but the inline-variable refusal applies in every placement.
- Why: The sentence added at SAFETY.md:38-39 says 'In every repository it refuses an agent command that sets AFK_WORKTREE_FOLDER or AFK_ALLOW_PROTECTED', and the test `test_setting_a_rule_variable_in_an_unlisted_repository_is_refused` shows no placement exemption; INV-026 noted this as stale only if the variable half is not limited to repositories.
- Fix: Qualify the line ('...pass, except the inline-variable refusal') or say the placement exemption covers verdicts on mutations only.
- Evidence: SAFETY.md:44-46 `...a folder outside Git and `AFK_ALLOW_PROTECTED=1` set by a human at launch pass everywhere.`

### r-016 — The ledger for the changed `decide()` caller set has verdict `partial`, so the caller set is not proven closed.
- Why: The checklist makes a non-closed verdict a finding; COVERAGE.json line 123 has "verdict": "partial" with B1 pending (import-alias and wire name forms never enumerated), though the report marks it not load-bearing (unverified 1, load-bearing 0).
- Fix: Close the B1 name-form check (or record why it cannot apply) and re-stamp the ledger as closed-with-frontier.
- Evidence: REPORT.md line 1: 'partial · boundaries 12/14 · unverified 1 (load-bearing 0)'; COVERAGE.json:2554 'import-alias and wire name forms carry no value (seed placeholders), so no pass enumerated them'. My own grep for `.decide(`/`decide(` over *.py,*.sh found one call site (protected_branch_guard.py:976, in main()), consistent with the report.

### r-017 — Six non-run-artifact files outside the contract's ## Scope were edited, and the Scope list was not amended.
- Why: D-71 records the edits (AGENTS.md, FRESHNESS.md, SAFETY.md, hooks/README.md, hooks/genericity-allow.txt, docs/afk/protected-branch-guard/PRD.md) with 'Supersedes: none', so the contract's Scope list still stands and each path is out of Scope.
- Fix: Record a decision superseding the Scope passage (or add the six paths to the contract's ## Scope) so the same-commit freshness edits are in lane.
- Evidence: D-71 'Supersedes: none'; 0006-worktree-guard.md ## Scope lists only protected_branch_guard.py, worktree_placement_rule.py, the three test files and bench-hooks.py.

### r-018 — The new rule imports private `_nested` and the constants DECLARE, PRINT_ONLY, MAX_DEPTH from `lavish_direct`, but FRESHNESS and the lavish_direct change trigger do not name this dependent.
- Why: A later refactor of `lavish_direct` (D-70 already plans folding `_sets_host`) can break this import. The import sits in `decide` outside `refusal`'s try, so `main()` returns 0 when no mutation is identified (protected_branch_guard.py:982-983) and the whole rule, including the AFK_ALLOW_PROTECTED refusal, fails open silently. Only the new test file would notice.
- Fix: Add `hooks/lib/worktree_placement_rule.py` to the lavish_direct row's move-together list in FRESHNESS.md, or expose a public helper and import that.
- Evidence: `from lavish_direct import DECLARE, MAX_DEPTH, PRINT_ONLY, _nested` (hooks/lib/worktree_placement_rule.py:245); lavish_direct.py:23-27,51 define them; FRESHNESS.md lavish row lists no worktree_placement_rule.

### r-019 — Possible false refusal: any agent command whose text contains `SetEnvironmentVariable` and either variable name anywhere is refused as a setter.
- Why: The check is a substring test over the whole lowercased, unquoted command (a commit message, echo or grep pattern qualifies), so a maintainer agent documenting both names is denied with no bypass line (inferred from reading; not executed).
- Fix: Limit the .NET-call text test to a segment whose program is PowerShell-like or require the name inside the call's argument list.
- Evidence: `flat = UNQUOTE.sub("", command).lower()` ... `if SET_ENV.search(flat) and name.lower() in flat: return _variable_text(name)` (worktree_placement_rule.py variable_refusal); the 'reading passes' test list has no case with SetEnvironmentVariable text.

### r-020 — The new `bash-worktree-add` scenario writes a hand-built repository list but no test checks that it reaches the deny path.
- Why: `list_clone` writes `repositories.json` and `config.yaml` by hand. If the shape or a root rule drifts (placement R-02, R-05 or R-06), the scenario times a pass or a different refusal and still prints rc 0; `test_bench_hooks.py` only covers read and the worktree lifecycle, plus uncovered/budget tables.
- Fix: Add a `test_bench_hooks.py` case running `--only bash-worktree-add --runs 1` that asserts the guard's deny output, or have the scenario check the refusal text once.
- Evidence: hooks/tests/bench-hooks.py:91-92 `"bash-worktree-add": Scenario(... "git worktree add {(scratch / 'outside').as_posix()}" ..., lifecycle=True, listed=True)`; list_clone :96-104; no `bash-worktree-add` in scripts/tests/test_bench_hooks.py.

### r-021 — The bench times only `git worktree add`; `git worktree move` has no scenario, and no 50 ms figure appears in the bench output.
- Why: The bullet and SDD §10 name add and move for a listed repository, and the bench prints only handler p50/p95 with no 50 ms reference (BUDGET_MS has no entry for the new scenario).
- Fix: Add a `bash-worktree-move` scenario with `listed=True` and print or note the 50 ms reference for both; record the measured numbers in the run report.
- Evidence: Acceptance: "The guard's added time on add and move for a listed repository is measured by the informational bench against the 50 ms budget ... and reported"; diff adds only `"bash-worktree-add": Scenario("PreToolUse", "Bash", {... "git worktree add {outside}"}, lifecycle=True, listed=True)`. BUDGET_MS (hooks/tests/bench-hooks.py:47-61) is unchanged.

### r-022 — Every worktree-target case runs through the Bash tool only; none uses the PowerShell tool or another provider's shell tool.
- Why: decide() loops over readings(tool, facts), so the PowerShell reading of add, move and creator calls is unpinned; only the variable forms use tool="PowerShell".
- Fix: Add PowerShell-tool cases for add, move and the creator call (backtick escapes, Set-Location) in a listed repository.
- Evidence: guard(world, world["agent"], form.format(t=target.as_posix())) with the default tool="Bash" for all add, move and creator tests
