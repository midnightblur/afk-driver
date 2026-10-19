# Review — 0001-glossary-terms (base c3d0751, round tag r2)

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (lean trigger: 0017 and 0018 consume this slice), refactor-safety (pre-existing lines changed) · skipped: domain-alignment, api-contract (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
verified: no design-level finding at medium or above, so no verify pass · mutation probe: not applicable (no production code)
reviewed head: ade8ab1 · slice diff: commit 52ada6a

Verdict: advisory — crit=0 high=0 med=3 low=1

| Id | Severity | Class | Location | Finding |
|---|---|---|---|---|
| r-001 | medium | compliance | GLOSSARY.md:60 | The new Run entry narrows "run" to team-topology work, but existing entries (GLOSSARY.md:325, :328, :351, :445) use it for one skill execution (LANGUAGE.md:21). The tooltip injector (scripts/lavish/inject.py:227) also shows the narrow definition on every "run" in a lavish page. |
| r-002 | medium | correctness | GLOSSARY.md:76 | The Role agent entry says "Always a pane agent unless the pane switch says subagent", but with no pane transport found, role agents run as subagents (PRD AC-044, AC-041). |
| r-003 | medium | test | plan/0001-glossary-terms.md:43 | The glossary usage tier cannot fail for the new entries: the feature's own design documents count as consumers of every new term (scripts/glossary_usage.py:24, :32, :108-121). |
| r-004 | low | spec | GLOSSARY.md:169 | The One-off pattern entry drops the exception that a one-off pattern with no roles carries no charter (PRD AC-066; SDD.md:85, :406). |
