# ADR-0004 — Phase-label transition recovery: verify-after-write retry 3× + abort

> Status: Accepted
> Date: 2026-05-10
> Layer: L4 (cross-cutting / idempotency)
> Context ticket: github-backend (tasks folder)

## Context

ADR-0002 settled that phases are mutually-exclusive labels mutated via `gh issue edit --remove-label … --add-label …`. The REST surface underneath applies remove-then-add as separate operations; if the remove succeeds and the add fails, the issue ends with **zero** `afk:*` labels — invisible to the next queue scan. Symmetrically, a duplicate concurrent caller could leave **two** labels. SDD §5 (Idempotency table) and §6 (Invariants) both depend on the recovery posture for this.

Forces:

- Phase mismatch is a silent-failure mode; the runner must not advance to next sub-issue while a prior transition is in an undefined state.
- AFK runs unattended overnight; failures must be self-recovering or fail loud.
- A GraphQL atomic mutation exists in principle (single mutation that adds + removes labels) but adds GraphQL plumbing for one operation.
- The cost of a verification read is one extra REST call per transition (~4 transitions per sub-issue × ~20 sub-issues/run = 80 extra calls — well within budget).

## Decision

Every phase transition writes via the single `gh issue edit` call, then immediately reads back with `gh issue view --json labels` and asserts the result. On mismatch, the operation is retried up to **3 times** total (initial attempt + 2 retries) with backoff `0 / 200 / 600 ms`. If the third attempt still mismatches, the runner posts an abort comment on the sub-issue, transitions the parent's run state to "this parent halted", and continues to the next parent. The pre-flight sweeper (ADR-0005) catches any leftover mis-labeled issues at the start of the next run.

```mermaid
sequenceDiagram
  participant runner
  participant client as github_issues_client
  participant gh as gh CLI
  participant api as GitHub REST

  runner->>client: transition_phase(N, target=afk:developing)
  loop attempt 1..3
    client->>gh: gh issue edit N --remove-label A,B,C --add-label W
    gh->>api: PATCH labels
    api-->>gh: 200 (or error)
    client->>gh: gh issue view N --json labels
    gh->>api: GET issue
    api-->>gh: {labels: [...]}
    alt labels == {target}
      client-->>runner: ok
    else mismatch
      Note over client: backoff (0 / 200 / 600 ms)
    end
  end
  alt attempts exhausted
    client->>gh: gh issue comment N --body "AFK: phase transition failed; aborting"
    client-->>runner: PhaseTransitionError
  end
```

*Caption: every transition is a write+verify pair; up to 3 attempts, then an abort comment.*

## Alternatives Considered

| Alternative | Pros | Cons | Reason rejected |
|-------------|------|------|-----------------|
| **A — Best-effort + digest warning** | Cheapest; fewest API calls | Silent drops possible; sub-issue can become invisible; runner advances on false success | Violates "AFK never silently drops work" |
| **B (chosen) — Verify-after-write retry 3× + abort + sweeper** | Catches partial-write; bounded retry cost; clear abort signal | Extra read per transition (~80 calls/run); requires sweeper at next run start | Trade-off accepted; recovery is mechanical and observable |
| **C — Pre-flight reconciliation only** | Single sweep at run start | Mid-run drift not corrected until next run; affects parents in flight | Insufficient for in-flight safety |
| **D — GraphQL atomic mutation** | True atomicity at API level | Introduces GraphQL plumbing for one op; `gh api graphql` syntax is non-trivial; still requires retry on transient 5xx | Cost > benefit at AFK scale |

## Consequences

- **Positive** — Phase mismatches are caught within seconds, not next morning. Abort path leaves a clear audit trail (comment) on the sub-issue. Recovery is fully mechanical (sweeper at next run start). The verify cost is bounded and well within rate budget.
- **Negative** — Retry logic increases per-transition wall-clock (worst case ~1.4 s for two backoff waits). A pathological GitHub outage could make every transition trip the abort path, halting many parents in succession. The retry budget is fixed (3); rare environments with chronic 5xx will see false aborts.
- **Follow-ups** — Out of scope: a circuit breaker that halts the whole run after N consecutive transition failures (mid-run "GitHub is broken" detection). Out of scope: GraphQL atomic mutation as an upgrade path (ADR-0002 Alternative D in the architect-grill notes).
