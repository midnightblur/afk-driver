# Review round 6 — 0006-worktree-guard (8b8cad0)

- Verdict: **blocking** — crit=0 high=1 med=4 low=0
- Diff: delta fe66dc08..8b8cad05 (the round 5 fix commit); the full slice 5b62663..8b8cad05 given as context only. `plan/review/` left out of the reviewers' diff files.
- policy: lean · delta roster: delta-sweep (also the owner of the round 5 high finding), test-veracity (the delta touches tests) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: no design-level finding at medium or above, so no verify pass.
- Mutation probe: 6 hand-made Python mutants on the delta's changed lines; 2 survived the whole file (r-002, r-004), 3 killed, 1 judged equivalent.
- Ledger keys: r-001..r-005 = 0006-worktree-guard/f065..f069.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | high | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:184 | The new setter-operand check covers only `@(`/`$(` on one following segment; `(`, `;`-separated and newline-separated arrays still set a rule variable unrefused. |
| r-002 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:116 | Mutant survives: `_arrays` no longer joins a word that starts with a comma (`word.startswith(",")` replaced by `False`); all 320 tests pass. |
| r-003 | medium | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:181 | A harmless read of a rule variable inside a setter's `$(...)`/`@(...)` operand is now refused as 'refused to set'. |
| r-004 | medium | test | test-veracity | hooks/lib/worktree_placement_rule.py:185 | Mutant survives: the setter-operand check no longer treats a `$(` operand as one (`words[-1].text in ("@", "$")` changed to `("@",)`); all 320 tests pass. |
| r-005 | medium | correctness | delta-sweep | hooks/lib/worktree_placement_rule.py:396 | The unreadable-program `-S` split window is applied to the string word, not to the `-S` flag, so `$ENV <any option> -S '<git worktree add ...>'` still passes. |

## Detail

### r-001 — The new setter-operand check covers only `@(`/`$(` on one following segment; `(`, `;`-separated and newline-separated arrays still set a rule variable unrefused.
- Why: The fix closes one operand spelling while sibling spellings of the same write keep the old behaviour, so a plain `Set-Content -Path ('Env:AFK_ALLOW_PROTECTED') -Value 1` lifts the guard.
- Fix: Track operand state across every segment up to the matching close paren (and treat a lone `(` last word like `@`/`$`), or judge each inner segment of a setter's parenthesised operand.
- Evidence: Probe on 8b8cad05 (refusal(cmd, cwd, powershell=True)) returned None for: `Set-Content -Path ('Env:AFK_ALLOW_PROTECTED') -Value 1`; `Set-Content -Path:('Env:AFK_WORKTREE_FOLDER') x`; `Set-Content ('Env:AFK_ALLOW_PROTECTED') 1`; `New-Item -Path ('Env:AFK_ALLOW_PROTECTED') -Value 1`; `Set-Content @('Env:OTHER'; 'Env:AFK_ALLOW_PROTECTED') 1`; `Set-Content @(<newline>'Env:OTHER'<newline>'Env:AFK_ALLOW_PROTECTED') 1`. Cause: line 184-185 `operand = ... and words[-1].text in ("@", "$")` and `operand` is reset by the next segment (line 179 block runs for one segment only).

### r-002 — Mutant survives: `_arrays` no longer joins a word that starts with a comma (`word.startswith(",")` replaced by `False`); all 320 tests pass.
- Why: No test uses a spaced PowerShell array (`Set-Content Env:OTHER , Env:<rule var> 1`); the original refuses that command, the mutant passes it, and the delta's tests only use the trailing-comma form `Env:OTHER, Env:{n}`.
- Fix: Add SETTING_FORMS rows `Set-Content Env:OTHER , Env:{n} 1` and `Set-Content Env:OTHER ,Env:{n} 1`.
- Evidence: if joined and (joined[-1].endswith(",") or word.startswith(",")):  -- probe: original REFUSED, mutant pass for `Set-Content Env:OTHER , Env:AFK_ALLOW_PROTECTED 1`; whole-file run 320 passed.

### r-003 — A harmless read of a rule variable inside a setter's `$(...)`/`@(...)` operand is now refused as 'refused to set'.
- Why: The operand scan matches any word of the next segment against the env-drive pattern, with no check that the word is written rather than read.
- Fix: Judge the inner segment only when its program is a plain item name or bare path (not a read cmdlet such as Get-Content/Get-Item/Write-Output), or only the words in a path-bearing position.
- Evidence: Probe returned REFUSED for `Add-Content log.txt $($env:AFK_ALLOW_PROTECTED)`, `Set-Content out.txt $(Get-Content env:AFK_ALLOW_PROTECTED)`, `Set-Content -Path out.txt -Value $(Get-Content env:AFK_WORKTREE_FOLDER)`; fe66dc08 had no operand scan (diff lines `+        if operand:  # the words inside a setter's @(…) or $(…) operand`), and the sibling `Set-Content -Path out.txt -Value $env:{n}` is a listed passing row.

### r-004 — Mutant survives: the setter-operand check no longer treats a `$(` operand as one (`words[-1].text in ("@", "$")` changed to `("@",)`); all 320 tests pass.
- Why: Only the `@(...)` operand form is tested, so the `$(...)` branch is dead to the suite; the original refuses `Set-Content $('Env:OTHER','Env:<rule var>') 1` and the mutant passes it.
- Fix: Add SETTING_FORMS rows for the `$('Env:OTHER','Env:{n}')` operand with `Set-Content` and `Set-Content -Path`.
- Evidence: and words[-1].text in ("@", "$")  -- probe: original REFUSED, mutant pass for `Set-Content $('Env:OTHER','Env:AFK_ALLOW_PROTECTED') 1` and the `-Path` form; whole-file run 320 passed.

### r-005 — The unreadable-program `-S` split window is applied to the string word, not to the `-S` flag, so `$ENV <any option> -S '<git worktree add ...>'` still passes.
- Why: `lead` is `i <= hidden + 2` for the word being split; the quoted string sits at index 3 after one extra option, so it is not split and the worktree verb is never seen.
- Fix: Set `lead` on the flag (record the split request while `lead`, then split the next word regardless of its index), or widen the window to the whole program when the first word is opaque.
- Evidence: Probe through the real hook (Bash, agent worktree) returned pass for `$ENV -u A -S 'git worktree add ../../out'`, `$ENV -i -S 'git worktree add ../../out'`, `$ENV A=1 B=2 -S 'git worktree add ../../out'`, `${ENV} -u A --split-string='git worktree add ../../out'`; only `$ENV -S '...'` was refused. Code: `lead = envish or (hidden is not None and i <= hidden + 2)` then `splits = lead and (split or text.startswith(("-S", ...)))`.
