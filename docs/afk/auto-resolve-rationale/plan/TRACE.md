# Trace matrix

Harness sync: no AGENTS.md change. `RATIONALE.md` owns the behavior, so another instruction would duplicate it.

Staples: no-op. The PRD names no candidate, and the repository has no staples registry.

| Criterion (verbatim) | Subtask | Commits | Proven by |
|---|---|---|---|
| AC-001: A newly posted inline rationale comment is resolved before its batch receipt is posted. | 0001-resolve-rationale-threads | `27c658e` | `scripts/tests/test_rationale_ledger.py::test_post_opens_a_draft_for_the_pushed_branch_and_writes_receipt` |
| AC-002: A resolution failure leaves the rationale operation pending and posts no successful batch receipt. | 0001-resolve-rationale-threads | `27c658e` | `scripts/tests/test_rationale_ledger.py::test_post_retries_resolution_without_posting_a_duplicate_comment` |
| AC-003: A retry resolves the existing rationale thread without posting a duplicate rationale comment. | 0001-resolve-rationale-threads | `27c658e` | `scripts/tests/test_rationale_ledger.py::test_post_retries_resolution_without_posting_a_duplicate_comment` |
| AC-004: Verification rejects an unresolved rationale thread even when its marker and receipt otherwise match. | 0001-resolve-rationale-threads | `27c658e` | `scripts/tests/test_rationale_ledger.py::test_verify_rejects_an_unresolved_thread_with_a_valid_receipt` |
| AC-005: Resolution applies only to threads matched to the current pending rationale operations. | 0001-resolve-rationale-threads | `27c658e` | `scripts/tests/test_rationale_ledger.py::test_post_does_not_resolve_an_unrelated_review_thread` |
