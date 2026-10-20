midnightblur/afk-driver@53d1586136e0ee3fff69accf2f9536eb96114b03 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-080-spawn-rule-setup-ground/COVERAGE.json

## Answer
- Setup builds its election at run time from MANIFEST.md; an [opt-in] row is offered deselected, a `human:` fix is walked through and probed again, a declined row reports `skipped (user choice)`; the no-human skip is stated per row, never globally (skills/afk/setup/SKILL.md:80-132; MANIFEST.md:616-618).
- set_instruction_files.py writes only `pluginConfigs."agents-md@builtin".options.instructionFiles`, after a backup; the planned change leaves it and its tests unchanged (set_instruction_files.py:33-49, :115-126; scripts/tests/test_set_instruction_files.py:34-86).
- No code reads or writes a harness permission rule or a settings `permissions` key at this head.
- Gates: the comment gate runs at agent commits only (hooks/precommit-gates.sh:148); the four plugin-source gates run at agent commits and in CI (hooks/plugin-source-gates.sh:97; .github/workflows/tests.yml:85, :99).
- Breaks only if the change ignores them: check A fails a register row naming the harness without an allow line (hooks/native-contract-gate.sh:90-101, :137); check K fails a claude_*.py name outside claude.sh (:547-574); the genericity gate fails ticket-shaped ids, check 0b over the whole tree (hooks/lib/sensitive-patterns.tsv:8; hooks/genericity-gate.sh:135-145); the comment gate fails more than 2 comment lines (hooks/lib/comment_gate.py:22).
- Unchanged: checks G and H key on adapter file names (:505-531); skill-registry check C reads only hooks/*.sh and hooks/lib/*.sh (hooks/skill-registry-gate.sh:157, :183); no gate or test lists every adapter function or variable.
- Position tests: a row between C15 and C16 breaks scripts/tests/test_team_transport.py:486; row text outside H0 saying "no `.afk/config.yaml`" breaks scripts/tests/test_setup_secrets_repo_root.py:119.
- Every provider.sh sourcer runs under `set -u` and test_run_hook.py:159-163 asserts empty stderr, so an adapter line run at source time must read no unset variable (inference).
- In a Codex agent shell provider.sh detects `unknown` (providers/CONFORMANCE.md:434; codex.sh:8), so a check reading the provider layer cannot name Codex there.
- A Python file under scripts/team/ that runs bash through run-hook.py's find_bash follows scripts/team/probe.py:111-128 and trips no gate (inference).
- Stale, no gate: the add-harness checklist in providers/CONFORMANCE.md:402-408 does not list the new adapter functions.
## Sites
- breaks (conditional): hooks/native-contract-gate.sh:137, :547; hooks/lib/sensitive-patterns.tsv:8; hooks/lib/comment_gate.py:22; adapters/tracker/github-issues/adapter.json:28; providers/CONFORMANCE.md:406
- unchanged, load-bearing: skills/afk/setup/SKILL.md:80-132; skills/afk/setup/MANIFEST.md:616-618; skills/afk/setup/scripts/set_instruction_files.py:33-49; hooks/lib/provider.sh:13-163; hooks/skill-registry-gate.sh:157, :183; hooks/native-contract-gate.sh:448, :505-531; scripts/team/probe.py:111-128; scripts/tests/test_team_transport.py:486; scripts/tests/test_setup_secrets_repo_root.py:119; scripts/tests/test_run_hook.py:159-163; scripts/tests/test_h2_move.py:211-217
- every other site: COVERAGE.json nodes table
## Frontier
- B14: users' settings files, the harness's own evaluation of the printed rule and installed plugin caches lie outside this repository; no pre-existing line in scope, so no rationale lookup.
## Unverified
- c-b12524b8 (not load-bearing): the seed's hit set is complete over the name forms searched.
