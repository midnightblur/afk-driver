# No availability or quota check — react, never predict

> Status: Accepted
> Audited: 2026-09-17
> Layer: Requirements
> Context ticket: agent-team-topology

A run performs no availability or quota check before or during its work; a provider failure is detected when a call fails. The obvious alternative — check the provider first, then plan around what it reports — was rejected because the model whose quota is exhausted is the one that would have to run the check, and a usage limit resets on its own without anyone asking. Authentication is checked once per provider before the first spawn, because that failure does not resolve itself.

## Considered Options

- Predict: read each provider's remaining window and schedule around it. Rejected — an exhausted model cannot report its own exhaustion, and a confident wrong prediction is worse than none.
- Estimate a run's cost up front. Rejected in favour of reserving a fixed slice of each provider window for the contact agent, so the agent the human talks to can always answer and nothing has to be forecast.

## Consequences

Beyond a provider's wait horizon the run parks with a dated report rather than continuing in a reduced shape. A provider usage read was later proven free of cost by live trial; that changes nothing here, because nothing reads it.
