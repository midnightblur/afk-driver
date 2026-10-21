# Review — 0013-provider-layer-codex (base ecf0fd5, round tag r1)

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity (always), refactor-safety (the diff edits existing lines), logic-correctness (slice 0017-spawn-steps uses the seam "Codex agent lookup") · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: bf9d5bf · diff: ecf0fd5..bf9d5bf · forge ledger: pull request 112, keys 0013-provider-layer-codex/f001 to f006

Verdict: advisory — crit=0 high=0 med=4 low=2 (7 reviewer findings merged by file and line into 6)

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| r-001 | f001 | medium | scope | CHANGELOG.md:106 | "Re-run `/afk:setup`" does not refresh an installed stub's name, because setup's check never reads the name field | fixed in ebad0d6: delete the old copies, then run setup |
| r-002 | f002 | medium | correctness | PROVIDERS.md:23 | The Codex cell made the same promise | fixed in ebad0d6 |
| r-003 | f003 | medium | correctness | PROVIDERS.md:138 | The rule gave a single-model role with no reachable equivalent no defined action | fixed in ebad0d6: it waits like a debate role (D-98) |
| r-004 | f004 | medium | test | providers/codex/agents/afk-afk-reader.toml:1 | No standing check that each stub's name equals its role | withdrawn by a fresh adjudicator: Scope excludes hooks/ and scripts/tests/, SDD settles that no gate reads the name field |
| r-005 | f005 | low | spec | CHANGELOG.md:107 | Same setup gap as r-001 | fixed in ebad0d6 |
| r-006 | f006 | low | test | providers/CONFORMANCE.md:439 | The proof did not record its stub source and spawned only one role by name | fixed in ebad0d6: records the run over the five bf9d5bf stubs |

The run over the five stubs used files byte-identical to bf9d5bf after the root replacement (hashes compared); all five roles answered by skill name.
