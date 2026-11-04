# gc removes the run branch and keeps no record of the run

> Layer: Requirements
> Context ticket: 158

The run branch holds the plan, the journal, the decision ledger and the review telemetry. It is an orphan, so the merge of the feature carries none of these files, and removing the branch removes them for good. An earlier decision (requirements grill of 2026-10-29) kept the run branch as the run's record for a later retro. The developer reversed it: gc removes the run branch and keeps no record. Retro, deferred to 2.1, has no data for any work that gc cleaned.

## Considered Options

- Remove the branch, keep the record under a hidden ref that the branch list does not show. Rejected by the developer in i-record, because no record is needed.
- Keep the branch, as decided before. Rejected by the developer in i-record, because the leftover branches are the pain this ticket removes.
