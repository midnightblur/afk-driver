# Review — 0002-config-transport-and-pattern-keys (base d9e1569, round tag r1)

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (lean trigger: 0005, 0006 and 0017 consume this slice), refactor-safety (pre-existing lines changed), api-contract (the configuration schema is the public surface consuming repositories write) · skipped: domain-alignment (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
verified: the two design-level findings share a line with a spec finding and were merged into it, so no verify pass · mutation probe: not applicable (no production Java)
reviewed head: 69d002b · slice diff: commit 69d002b · forge ledger: pull request 112, keys 0002-config-transport-and-pattern-keys/f001 to f009

Verdict: advisory — crit=0 high=0 med=5 low=4

| Id | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|
| r-001 | medium | spec | skills/utils/report-issue/scripts/collect_env.sh:74 | The collector writes a new `transport` field that the issue template never shows. | open: its reader, ISSUE-TEMPLATE.md:42, is outside Scope |
| r-002 | medium | spec | CONFIG.md:159 | CONFIG.md said the reader does not check pattern field values, but it checks their types. | fixed in 44b1c34 |
| r-003 | medium | scope | skills/utils/report-issue/ISSUE-TEMPLATE.md:42 | The template's Adapters row lists four families, so the new field reaches no issue. | open: outside Scope |
| r-004 | medium | test | scripts/tests/test_afk_config.py:633 | Several new shape checks had no test that proves they refuse bad input. | fixed in 44b1c34 |
| r-005 | medium | correctness | scripts/afk-config.py:643 | A mapping under `includes` crashed the reader instead of being refused. | fixed in 44b1c34 |
| r-006 | low | spec | scripts/afk-config.py:654 | An empty stage-map list passed the check. | fixed in 44b1c34 |
| r-007 | low | scope | docs/afk/agent-team-topology/investigations/INV-076-config-team-keys/REPORT.md:1 | The investigation files are outside the Scope list. | withdrawn by the adjudicator |
| r-008 | low | test | skills/utils/report-issue/scripts/collect_env.sh:47 | No test runs the collector and checks the new field. | fixed in 44b1c34 |
| r-009 | low | test | scripts/tests/test_afk_config.py:607 | A test checked an internal table instead of what the reader returns. | fixed in 44b1c34 |
