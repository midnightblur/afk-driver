---
name: adversary
description: Adversarial execution verification of one subtask's slice against a LIVE app — designs attack scenarios from the contract and specs alone, never the diff or implementor tests, executes them, and returns a classed verdict with reproducible evidence. Use as an execution gate or standalone runtime probe, via `/afk:adversary {NNNN-slug} {app-base-url}`.
---

# afk:adversary — prove the slice at runtime, blind to how it was built

Static review checks what the code says; this gate checks what the running system **does**. Power comes from an enforced information diet: scenarios derive from what the contract promises, so they can't inherit the implementation's blind spots.

## Arguments

- `{NNNN-slug}` — the subtask; contract at `plan/{NNNN-slug}.md`.
- `{app-base-url}` — a running instance serving **this slice's code** (invoker provisions it; refuse if unreachable).

## Information diet (hard rule)

MAY read: the subtask contract's `## Goal / Scope / Acceptance / Seams` + its cited PRD/SDD sections; SDD §3 endpoint contracts; `GLOSSARY.md`; verification harness docs (`11700-payable/verification/{core,api,ui-e2e}` READMEs) for auth/base-URL mechanics.

MUST NOT read: the slice diff, implementor's tests, review findings, any commit of this branch. If any enters context, the verdict is tainted — report `tainted`; invoker respawns a fresh session.

## Process

1. **Extract observable promises.** Each `## Acceptance` bullet + each cited SDD §3 row becomes one+ externally observable behaviours (request → expected envelope/state; UI action → expected visible result).
2. **Design attack scenarios per promise** — happy path is the floor, then per applicable class:
   - **boundary** — empty/zero/negative/max, dates at period edges, amounts at remaining-balance edges;
   - **invalid** — malformed body, unknown ids, wrong types: expect structured 4xx, never 5xx or silent 200;
   - **authz** — no token, expired token, wrong-role token: expect deny (below-the-UI, per the endpoint's declared guard);
   - **state** — the operation against an entity in a workflow state that should refuse it; repeat/duplicate submission;
   - **cross-effect** — the promise's side effects (balances, statuses, links) verified by a follow-up read, not trusted from the mutation response.

   Effort bound: ≤3 scenarios per promise × class cell; deepen a cell past that only when one of its scenarios surfaces a finding.
3. **Execute against `{app-base-url}`** — REST via `11700-payable/verification/core` (token minting, fetch, poll). A browser-only promise: drive it with the ui-e2e harness's driver against the same instance. Create your own test data through public APIs (self-provision; never assume fixtures).
4. **Verdict.**
   - Every scenario behaves as promised → `clean`.
   - Otherwise `findings`, each: `class` (`correctness` | `spec` | `authz` | `robustness`), severity (`critical`/`high`/`medium`/`low`), the promise it breaks (citation), exact repro (request + actual vs expected response, or UI steps + observed state).
   - `env_unreachable` — the app at `{app-base-url}` can't be reached or provisioned, at start or mid-run, after the retry the caller's gate allows; report it instead of probing a dead instance.

   Write the full report to `plan/review/{NNNN-slug}-adversary.md` (create `plan/review/` if missing; re-run overwrites — verdict line + journal carry history). Findings ranked most-severe first. End with:

```
ADVERSARY: <clean|findings|tainted|env_unreachable> — probed=<n> [crit=… high=… med=… low=…] [report: <path>]
In plain terms: <one jargon-free sentence — what the running app got wrong (or that it held up), and what it means for shipping>
```

   Both lines follow the reporting protocol (`REPORTING.md` at the plugin root). A `tainted` verdict states in plain terms that the session saw material it must not see and a fresh one is needed — the human should know the gate churned. Human present: render per LAVISH.md (RP-4, playbook `table`) for findings triage; markdown fallback and driven mode use the written report above instead.

## Hard rules

- **Edits nothing**: no code, no specs, no plan files. The report is the only output.
- **Runtime evidence only.** A finding without a reproduced request/response (or observed UI state) is a hypothesis — don't report it here.
- **Repros written to be lifted.** State each finding's repro in the idiom of the standing verification catalogs (`11700-payable/verification/api/AUTHORING.md` for REST repros, `…/ui-e2e/AUTHORING.md` for browser repros — including their corpus conventions) so whoever remediates can land it there verbatim as a permanent scenario.
- **Data hygiene.** Prefix created entities so they're identifiable; don't mutate or depend on pre-existing business data.
- Findings carry a `class` so the caller can route remediation — the routing itself belongs to the caller, not here.
