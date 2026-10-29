# Review round 3 — 0006-worktree-guard (062db01)

- Verdict: **advisory** — crit=0 high=0 med=6 low=5
- Diff: delta b00e47df..062db01c (the round 2 fix commit); the full slice 5b62663..062db01c given as context only. `plan/review/` left out of the reviewers' diff files.
- policy: lean · delta roster: delta-sweep, logic-correctness (owner of the round 2 high finding), test-veracity (the delta touches tests) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: no design-level finding at medium or above, so no verify pass.
- Mutation probe: 6 hand-made Python mutants on the delta's changed lines; 5 survived (r-001, r-005, r-006, r-007, r-008), 1 killed.
- Dedup: r-001 joins the delta-sweep (abbreviated options), logic-correctness (common parameters) and test-veracity (valued-option mutant) findings on `_path_operand`; r-009 and r-010 join a delta-sweep and a logic-correctness finding each.
- Ledger keys: r-001..r-011 = 0006-worktree-guard/f035..f045.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | medium | correctness | delta-sweep+logic-correctness+test-veracity | hooks/lib/worktree_placement_rule.py:73 | Narrowing the setter check to `_path_operand` lets an abbreviated option hide the `env:` path, which the old check refused. |
| r-002 | medium | correctness | logic-correctness | hooks/lib/worktree_placement_rule.py:116 | `Invoke-Expression -Command '...'` (and `iex -Command`) is not read, so `iex` closes only the positional form. |
| r-003 | medium | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:308 | `_program` now re-parses `segment.words`, so an opaque-program command applies `env -C <relative>` twice and probes the wrong folder. |
| r-004 | medium | correctness | logic-correctness | hooks/lib/worktree_placement_rule.py:333 | A command-substitution program, `$(which git) worktree add ../../out`, is not refused, though `$GIT`, `"$(...)"` and backtick forms are. |
| r-005 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:335 | Mutant survives: dropping `or "create-worktree" in joined` from the unreadable-program branch fails no test. |
| r-006 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:336 | Mutant survives: narrowing the opaque-program regex from `(?:add|move)` to `(?:add)` fails no test. |
| r-007 | low | test | test-veracity | hooks/lib/worktree_placement_rule.py:43 | Mutant survives: removing the `rni` and `ren` aliases from `ITEM_SETTERS` fails no test. |
| r-008 | low | test | test-veracity | hooks/lib/worktree_placement_rule.py:58 | Mutant survives: removing `\?\?|` from `_env_drive` fails no test. |
| r-009 | low | correctness | delta-sweep+logic-correctness | hooks/lib/worktree_placement_rule.py:76 | ITEM_SETTERS refuses a read: `any(drive.match(a))` matches `$env:NAME` in the source position of `Copy-Item`/`Move-Item`. |
| r-010 | low | correctness | delta-sweep+logic-correctness | hooks/lib/worktree_placement_rule.py:124 | `SET_ENV_INDIRECT` makes any `SetEnvironmentVariable` followed by `.`, `,` or `)` plus a rule-variable name anywhere in the command a refusal, including prose. |
| r-011 | low | correctness | logic-correctness | hooks/lib/worktree_placement_rule.py:334 | The opaque-program branch matches `worktree add` inside any quoted string, so harmless commands behind an unreadable program are refused in a listed repository. |

## Detail

### r-001 — Narrowing the setter check to `_path_operand` lets an abbreviated option hide the `env:` path, which the old check refused.
- Why: `_path_operand` matches only exact `-path`/`-literalpath`/`-pspath`/`-lp` and exact valued options, but PowerShell accepts unique prefixes. In `Set-Item -V 1 -Pa env:AFK_ALLOW_PROTECTED` the operand becomes `1`, so the command passes. The replaced `any(drive.match(a) for a in args)` caught it.
- Fix: Treat any `-p...` prefix of `path`/`literalpath`/`pspath` as a path option and any `-v...` prefix of `value` as valued, or fall back to `any(drive.match(a))` for the PATH_SETTERS when the operand is not found by an exact option.
- Evidence: -        return any(drive.match(a) for a in args)  /  +        return bool(drive.match(_path_operand(args)))  and  PATH_OPTIONS = ("-path", "-literalpath", "-pspath", "-lp"); `if low.startswith("-"): i += 2 if low in VALUED_OPTIONS else 1`. No SETTING_FORMS row uses an abbreviated option.

