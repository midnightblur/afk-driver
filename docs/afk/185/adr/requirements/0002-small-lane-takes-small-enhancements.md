# The small lane takes small enhancements, not only bugs

> Layer: Requirements
> Context ticket: 185

The small lane takes any small change: a bug fix or a small new behavior. The v1 small-lane branch took bugs only (its ADR-0006) and sent every enhancement to the full chain. The motivating incident was a small enhancement: under the v1 rule it had no light path, so it got no path at all.

## Considered Options

- Enhancements always go to the medium lane, as in v1. Rejected by the developer in i-small-scope, because a 10-line enhancement would then need requirements, design and a plan.
