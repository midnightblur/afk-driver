# One consent rule for code, tickets and merge requests

> Status: Accepted
> Audited: 2026-10-13
> Layer: Requirements
> Context ticket: small-lane

Before `/afk:fix` changes anything, the caller approves the fix proposal. One approval covers the code change, the ticket writes and the merge request. A prior approval, which is an explicit instruction or approval given earlier, stands in for asking. Starting a hands-off run is a prior approval. An agent caller approves under `DECISIONS.md`, and stops for the human when the change is not easy to undo or no option is a clear winner. The fix never approves itself. With one rule, code and tickets cannot drift into different consent models, and a hands-off run does not stall at each ticket write.

The rule that a hands-off run counts as prior approval was decided by the agent and accepted by the human on 2026-10-13.

## Consequences

- This replaces the earlier rule that a tracker write needs a human present: a write under a prior approval that covers ticket writes is allowed.
