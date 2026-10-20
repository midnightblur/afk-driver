# The fix runs in the current session

> Status: Accepted
> Audited: 2026-10-13
> Layer: Requirements
> Context ticket: small-lane

`/afk:fix` runs in the session that called it. The background fixer, the rule that only one fix runs at a time, the local merge of a fix branch for re-test and the push notifications all go. The notifications served only the background fixer. A fix in the current session keeps the caller in charge of approval and of the merge request.

Removing the local merge and the notifications was decided by the agent and accepted by the human on 2026-10-13.
