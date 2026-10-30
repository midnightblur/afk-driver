# Review of 0003-engine-core-schema-show-poll, round 2

Telemetry only. The review record is pull request 155.

policy: lean · activated: delta-sweep, logic-correctness and api-contract (owners of the fixed high findings), test-veracity (the change touches tests) · skipped: scope-and-impact (own Scope check over the change found nothing), refactor-safety, domain-alignment (no trigger) · deferred: agents-md-compliance, code-quality, design-quality, resilience (→ feature gate)
verified: no design-level finding, so no verify pass ran. Caller set: no pre-existing public symbol changed, so no coverage ledger exists.

Diff e39818dc..00944916.

Verdict: advisory, 0/0/1/2 (critical/high/medium/low). Under owner ruling R-2 the 3 findings stay on the pull request with no fix and no dispute round, and the gate passes.

- r-001 medium test afkv2/tests/engine/test_engine_core.py:496: Map-entry name test puts the bad entry at index 0 only, so the index fallback is not proven.
- r-002 low correctness afkv2/engine/engine.py:71: describe() names a map by any truthy id, so a non-string id is shown as the map name instead of its index.
- r-003 low smell afkv2/engine/registry.py:19: Possible drifted twin: registry hard-wires page-v0.schema.json while engine.py selects the schema file by document version.
