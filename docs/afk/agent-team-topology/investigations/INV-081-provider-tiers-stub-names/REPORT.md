midnightblur/afk-driver@ecf0fd57f2ee6565774f2163fc0168eb693d4b8b · closed-with-frontier · boundaries 13/14 · unverified 2 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-081-provider-tiers-stub-names/COVERAGE.json

## Answer
- Native check L is the only parser of the `## Model tiers` section: it reads from the heading to the next `##` and keeps only bar-delimited table lines (hooks/native-contract-gate.sh:227-239). Its runner is hooks/plugin-source-gates.sh:97, at commit (precommit-gates.sh:153) and in CI (.github/workflows/tests.yml:85, :99).
- The fallback paragraph is still PROVIDERS.md:138. A bar-free sentence appended to it gives check L 0 problems; on a copy of HEAD with both changes the gate exited 0 and test_model_tier_gate.py passed 9 of 9.
- Trap: a tier-row literal on :138 makes test_model_tier_gate.py:75 and :112 fail, because their edit() replaces the first occurrence of the row text.
- The genericity gate re-judges the whole of :138 and refuses only an upper-case ticket-shaped token (hooks/lib/sensitive-patterns.tsv:8); a lower-case model id passes.
- Nothing in the repository reads a Codex stub's `name =` value. Checks D and L open each stub by filename and read only `model` and `model_reasoning_effort` (native-contract-gate.sh:219, :262-267); setup O5 copies and probes by filename (skills/afk/setup/MANIFEST.md:867, :890). Change (2) is unguarded by any test.
- Check A scans CHANGELOG.md and refuses a line naming the second harness by its product name (native-contract-gate.sh:90, :137); PROVIDERS.md and providers/CONFORMANCE.md are excluded.
- behavior_registry.py:518 reads only the `Managed behavior` row (PROVIDERS.md:34): irrelevant to both changes.
- Docs: providers/CONFORMANCE.md:439 records `afk-afk-reader` as the Codex agent type from a dated 2026-09-30 probe; :249 is round-5 cutover history (:47, :240). The tracer passes disagree on whether :249 goes stale (claim c-0ca65819 says stale; node B13:providers/CONFORMANCE.md:249 says history). PROVIDERS.md:22 ("same names") is refuted at head and holds after the change (inference).
- Deployment order: none for gates; each machine keeps the old name field under ~/.codex/agents/ until /afk:setup copies the stubs again (inference).
## Sites
- breaks (conditional): scripts/tests/test_model_tier_gate.py:75, :112 (only if :138 holds a row literal); hooks/native-contract-gate.sh:137 (a changelog line naming the harness); hooks/lib/sensitive-patterns.tsv:8 (an upper-case ticket-shaped token on :138)
- goes stale: providers/CONFORMANCE.md:439 (agent type proof)
- unchanged, load-bearing: hooks/native-contract-gate.sh:219, :227-239, :262-267; scripts/tests/test_model_tier_gate.py:58, :73, :82; scripts/tests/test_native_contract_events.py:57; skills/afk/setup/MANIFEST.md:867, :890; scripts/behavior_registry.py:518; PROVIDERS.md:157
- every other site: COVERAGE.json nodes table
## Frontier
- B14: Codex CLI's agent lookup is external; observed by name field once on 0.157.0 (GRILL-LOG.md:398), to be re-proved live. Installed copies under ~/.codex/agents/ lie outside the repository. Rationale lookup: none for PROVIDERS.md:138 and afk-afk-reader.toml:1.
## Unverified
- c-544786bc (not load-bearing): the hit set is complete over the name forms searched.
- c-53c67584 (not load-bearing): whether the O5 fix asks the human before it replaces an installed stub whose only change is the name field.
