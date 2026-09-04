# SETTLEMENT.md — the review gate's settle loop

One home for the caller-side protocol a gate follows when gating on review findings. The **review pass** — `/afk:review` for AFK gates; a caller outside the AFK chain may supply its own pass honouring the same findings contract and delta-round rules (`/afk:review`'s SKILL.md owns both) — stays read-only and single-shot: one invocation, one report; looping, remediation, disputes, and termination belong to the caller. Callers point here; this file names no caller. The loop: review → remediate → review until **nothing actionable remains** — every finding either **fixed** or **settled** (withdrawn after a dispute judged on merit).

## Roles

- **Implementor** — whoever owns the diff at the gate (the executing session and the fixer subagents it routes to). Fixes or disputes findings.
- **Reviewer side** — per round, a fresh review-pass fan-out; per dispute, a fresh adjudicator subagent. Never persistent across rounds; never handed prior-round reasoning.
- **Referee** — the gate orchestrator (the session running the caller skill). Keeps the round ledger, applies termination, and keeps that accounting out of every subagent prompt (Information diet below).

## The round

1. **Review.** Run the review pass tagged `r{n}` (`n` = this round, referee-private) — for AFK gates, `/afk:review {args} --tag r{n}`. Round 1 reviews the caller's full unit (slice or feature diff). Round n≥2 passes `--base {tip reviewed in round n-1}` (from the ledger) so fresh reviewers focus on what changed since the last review — the delta-round rules keep the full diff and repo visible as context and scale the reviewer roster down.
2. **Filter to the actionable set.** Drop `pattern-debt` and `product-debt` (neither gates; `product-debt` still owes a home — `/afk:review` "Product-debt homes"). Apply the caller's deferral rule when one is declared ("Deferral rule" below) — matching findings leave the set, recorded `deferred` in this round's outcomes file. Drop findings already `settled` in the ledger — fresh reviewers will re-surface settled findings; match by criterion + file + substance (line numbers shift across fixes) and don't re-open one unless the new finding carries material evidence the adjudicated dispute lacked.
3. **Zero actionable findings → the gate settles.** Exit the loop; pass.
4. **Fix or dispute — every finding, every severity.** For each actionable finding the implementor either **fixes** it (routed by `class` per the caller's routing table) or **disputes** it with a written, evidence-cited rationale: a spec/contract citation, a documented repo pattern, or a constraint the reviewer missed. Medium/low are not exempt — a nit not worth fixing is worth one dispute sentence; "not worth it" without evidence is not a rationale. A fix that introduces new behaviour — a new method, new transactional/compensation semantics, new failure handling — is a **design change, not a patch**: enumerate its failure modes first (each single failure, compound failures, early returns, ordering) and pin each with a test in the same fix commit; review rounds catch defects, they must not incrementally design the feature. The carve-out sizes the fix, never the finding: a finding naming an **observable runtime failure** — a 5xx, a leaked internal, a broken idempotency promise — is not settled by the fix being large. Route it to the adversarial gate’s remediation path so it is proved against the running app, and record it as an open advisory only if that gate agrees it cannot fire. Convergence across independent reviewers raises the bar for settling; it does not lower it.
5. **Adjudicate disputes.** One fresh subagent per disputed finding, all spawned in a single parallel message. Each gets: the finding (verbatim JSON), the implementor's rationale, the diff path, and the contract/spec + CLAUDE.md-chain paths — nothing more (Information diet). Brief: judge the rationale on its merits — `withdrawn(<reason>)` if it holds, `stands(<reason>)` if not.
6. **Apply verdicts.** `withdrawn` → mark the finding `settled(<reason>)` in the ledger. `stands` → the finding must be fixed before the loop can settle; no re-dispute without evidence absent from the first rationale. A stands-finding that can't be fixed within the caller's boundaries (e.g. Scope) → the caller's blocked/park path, not a settlement.
7. **Close the round.** Commit fixes per the caller's commit rules, then run only the caller's **cheap re-verification** (the caller defines it — compile/static plus the local tests covering the changed code); expensive surfaces — live-app tiers, full builds, app provisioning — never run inside the loop, only once after it settles, per the caller's own steps. Write this round's outcomes file (`…-r{n}.outcomes.json`, grammar owned by `/afk:review`): `fixed` for fixes committed this round, `dismissed(settled: <adjudicator reason>)` for settlements, `deferred` for findings still open going into the next round or routed by the caller's deferral rule — at stalemate the final round's non-rule `deferred` entries are the human's worklist. Record this round's reviewed tip in the ledger (next round's `--base`), journal the round's verdict, then next round from 1. **Never state a round's verdict before that round reports.** A report, an `INDEX.md` cell, or a JOURNAL line covers only rounds whose sweep has already returned — so the referee's termination note belongs in the last report, never in the one before it. A verdict written ahead of its sweep falsifies the ledger, and the next round is spent on bookkeeping instead of code.

## Deferral rule (optional, caller-declared)

A caller may declare, before round 1, a rule routing a class of findings to a **named later gate** instead of settling them here — deferral is routing, never dropping. Matching findings leave every round's actionable set, recorded `deferred` in that round's outcomes file, and stay visible as open advisories in the review rollup. The later gate's round 1 **must sweep them back in**: read the earlier unit's `*.outcomes.json` files, take every finding whose *latest* outcome across that unit's rounds is `deferred`, resolve it against its findings file, and add the still-unfixed ones to its own actionable set. No declared rule → nothing defers.

## Termination (referee-only)

- **Settled** — a round's actionable set is empty: everything the loop surfaced is `fixed` or `settled`. The gate passes.
- **Ledger-only rounds do not extend the loop.** A round whose findings all target review artifacts or documentation — reports, `INDEX.md`, `PATTERN-DEBT.md`, JOURNAL lines, `CLAUDE.md` and spec files — and none target main or test code is remediated in place and closed as settled; it mints no further round. **The termination test governs and the list only illustrates:** the latest sweep raised no finding against main or test code. Without this a slice whose code has been stable for rounds keeps failing on its own bookkeeping.
- **Stalemate** — hard cap: **10 rounds**. Findings still open at the cap → the gate fails with the caller's stalemate outcome, naming the leftovers for a human (why the cap always escalates: plugin `GLOSSARY.md`, "Stalemate").

## Scope escalation — when delta review stops being enough

A delta round sees only the delta. One defect class is invisible to it by construction — **a fact corrected in one file and left standing in a sibling** — because the sibling sits outside the delta.

Trigger: **two consecutive rounds file a finding of that shape.** From the next round the loop is no longer delta-scoped. The referee passes the review pass `--scope-escalated`, and each reviewer reads the whole surface the feature touches: the component's code and its `CLAUDE.md`, the specs and ADRs stating the same facts, the review records the loop has written, and the cross-service consumers of anything the feature publishes.

That escalation adds one reviewer, `consistency-sweep`: take every finding an earlier round recorded `fixed` and search that whole surface for an uncorrected copy of the same claim. It is the only reviewer positioned to close the class, and it cannot be a delta reviewer.

Widening raises each round's cost. A loop re-finding the same shape every round is already paying more.

## What the cap means

The cap **parks**; it does not conclude. Parking says a human must look, not that the feature is unsound. Two situations reach the cap and they need different decisions, so the park report states, before parking:

1. whether any finding in the last two rounds carried `blocks_ship: true`, and
2. when the shipped code last changed.

A loop whose own records became its review surface — no `blocks_ship` findings, code untouched for several rounds — has stopped converging on the feature and started converging on itself. That is a scope problem ("Scope escalation" above), and the human's likely call is to widen and continue. A loop still finding real defects in the diff at the cap is the opposite situation, and the same park reason would mislead.

## Information diet (hard rule)

The termination rules exist for the referee alone. No subagent prompt — reviewer, adjudicator, or fixer — ever contains the round number, the round cap, the settled ledger, or the fact that agreement/withdrawal ends the loop. A reviewer that knows it's round 9 of 10 reviews the clock, not the code; an adjudicator that knows `withdrawn` terminates the loop is being handed the ending, not the dispute. The referee's accounting lives only in its own context and the artifacts under `plan/review/`.
