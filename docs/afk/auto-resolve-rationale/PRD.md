## Problem Statement

Inline rationale comments remain open after the plugin posts them. Reviewers can mistake these informational comments for unresolved code-review work.

## Solution

The rationale writer resolves each rationale thread before it records the batch receipt. Retries resolve an existing rationale thread without posting a duplicate.

## User Stories

1. As a reviewer, I want rationale threads resolved automatically, so that open threads represent review work that needs action.
2. As a plugin operator, I want failed resolution attempts to retry safely without duplicate comments.

## Acceptance Criteria

- [ ] AC-001: A newly posted inline rationale comment is resolved before its batch receipt is posted.
- [ ] AC-002: A resolution failure leaves the rationale operation pending and posts no successful batch receipt.
- [ ] AC-003: A retry resolves the existing rationale thread without posting a duplicate rationale comment.
- [ ] AC-004: Verification rejects an unresolved rationale thread even when its marker and receipt otherwise match.
- [ ] AC-005: Resolution applies only to threads matched to the current pending rationale operations.

## Access & validation policy

| Capability / User Story | Permitted role(s) | Denied role(s) | Data scope | Key validation rules |
|-------------------------|-------------------|----------------|------------|----------------------|
| Post and resolve rationale | Everyone may use an enabled plugin | none | Current change and branch | Match the immutable rationale marker to the pending operation |

## Implementation Decisions

| Module | Responsibility |
|--------|----------------|
| Rationale ledger | Retain or recover the thread identifier, resolve the thread, and gate the receipt on success |
| Forge adapters | Use the existing `thread-resolve` contract without changing its interface |
| Rationale tests | Cover new posts, failures, retries, and verification |

The change preserves the existing marker, receipt, command, and adapter-field grammar.

## Testing Decisions

Exercise the public rationale commands through the existing fake forge. Assert observable comments, thread state, receipts, pending operations, and exit results.

## Out of Scope

- Resolving review findings or unrelated inline threads.
- Changing the forge adapter interface.
- Changing rationale marker or receipt grammar.

## Further Notes

The repository investigation confirmed that both GitHub and GitLab adapters accept the thread identifier returned by `change-comment`. Live forge behavior remains unverified.
