C:\Users\mvu\PersonalProjects\afk-driver-agent-teams@9d9fce6 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-002-schema-table/COVERAGE.json

## Answer

Three sites read the CONFIG.md schema table or CHILD_KEYS:

- scripts/afk-config.py:586 — `validate()` iterates CHILD_KEYS.
- scripts/tests/test_afk_config.py:267-290 — parity test between the table and the map.
- hooks/lib/adapter_registry_check.py:131-138 — `family_enum`, which parses table rows by family name.

## Sites that break

One new family row plus one CHILD_KEYS entry breaks these unless they get matching edits:

- scripts/afk-config.py:51-57 (TOP_LEVEL) and :541 — the new key is refused as an unknown top-level key. Pinned by scripts/tests/test_afk_config.py:134.
- scripts/afk-config.py:46-49 and :544-546 — enum tuples and `_choice` calls are per family and hand-written; a new family's value goes unvalidated. Pinned at :129 for tracker only.
- scripts/tests/test_afk_config.py:281 — hand-written values set; an unlisted backticked child value fails the test. :287 and :289 need a matching CONFIG.md map row in the same change.
- hooks/lib/adapter_registry_check.py:45 and :137 — a family directory spelled neither as the row key nor as the key minus a trailing "s" reports "has no enum row". Unguarded.
- Documents going stale: ADAPTERS.md:1, CLAUDE.md:9 and :197, AGENTS.md:9 and :197 ("four adapter families"; AGENTS.md is untracked).
- Finding: ADAPTERS.md:137 covers adding a kind, not adding a family.

## Frontier

B14: other repositories, deployment manifests, live consumers.

## Unverified

One claim, not load-bearing: the hit set holds every reference to CHILD_KEYS over the name forms this pass searched.
