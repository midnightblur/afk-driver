midnightblur/afk-driver@b33b6d087c78eed2554175c7c2602c8f888480c3 · closed-with-frontier · boundaries 13/14 · unverified 3 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-077-pattern-resolver-records-ground/COVERAGE.json

## Answer

At head b33b6d0 no code defines, imports or loads a pattern resolver, and no code reads scripts/team/patterns/. The only pattern check is the configuration reader's `_validate_saved_patterns`, which `validate` calls once.

- **Exit 2.** No surface runs a resolver today, so a resolver's exit 2 can reach only the planned team entry script, which also gives 2 for a refusal. To the hook runner, 2 is a refusal on Stop and PreToolUse only. To afk-config.py, 2 is an invalid configuration. To the plugin-source runner, 2 means blocked.
- **The genericity gate** needs allow entries for BP-1 to BP-5 and PS-1 to PS-4. The JSON records need none.
- **The native-contract gate** forbids harness vocabulary in STANDARD.md and in the markdown charter parts.
- **The comment gate** caps a run of added comment lines in resolver.py and its test at 2.
- **Records.**
  - Their field names must match PATTERN_KEYS and ROLE_KEYS in afk-config.py, or a saved copy fails validate.
  - Lifespans must be spelled Turn, Step or Feature, as manifest.py accepts.
- **FRESHNESS.md** owes a scripts/team row; **CHANGELOG.md** [Unreleased] owes one line.
- **MANIFEST.md** row P1 already covers every Python entry point.
- **The wiring gate** finds a consumer for every new file stem by name. resolve_pattern( owes an IOU until a later step calls it.
- **Stale design text.** SDD.md:1508-1509 and the plan 0005 excerpts are stale at head:
  - afk-config.py:696-699 refuses unknown role fields.
  - GLOSSARY.md:38 already lists the charter.

## Sites

- scripts/afk-config.py:57-62, :609-699, :785
- scripts/team/manifest.py (LIFESPANS)
- hooks/genericity-gate.sh, hooks/genericity-allow.txt
- hooks/native-contract-gate.sh, hooks/wiring-gate.sh, hooks/run-hook.py:95, :621; FRESHNESS.md, CHANGELOG.md, MANIFEST.md (P1)
- .claude/wiring-ious.md
- 4 tree-walking tests that reach new files: test_no_review_id_citations.py, test_execute_step_pointers.py, test_native_contract_events.py, test_plugin_source_gates.py

## Frontier

- B14: these are outside this repository:
  - consuming repositories' .afk/config.yaml and .afk/hooks.json
  - installed plugin cache copies
  - live team runs

## Unverified (none load-bearing)

- c-16522caf: the hit set holds every reference over the name forms searched. This is the standard completeness caveat.
- c-1f8df806: the branch-range genericity CI run on BP, PS or INV tokens in plan prose was not run.
- c-f3c88d98: the uncommitted slice-0005 edits were not judged. The answer is about the committed head.