### r-002 — `Invoke-Expression -Command '...'` (and `iex -Command`) is not read, so `iex` closes only the positional form.
- Why: The joined text is `-Command $env:AFK_ALLOW_PROTECTED=1`, whose first word is `-Command`, so no assignment is recognised. Probe: `Invoke-Expression -Command '$env:AFK_ALLOW_PROTECTED=1'` returns no refusal, while `iex '$env:AFK_ALLOW_PROTECTED = 1'` is refused.
- Fix: For iex/invoke-expression drop a leading `-Command` (and `-Command:`) word before joining, as the eval branch drops `--`.
- Evidence: +        else:
+            found.append(" ".join(w.text for w in args))

### r-003 — `_program` now re-parses `segment.words`, so an opaque-program command applies `env -C <relative>` twice and probes the wrong folder.
- Why: `shell_mutations.steps` already folds `effects['chdir']` into `spot`; the re-parse refills `effects['chdir']` when `words` is [] (e.g. `env -C sub $X git worktree add ../x`), and `_targets` resolves it again against `spot` (here/sub/sub). A non-repository or unlisted folder then gives NOT_LISTED and the command passes.
- Fix: Skip the second `chdir` resolve in `_targets` when `words` was empty, or take `chdir` only from the keyword-prefix strip, not from a re-parse of `segment.words`.
- Evidence: +    program = strip_prefixes(words or segment.words, effects, keywords=True)  (worktree_placement_rule.py:308) with `if effects.get("chdir"): spot = shell_mutations.resolve(effects["chdir"], spot)` (line 323) and `spot = resolve(effects["chdir"], here) if effects.get("chdir") else here` (shell_mutations.py:837). The new test uses an absolute `-C` path, so the relative case is untested.

### r-004 — A command-substitution program, `$(which git) worktree add ../../out`, is not refused, though `$GIT`, `"$(...)"` and backtick forms are.
- Why: The segmenter splits `$(` into an opaque `$` segment, an open/close pair and a separate segment `worktree add ../../out` whose program is `worktree`, so `_targets` returns [] and the opaque branch is never reached. Probe from a listed repository's agent worktree: `$(which git) worktree add ../../out` returns None, while `` `which git` worktree add ../../out `` and `"$(which git)" worktree add ../../out` are refused as unreadable. The parser is untouched by this delta, but the delta's own opaque-program closure (`env $X`, `sudo $X`) leaves this sibling form open.
- Fix: Treat a segment that directly follows a `$(...)` close mark with no operator as the argument list of an opaque program, or refuse `worktree add|move` words whose preceding segment ended in a substitution.
- Evidence: +    if program[0].opaque or effects.get("opaque"):  # a program the guard cannot read, e.g. behind `env $X`

### r-005 — Mutant survives: dropping `or "create-worktree" in joined` from the unreadable-program branch fails no test.
- Why: Whole-file run stayed green (197 passed). The added cases in `test_a_target_that_cannot_be_worked_out_is_refused` (`env $X`, `env -S`, `sudo $X`, `git 'worktree add'`) all use `git worktree add`; none hides a `create-worktree` call behind an opaque program.
- Fix: Add a refused case such as `env $X <plugin>/scripts/create-worktree --parent P --dir D` to the parametrized list.
- Evidence: hooks/lib/worktree_placement_rule.py:335 `if re.search(r"\bworktree\s+(?:add|move)\b", joined) or "create-worktree" in joined:`; mutant removes the `or` clause: 197 passed.

