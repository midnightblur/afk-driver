# Split definition and audit history

> Status: Accepted
> Audited: 2026-10-19
> Layer: Requirements
> Context ticket: P2P-2067

Git records glossary definition changes. Append-only merge request comments record audit and reconciliation results. The repository does not keep a rebuild directory or receipt archive.

Validation detects comment edits and deletions inside the retained record sequence. It cannot prove deletion of the complete newest suffix because the remaining comments form an older valid prefix. This forge limitation is accepted.

## Considered Options

- Commit generated receipts and reconciliation reports.
- Use Git for definitions and the merge request for delivery evidence.
- Add provider audit-event reads to prove deletion of the newest comment suffix.
