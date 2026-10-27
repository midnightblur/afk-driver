# Review — 0001-pure-domain-rules, remediation round 2

Base: `a140274` · policy: lean delta · activated: delta-sweep, spec-fidelity, logic-correctness, api-contract, test-veracity, code-quality · skipped: remaining concerns (delta policy) · verified: 0 upheld / 0 downgraded / 0 dropped

## Verdict

Blocking: 3 high and 1 medium findings.

## Findings

| ID | Severity | Concern | Finding | Evidence |
|---|---|---|---|---|
| r2-001 | high | spec-fidelity, logic-correctness, api-contract, code-quality | The publication codec accepts non-Boolean closure evidence. | `scripts/glossary_lifecycle/domain.py:417`; PRD AC-034 |
| r2-002 | high | spec-fidelity, logic-correctness | Tooltip projection splits an alias that contains `/`. | `scripts/glossary_lifecycle/markdown.py:180` |
| r2-003 | high | logic-correctness | Serialization splits an alias that contains a comma. | `scripts/glossary_lifecycle/markdown.py:141` |
| r2-004 | medium | test-veracity | The slash-alias test omits the lossy tooltip projection. | `scripts/glossary_lifecycle/tests/test_markdown.py:80` |

REVIEW: blocking — crit=0 high=3 med=1 low=0 findings: docs/afk/P2P-2067/plan/review/0001-pure-domain-rules-a140274-r2.findings.json
In plain terms: Type checks and alias handling still permit incorrect evidence and changed vocabulary.
