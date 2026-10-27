# Review — 0001-pure-domain-rules

Base: `a140274` · policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness, api-contract · skipped: refactor-safety, domain-alignment (no trigger) · deferred: agents-md-compliance, code-quality, design-quality, resilience (feature gate) · verified: 1 upheld / 0 downgraded / 0 dropped

## Verdict

Blocking: 7 high and 5 medium findings.

## Findings

| ID | Severity | Concern | Finding | Evidence |
|---|---|---|---|---|
| r-001 | high | spec-fidelity, api-contract | RE-07 and RE-08 omit required actor, prompt, auditor, and fingerprint evidence. | `scripts/glossary_lifecycle/domain.py:136`; PRD Records and evidence |
| r-002 | high | spec-fidelity | RE-03 hashes raw wording and cannot preserve a confirmed nonsemantic edit. | `scripts/glossary_lifecycle/domain.py:211`; PRD AC-010 |
| r-003 | high | spec-fidelity, logic-correctness | Any known finding ID closes without a valid resolution or satisfied closure test. | `scripts/glossary_lifecycle/domain.py:267`; PRD AC-034 |
| r-004 | high | spec-fidelity | Routing drops unmatched domain areas and accepts empty owner chains. | `scripts/glossary_lifecycle/domain.py:298`; PRD AC-001 |
| r-005 | high | spec-fidelity | No versioned publication-record codec parses records before replay. | `scripts/glossary_lifecycle/domain.py:244`; subtask seam contract |
| r-006 | high | spec-fidelity | The cross-parser corpus excludes adopted identity metadata and aliases. | `scripts/glossary_lifecycle/tests/test_markdown.py:50`; ADR-0002 |
| r-007 | high | logic-correctness | Markdown round-trip drops Avoid, Code, and Related metadata. | `scripts/glossary_lifecycle/markdown.py:104`; SDD §9b |
| r-008 | medium | logic-correctness | Serialization splits an Also alias that contains `/`. | `scripts/glossary_lifecycle/markdown.py:128` |
| r-009 | medium | test-veracity | The canonicalization test only reorders keyword arguments. | `scripts/glossary_lifecycle/tests/test_domain.py:43` |
| r-010 | medium | test-veracity | Parser parity lacks explicit adopted-format expectations. | `scripts/glossary_lifecycle/tests/test_markdown.py:66` |
| r-011 | medium | test-veracity | Gate tests do not prove admission or freshness behavior. | `scripts/glossary_lifecycle/tests/test_domain.py:139` |
| r-012 | medium | api-contract | Separate term ID and hash arrays permit mismatched attestations. | `scripts/glossary_lifecycle/domain.py:128` |

REVIEW: blocking — crit=0 high=7 med=5 low=0 findings: docs/afk/P2P-2067/plan/review/0001-pure-domain-rules-a140274.findings.json
In plain terms: Required evidence, replay safety, routing, parsing, and tests are incomplete, so this slice cannot ship.
