nakisainc/core/core-services@fe27ed571348f12ecf5b3ea3633fe50582c26f79 · closed-with-frontier · boundaries 13/14 · unverified 0 (load-bearing 0) · ledger: 11700-payable/specs/2026r2/P2P-2067/investigations/INV-004-forge-record-seam/COVERAGE.json

## Answer
The referee reconstructs the change record before each stateful action. It reads plain notes and inline threads, then normalizes them into one ordered entry set.

Each finding starts at sequence 1. Each outcome or location update becomes a new thread reply or plain note. The record includes a sequence number and an operation ID that binds the prior sequence.

Reconstruction accepts marker-bearing entries only when the forge reports `edited: false` and the author is trusted. It rejects missing edit metadata, edited markers, unclassified authors, malformed markers, orphan records, sequence gaps, invalid operation IDs, illegal transitions, and conflicting duplicate content.

GitHub posts plain notes through the issue-comment API and inline notes through the review-comment API. It joins REST data with GraphQL edit and resolution data. GitLab posts positioned discussions, verifies the result is a `DiffNote`, and can delete a degraded plain note when inline placement is required. GitLab uses `lastEditedBy`; a hidden author and editor is an error.

A deleted finding origin is detectable when records remain. A deleted middle record is detectable as a sequence gap.

Inference: deleting the newest record can silently roll the state back. Reconstruction computes the expected sequence only from records that remain, so no later record proves the deleted tail existed.

The focused tests passed: 234 tests in `scripts/tests/test_forge_ledger.py` and `scripts/tests/test_forge_adapters.py`.

## Sites
- `skills/afk/review/scripts/forge_ledger.py:158` — finding marker emission.
- `skills/afk/review/scripts/forge_ledger.py:184` — record marker emission and operation ID.
- `skills/afk/review/scripts/forge_ledger.py:611` — author and edit screening.
- `skills/afk/review/scripts/forge_ledger.py:829` — reconstruction entry point.
- `skills/afk/review/scripts/forge_ledger.py:856` — orphan-record rejection.
- `skills/afk/review/scripts/forge_ledger.py:870` — sequence and operation validation.
- `skills/afk/review/scripts/forge_ledger.py:1012` — plain or inline publication.
- `skills/afk/review/scripts/forge_ledger.py:1021` — append operation.
- `hooks/lib/adapter.sh:29` — configured provider selection.
- `adapters/forge/github/CONTRACT.md:51` — GitHub publication and read model.
- `adapters/forge/gitlab/CONTRACT.md:48` — GitLab publication and read model.
- `scripts/tests/test_forge_ledger.py:315` — corruption and sequence tests.
- `scripts/tests/test_forge_adapters.py:942` — provider edit metadata tests.

## Unverified
- None.

## Frontier
- Live GitHub and GitLab API behavior was not queried. The provider tests use stub command-line tools.
