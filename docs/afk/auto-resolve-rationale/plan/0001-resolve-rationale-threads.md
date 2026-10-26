## Goal

Resolve each inline rationale thread before its successful batch receipt becomes durable. Recover and resolve existing threads during retry.

## Complexity

standard

## Design refs

(none — sliced from the PRD without an SDD, per human approval)

## Scope

- skills/afk/review/scripts/forge_ledger.py
- scripts/tests/test_rationale_ledger.py
- RATIONALE.md
- CHANGELOG.md
- skills/afk/execute/SKILL.md
- skills/utils/settle-change/SKILL.md
- docs/afk/auto-resolve-rationale/**

## Seams

(none — no SDD seam register)

## Acceptance

- [ ] New rationale comments are resolved before the receipt is posted, satisfying AC-001.
- [ ] Resolution failure leaves the operation pending without a successful receipt, satisfying AC-002.
- [ ] Retry resolves the existing rationale thread without another rationale comment, satisfying AC-003.
- [ ] Verification rejects unresolved matching rationale threads, satisfying AC-004.
- [ ] Only threads matched to current pending rationale operations are resolved, satisfying AC-005.

## Verification

| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `python -m py_compile skills/afk/review/scripts/forge_ledger.py` | rationale ledger parses |
| unit | `python -m pytest -q scripts/tests/test_rationale_ledger.py` | post, retry, failure, and verification behavior |

## Context excerpts

> (PRD Acceptance Criteria) "AC-001: A newly posted inline rationale comment is resolved before its batch receipt is posted."
>
> (PRD Acceptance Criteria) "AC-002: A resolution failure leaves the rationale operation pending and posts no successful batch receipt."
>
> (PRD Acceptance Criteria) "AC-003: A retry resolves the existing rationale thread without posting a duplicate rationale comment."
>
> (PRD Acceptance Criteria) "AC-004: Verification rejects an unresolved rationale thread even when its marker and receipt otherwise match."
>
> (PRD Acceptance Criteria) "AC-005: Resolution applies only to threads matched to the current pending rationale operations."

## Parent PRD

../PRD.md

## Parent SDD

(none — uncited mode)

## Blocked by

(none)
