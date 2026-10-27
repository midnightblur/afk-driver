# Allow solo-owner attestation

> Status: Accepted
> Audited: 2026-10-19
> Layer: Requirements
> Context ticket: P2P-2067

A sole human owner can explicitly attest a single-service term through an interactive AFK prompt that shows the exact terms, hashes, fingerprints, and source commit. Only an explicit final or reject answer counts; an agent answer or free text does not. The record states that the forge cannot prove the human supplied the answer because the agent publishes with the same credentials.

## Considered Options

- Require another maintainer or product-domain owner for every approval.
- Permit a narrow solo-owner exception with an explicit trust limit.

## Consequences

Cross-service terms still require every affected owner. Hands-off and driven work park without a timeout until the human responds with final or reject.
