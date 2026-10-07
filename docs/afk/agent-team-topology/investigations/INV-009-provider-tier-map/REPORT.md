C:\Users\mvu\PersonalProjects\afk-driver-agent-teams@7e9c87a · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-009-provider-tier-map/COVERAGE.json

## Answer

The model-tier map has one home, the `## Model tiers` table at PROVIDERS.md:51-60, and no code parses it. One equivalence rule sentence there ("the same tier row in another harness column is equivalent, for substitution on a provider failure") trips no gate: native-contract-gate check A excludes PROVIDERS.md. Two lines change under the settled design (S-99).

## Sites that change or break

- PROVIDERS.md:53 — breaks. The in-harness fallback ("first available model in the column, else the nearest capability-compatible model") and the new cross-harness rule need a stated order. The rule keys on the tier row, because rows :57-60 name more than one model per cell. Unguarded.
- DELEGATION.md:50 — breaks under S-99. "Callers override per-spawn — always upward" forbids a human-written pattern that sets a role below its tier; the line gains the carve-out, and agents stay upward-only. Unguarded.
- agents/*.md `model:` and providers/codex/agents/*.toml `model` / `model_reasoning_effort` — restate the columns by hand. Unchanged by a rule sentence; no gate or test checks them. Unguarded.

## For the design

- DELEGATION.md:45 ("A judge is never a cheaper model than the implementor it judges") and DELEGATION.md:49 ("Plugin/harness work is always frontier") are absolute. A human pattern that sets a judge role or a plugin-editing role below its tier contradicts them unless the carve-out names them (claim c-e7c1180e, inference). The ledger judged both lines against the equivalence facet only, so they read `unchanged`.
- DELEGATION.md:46 and skills/afk/autopilot/SKILL.md:35 point at a PROVIDERS.md "Pin delivery" heading that does not exist.
- Claim c-42dba1c5 ("override direction not stated") is superseded by S-99; the merge keeps it by id.

## Frontier

B14: installed plugin copies and other repositories that restate the tier map.

## Unverified

One claim, not load-bearing (c-7a676672): the hit set is complete over the tier name forms searched; no case-blind pass ran.