### r-006 — Mutant survives: narrowing the opaque-program regex from `(?:add|move)` to `(?:add)` fails no test.
- Why: Whole-file run stayed green (197 passed). The pre-delta code accepted `worktree move` behind an opaque program; no test covers `env $X git worktree move ...`, so the regression guard on `move` is missing.
- Fix: Add `env $X git worktree move ../x ../../y` to the refused-target list.
- Evidence: hooks/lib/worktree_placement_rule.py:335 `re.search(r"\bworktree\s+(?:add|move)\b", joined)`; mutant `(?:add)`: 197 passed.

### r-007 — Mutant survives: removing the `rni` and `ren` aliases from `ITEM_SETTERS` fails no test.
- Why: Whole-file run stayed green (197 passed). SETTING_FORMS covers only `Rename-Item`, `Copy-Item` and `New-Item` by full name; the aliases `rni`, `ren`, `cpi`, `mi`, `ni` are untested.
- Fix: Add one aliased form per untested alias (for example `ren env:FOO {n}`) to SETTING_FORMS.
- Evidence: hooks/lib/worktree_placement_rule.py:43 `"rename-item", "rni", "ren")`; mutant `"rename-item")`: 197 passed.

### r-008 — Mutant survives: removing `\?\?|` from `_env_drive` fails no test.
- Why: Whole-file run stayed green (197 passed). The added test `$env:{n} ??= '1'` is caught by the separate `"??="` entry in `_sets`; the no-space form `$env:{n}??='1'`, which only the regex branch covers, is untested. Original code refuses that form (direct call), so the regex change is unpinned.
- Fix: Add `$env:{n}??='1'` to SETTING_FORMS.
- Evidence: hooks/lib/worktree_placement_rule.py:58 `(?:\s*(?:\?\?|\+)?=.*)?$`; mutant `(?:\s*(?:\+)?=.*)?$`: 197 passed.

### r-009 — ITEM_SETTERS refuses a read: `any(drive.match(a))` matches `$env:NAME` in the source position of `Copy-Item`/`Move-Item`.
- Why: `Copy-Item $env:AFK_WORKTREE_FOLDER dest` only reads the variable (the source), yet the check is positional-blind, unlike the PATH_SETTERS branch, which tests only the written operand.
- Fix: For copy-item/cpi, test only the destination operand (`-Destination` or second positional); keep the any-arg test for the new-name forms.
- Evidence: +        return any(drive.match(a) or (under_env and a.upper() == name) for a in args)  with `_env_drive` matching `^(?:\$\{env:N\}|(?:\$env:|env:)N)...$`. The new read-passes test covers only Set-Content/Add-Content.

### r-010 — `SET_ENV_INDIRECT` makes any `SetEnvironmentVariable` followed by `.`, `,` or `)` plus a rule-variable name anywhere in the command a refusal, including prose.
- Why: A commit message or note such as 'document SetEnvironmentVariable, AFK_ALLOW_PROTECTED' (quotes are stripped before the match) is now refused for an agent in every checkout, which the old `(`-only match did not do.
- Fix: Require the indirect form to sit in a PowerShell command, or require a `[environment]` or `.invoke(`/`getmethod(` anchor before the match.
- Evidence: +SET_ENV_INDIRECT = re.compile(r"setenvironmentvariable\s*[.,)]")  and  +    called = firsts or SET_ENV_INDIRECT.search(flat)  # `.Invoke(` or a reflection lookup names no argument. The passing-prose test uses `'document SetEnvironmentVariable and {n}'` (no punctuation after the word).

### r-011 — The opaque-program branch matches `worktree add` inside any quoted string, so harmless commands behind an unreadable program are refused in a listed repository.
- Why: Words are joined with spaces before the regex, so a single quoted word 'worktree add' counts as the verb; the old code compared whole words. Probes (listed repository): `$GIT log --grep 'worktree add'`, `$GIT commit -m 'docs: worktree add flow'`, `env $X echo worktree add notes` are refused ("cannot work out this command's worktree target").
- Fix: Match consecutive whole words (`worktree` then `add`/`move`) instead of the joined string; keep the single-word 'worktree add' case only when it is the word right after the program.
- Evidence: +        joined = " ".join(_bare(w) for w in program if not w.opaque).lower()
+        if re.search(r"\bworktree\s+(?:add|move)\b", joined) or "create-worktree" in joined:
