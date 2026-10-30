midnightblur/afk-driver@22ab4de0ff03d9b3b79425494df03938b56d0899 · partial · boundaries 10/14 · unverified 5 (load-bearing 3) · ledger: docs/afk/afkv2/investigations/INV-001-v1-sessionstart-hooks/COVERAGE.json

## Answer

Both providers register the same SessionStart set: group `*` with 7 commands and group `startup|clear` with nested-steering.sh (hooks/hooks.json:3-54, hooks/hooks.codex.json:3-54). The only difference is the root variable, `${CLAUDE_PLUGIN_ROOT}` or `${PLUGIN_ROOT}`. Codex finds its file through .codex-plugin/plugin.json:54. .claude-plugin/plugin.json has no `hooks` key, so Claude uses its default `hooks/hooks.json`.
Every command except occupancy runs `afk-python …/run-hook.py --soft --deadline N plugin <handler>`. The launcher takes its root from `__file__` (run-hook.py:90) and never reads CLAUDE_PROJECT_DIR. It exports AFK_PLUGIN_ROOT and AFK_HOOK_DEADLINE (:1034-1036), finds Git Bash (:376-412) and copies stderr (:616). On exit 0 it passes stdout through unchanged (:642). Under `--soft` it always exits 0.
Output to the session: plain stdout from update-notice.sh:146-151, agents-md-config-check.sh:49-51 (Claude only) and behavior-drift.sh:37. JSON `hookSpecificOutput.additionalContext`, plus `additional_context`, from protected-branch-occupancy.py:31-32 and remove-worktree.py:478-481 (adds `systemMessage`). No handler writes an unconditional "hook fired" marker.

## Sites

- Registration: hooks/hooks.json:3-54; hooks/hooks.codex.json:3-54; .codex-plugin/plugin.json:54
- Launcher: hooks/run-hook.py:90, :472-473, :616-649, :983-1048, :1126-1140
- Provider facts: hooks/lib/providers/claude.json:11-16; codex.json:5,11-16; hooks/lib/provider_facts.py:18-29; hooks/lib/provider.sh:26-57
- Handlers: install-git-hooks.sh:33,48,81,88; update-notice.sh:82,146-151; agents-md-config-check.sh:47-51; behavior-drift.sh:20-42; worktree-prune.sh:14-15; protected-branch-occupancy.py:29-35; nested-steering.sh:35-41
- Docs: CAPABILITIES.md:32-57; PROVIDERS.md:11-29,109-118; providers/CONFORMANCE.md:21,452,458; providers/HARNESS-MATRIX.md:65-81; adr/0005-managed-behavior-transport.md:15-30
- Tests: scripts/tests/test_hook_failures.py:99-176; scripts/tests/test_run_hook.py:172-179,672-716; scripts/tests/test_occupancy.py:229-259; hooks/tests/bench-hooks.py:53-60; hooks/tests/hook-smoke.sh:819-844

## Doc-vs-code findings

- CAPABILITIES.md:44 shows `${CLAUDE_PLUGIN_ROOT}`, but the Codex manifest uses `${PLUGIN_ROOT}` (hooks.codex.json:9-50).
- hooks/README.md:99 says behavior-drift "compares both targets". The code checks only the current provider's target (behavior-drift.sh:20-22).
- HARNESS-MATRIX.md:88 says the nested mode lives in claude.sh. It is in claude.json:12.
- codex.sh:8 detects only PLUGIN_ROOT. Python also uses CODEX_THREAD_ID (codex.json:5).

## Frontier

- B14: how each harness reads SessionStart stdout, finds plugin hooks, and applies trust. Vendor behavior, outside the repository.

## Unverified

- B1, B4, B8 partial: the import-alias name form was not enumerated, and the agent counter-search did not cover untracked files.
- How plain-text SessionStart stdout reaches each harness's model: no repository source states it (3 load-bearing claims).
- Whether a `source=clear` envelope is tested through the `startup|clear` matcher.
