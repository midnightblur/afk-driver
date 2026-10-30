# ADR-0003 — Jira through the ported v1 REST client, no acli

> Status: Accepted
> Date: 2026-10-29
> Layer: L2
> Context ticket: GitHub #153

## Context

Decision 40 of issue #153 named acli. The publish the owner chose (whole PRD with diagram pictures) needs picture upload; acli's attachment commands are only list and delete (Atlassian command reference; request CLOUD-12967). The v1 REST client already does rich text and pictures (INV-002; SDD §3).

## Decision

Every Jira call goes through the ported v1 REST client, wrapped in the afkv2 answer envelope; create, transition and comment are removed; credentials are looked up as v1 does. No acli in P0. Owner, R-2: "rest | no acli at all then. JIRA is working just perfectly in v1, let's not change that".

```mermaid
flowchart LR
  P["to-prd publish"] -->|"verbs, JSON"| T["tracker port"]
  T -->|"REST v3, API token"| J["Jira Cloud"]
```

## Alternatives Considered

| Alternative | Pros | Cons | Reason rejected |
|-------------|------|------|-----------------|
| acli for everything | one login (acli) | no picture upload | breaks the owner's Y-1 |
| acli plus REST for pictures | keeps decision 40 | 2 logins, 2 clients | the token is needed anyway |
| acli only, no pictures | one client | reverses Y-1 | owner chose pictures |

## Consequences

- **Positive** — one credential, one client, proven paths.
- **Negative** — decision 40 changes; issue #153 still names acli.
- **Follow-ups** — none in P0.
