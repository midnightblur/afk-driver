C:\Users\mvu\PersonalProjects\afk-driver-agent-teams@9d9fce6 · closed-with-frontier · boundaries 13/14 · unverified 0 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-001-config-reader/COVERAGE.json

## Answer

One new family key plus a kind block breaks no existing config: refusal is computed at run time (scripts/afk-config.py:541-542, :586-597). It turns the CHILD_KEYS drift test red unless CONFIG.md gains the kind's map row. It needs a transports tuple and a `_choice` call, or any value validates. Dispatch and the shell view need no edit (hooks/lib/adapter.sh:32,45; export_shell at scripts/afk-config.py:1001). Ship the reader and its CONFIG.md rows first, or in one commit; config files that use `transport` come after. Only `validate` refuses the key; `load`, `get` and `export-shell` pass it through (:1084-1090). Schema effects: none.

## Sites that break

- scripts/tests/test_afk_config.py:268 and :286 — red unless CONFIG.md gains the kind's map row, in the schema table at CONFIG.md:91.
- scripts/afk-config.py:541 — refuses both keys until they are in TOP_LEVEL.
- scripts/tests/test_afk_config.py:124 — red only if .afk/config.yaml gains `transport` before the reader does.
- hooks/lib/adapter_registry_check.py:101 — needs a `transport` enum row once adapters/transport/<kind>/ exists; runs from hooks/skill-registry-gate.sh:194.
- ADAPTERS.md:1 — "four adapter families" becomes false; no check guards it.

## Unguarded

- No transports tuple and no `_choice` call (scripts/afk-config.py:46-49, :544-546), so any `transport` value validates.
- No test ties TOP_LEVEL to CONFIG.md.
- TYPOS (scripts/afk-config.py:237) is a hand-written list, so a typo in the new block is not refused.
- skills/utils/report-issue/scripts/collect_env.sh:43-46 keeps its own family list, so filed issues leave out `transport`.
- GRILL-LOG.md:125 and :161 understate the change.

## Frontier

B14: consumer repositories' configs, `~/.afk/config.yaml` and installed plugin copies are outside this repository.

## Unverified

None load-bearing. A developer's local config may already carry `transport`. Kind names are not fixed, so a shell-name collision was not checked against real names.
