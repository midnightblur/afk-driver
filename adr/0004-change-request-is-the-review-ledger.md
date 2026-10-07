# ADR-0004 — The change request is the review ledger

> Status: Accepted
> Date: 2026-09-28

## Context

The review loop recorded gate state in `plan/review/`. A restarted session also needed the forge threads. The two records could disagree. A feature gate could then accept stale local state or lose a decision made on the change.

## Decision

The forge change is the only review record. Every finding is posted at its exact diff location when possible. Immutable marker records capture disputes, verdicts, fixes, verification, deferral, debt disposition, and location changes. Immutable summary notes capture round history.

Every gate decision reconstructs this record from the forge. `plan/review/` remains telemetry for reports, retro, and mission-control. No gate reads it.

The shared protocol lives in `skills/afk/review/SETTLEMENT.md`. Its parser and emitter live in `skills/afk/review/scripts/forge_ledger.py`. Forge adapters expose provider-neutral comment, note, thread, and change metadata shapes.

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| Keep local outcomes authoritative | A new checkout or deleted run artifact loses the gate state. |
| Mirror forge state into a manifest | Two authoritative copies can drift and require reconciliation. |
| Parse human prose | Wording is not a stable protocol. |
| Edit one managed summary note | Cross-identity resumes need write access to another author's note and erase history. |

## Consequences

- A resumed loop needs only the change and an explicit trusted-writer set.
- Exact inline locations and all historical threads become closure conditions.
- Cross-fork changes remain review-only because the adapter does not model a writable source target.
- Edited marker comments fail closed. Humans can delete or explicitly reclassify them.
- Local review files remain useful telemetry, but they cannot approve shipment.
