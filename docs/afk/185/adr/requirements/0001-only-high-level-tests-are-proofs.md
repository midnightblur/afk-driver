# Only high-level tests are proofs, and they gate the ship once

> Layer: Requirements
> Context ticket: 185

A proof is the result of a high-level test (API, UI end to end, acceptance) on a surface a user meets. High-level tests are planned ahead, written in their own subtasks, and run once at the end of the chain, as the ship gate. Low-level tests (unit, integration, contract) gate each subtask and are not proofs. High-level tests are expensive and slow, so they run as rarely as possible, and they prove the feature works as a whole; a proof per subtask was too heavy.

## Considered Options

- A proof per subtask, with an agreed lower level when a hands-off run cannot reach it. Rejected by the developer in i-park6 and i-tiers8, because a proof per subtask is too heavy and the intent is one proof that the feature works as a whole.
- One rule for all tests, "the highest level closest to the user" (round 1). Superseded in i-terms6: it conflicts with placing each test at the lowest level that sees its outcome for real.
