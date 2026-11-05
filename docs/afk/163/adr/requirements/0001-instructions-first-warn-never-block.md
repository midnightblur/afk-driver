# Instructions carry the quality bar; engine logic only warns, and never blocks

> Layer: Requirements
> Context ticket: #163

The owner ruled "instructions only. No engine checks or guardrails to force this", and a later steer refined it: deterministic logic is allowed for a critical or irreversible outcome, if it never blocks. So the page rules and the answer rules are instructions with no engine check. Engine changes that give a page a new ability are allowed, and the only deterministic logic is a warning (a secret on a tracked page, a page git does not track).

## Considered Options

- No engine change at all. Rejected by the owner in i-ruling, because the answer link becomes words and an ad-hoc page must pretend to be a grill session.
- Engine checks that force the rules. Rejected by the owner in the round 2 steer, because checks create friction and blockers that smarter models no longer need.
