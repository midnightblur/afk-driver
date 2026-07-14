# resilience — integration points, load shape, failure stories

Design-level. Default `class: design`; escalate to `class: correctness` (severity `high`) when a concrete failure scenario is demonstrable on a reachable path (name the scenario). Repo-pattern overrides → `pattern-debt` per PRECEDENCE.md. Every new out-of-process touchpoint in the diff is a suspect.
**Not yours:** single-process logic bugs → `logic-correctness`; transaction boundaries → `domain-alignment`; error *contract shape* → `api-contract`.

## Reviewer checklist

Integration points:
- **Naked integration point** (Nygard) — new out-of-process call (HTTP client, JMS, DB, RFC, file share) with no explicit connect **and** read timeout → set both explicitly; a library default is not a decision.
- **No failure story** (Nygard) — new remote call whose failure propagates as an unhandled 500 or a half-done state → decide retry / fallback / park / surface, visibly in code.
- **SLA inversion** (Nygard) — critical path takes a new hard dependency on a lower-availability system → degrade gracefully or go async.

Load shape:
- **Unbounded result set** (Nygard) — new query, `findAll`, or collection load sized by production data with no page/limit → bound it.
- **N+1 remote / lazy-load loop** (Nygard, PoEAA) — remote call or lazy association access inside a loop over a data-sized collection → batch endpoint, fetch-join, or one bulk query.
- **Blocked request thread** (Nygard) — new blocking wait (`.get()` without timeout, sleep, coarse lock) on a request path → time-box the wait or move off the request thread.
- **Dogpile** (Nygard) — identical cron across instances, cache entries expiring together, retries without jitter/backoff → stagger, jitter, back off.

State & retries:
- **Dual write** (Newman) — one flow writes the DB and emits a message / writes a second store, no outbox or compensation → outbox pattern, or single write + derive.
- **Non-idempotent retryable** (Newman) — new consumer/webhook/scheduled handler that double-applies on redelivery → idempotency key or a naturally idempotent write.
- **Unbounded growth** (Nygard) — new log stream, table, cache, or queue that only grows — no TTL/purge/rotation story → declare the cleanup.
- **Fail slow** (Nygard) — validation after expensive work; accepting work it can't finish → fail fast at entry.

## Guardrails (design-time digest)

- Every out-of-process call: explicit connect+read timeout and a named failure story.
- Every query over production-sized data: bounded or paged.
- No remote calls in loops — batch.
- Retryable handlers are idempotent; DB-write + message-emit needs an outbox.
- Whatever grows must also shrink (TTL, purge, rotation).
- Validate before spending resources.
