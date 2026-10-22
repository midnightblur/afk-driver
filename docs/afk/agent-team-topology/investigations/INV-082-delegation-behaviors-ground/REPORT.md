midnightblur/afk-driver@83372fd104a23208e3c1eac76fb6c085e0adcfa8 · closed-with-frontier · boundaries 13/14 · unverified 2 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-082-delegation-behaviors-ground/COVERAGE.json

## Answer
- A new BEHAVIORS.md entry must pass the field grammar, a body of 1-2 lines, a doctrine `.md` whose `§` heading exists (DELEGATION.md:22 `## Spawn rules`), a `${AFK_PLUGIN_ROOT}/DELEGATION.md` pointer unless self-contained, no provider name in the body, and a rendered block of 6000 bytes or fewer (scripts/behavior_registry.py:37-48, :373-403). The block is 2570 bytes at head.
- At head the entry needs one `registry` row in hooks/behavior-dispositions.tsv (else :460-462 refuses) and its inventory id in EXPECTED_INVENTORY_IDS (else :453-459 refuses); scripts/tests/test_behavior_registry_gate.py:51 goes red on either miss.
- origin/main 82c3db8 has no EXPECTED_INVENTORY_IDS and appends an all-repos `ci-parity-before-push` entry; the id-set edit and an appended row will likely conflict at the main merge (inference, no trial merge run).
- An all-repos entry renders first, in file order (:219-239). Every installed block then audits stale, and behavior-drift.sh prints the setup notice at SessionStart (hooks/hooks.json:24, hooks/hooks.codex.json:24).
- Renaming `Must-delegate triggers` or `Spawn rules` fails the gate (delegate-exploration doctrine, BEHAVIORS.md:38). Native check A scans DELEGATION.md and BEHAVIORS.md for harness words (hooks/native-contract-gate.sh:97, :132-138).
- No gate or test reads DELEGATION.md's spawn-rule, watchdog or tier text; check L reads only PROVIDERS.md `## Model tiers`.
- Only skills/afk/autopilot/SKILL.md:40 and skills/utils/investigate/SKILL.md:44 arm the stall watchdog; hooks/stall-watchdog.sh never exits 0 and a kill disarms it, so a park is a kill and a resume a fresh arm. No test runs it.
- AGENTS.md:22 restates DELEGATION.md:49 with no carve-out (FRESHNESS.md:43).
- The pane switch is `transport.pane-switch` (scripts/afk-config.py:53-54, :591-601).
## Sites
- breaks (unless the same commit adds the TSV row and the id): scripts/tests/test_behavior_registry_gate.py:51; scripts/behavior_registry.py:453-462
- goes stale (outside this change's lines): hooks/stall-watchdog.sh:2, hooks/README.md:101, INVESTIGATION.md:118 (inference); spawn steps autopilot/SKILL.md:35, SUBAGENT-PROMPT.md:3, bug/SKILL.md:68, review/SKILL.md:43, settle-change/SKILL.md:48, investigate/SKILL.md:44 until their own subtasks land (inference)
- wrong today: providers/PARITY.md:155 (no gate reads DELEGATION.md agent names); hooks/README.md:99 (the drift hook checks only its own target)
- unchanged, load-bearing: hooks/behavior-registry-gate.sh:22-26; hooks/native-contract-gate.sh:224-272; scripts/behavior_registry.py:887 (pinned by hooks/tests/hook-smoke.sh:641); skills/afk/setup/scripts/install_block.py; hooks/behavior-drift.sh:37
- every other site: COVERAGE.json nodes table
## Frontier
- B14: installed harness copies, developers' user instruction files, live pull-request CI.
## Unverified
- c-4a196692 (not load-bearing): the hit set is complete over the name forms searched.
- c-d65c6c7b (not load-bearing): the installed Codex plugin root was not read; its `## Spawn rules` heading rests on git history.
