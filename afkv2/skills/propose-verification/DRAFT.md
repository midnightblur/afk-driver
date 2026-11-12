# Drafting a verification plan

The rules for each draft, each critique and the reconciled plan. The row fields and the refusals of `write`: [VERIFICATION-FORMAT.md](VERIFICATION-FORMAT.md).

## The draft

- Go from high to low. Per story: its user journeys (`ui-e2e`), its API scenarios (`api`), then the low-level rows.
- Give each user-visible acceptance criterion at least 1 active high-level row. List each criterion with no user-visible outcome under `internal`, with why.
- Give each row its highest-value level ([LEVELS.md](LEVELS.md)). Never pick a higher level for comfort, and never a lower level that cannot see the outcome.
- Name the data and the environment of each row. `then` is what you should see, so a judge can compare to it.
- List each service boundary that the change crosses. The repository has a contract test there: add or update an active `contract` row. It has none: propose a ticket to set one up, and keep an active `api` row or higher as the floor.

## The critique

Write what you would change in the other plan, and why, 1 point each. Flag at least:

- a row whose level is not its highest-value level;
- a test that repeats a cheaper test just as faithfully;
- a user-visible criterion with no high-level row;
- a boundary with no contract row, or with no ticket and no API floor;
- a row with no data, no environment, or a `then` a judge cannot compare to.

## The reconcile

A point that both critiques accept goes into the plan. Each other difference is 1 fork card (a `debate` item) with both sides. A row at a lower level than its highest-value level needs a `confirm` card that the developer settles with an `accept` mark; its status is then `lower: <from> to <to> · <card id>`.
