# No diagnosis step for a bug inside a bigger job

> Layer: Requirements
> Context ticket: small-lane

A feature build can hit many defects: a check still red after its retry, a review finding, an adversary finding, a red smoke gate. A diagnosis for each one costs time and tokens that the run cannot spare. So inside a bigger job, the agent fixes in place with no diagnosis step and approves under `DECISIONS.md`. The regression test, the tiers, escape analysis and the workflow lesson still run. A finding the agent thinks is wrong is disputed in the settle loop. An in-place fix returns today's outcomes and no diagnosis verdict.

## Considered Options

- A light diagnosis for every defect in a bigger job: rejected for its cost.
- A full diagnosis for every defect: rejected for its cost.

## Consequences

- A bug that a human reports while testing the feature branch is not covered by this rule: it gets a full diagnosis, and that human approves the fix.
- A defect outside the slice is not covered by this rule (ADR-0005).
