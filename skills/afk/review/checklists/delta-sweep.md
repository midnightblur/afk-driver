# delta-sweep — remediation-delta regression review (delta rounds only)

The consolidated implementation reviewer for a settle-loop delta round — the full-roster always-set's highest-yield items at remediation-delta altitude. Not one of the 11 concerns; spawned only on delta rounds (SKILL.md "Delta-round roster"). Reviews the delta cold: no finding history, no round context. Each item below names its `class`; stamp `concern: delta-sweep`, `criterion` = the item name. Baseline items follow PRECEDENCE.md; when the orchestrator's prompt names co-spawned specialist concerns, their territory is theirs — skip it (one owner).
**Not yours (always):** whole-unit altitude — acceptance completeness, module shape, domain vocabulary, resilience of pre-existing touchpoints, API-surface coherence — full-unit-round and specialist territory.

## Reviewer checklist

- **New defect in the change** (`class: correctness`) — inverted or incomplete condition, dropped error path, null slip, off-by-one, leaked resource in the changed lines; a fix applied at one site while a sibling path keeps the old behaviour.
- **Propagation gap** (`class: correctness`) — the change edits a shared symbol, signature, or util without updating all direct callers — grep the repo, cite the missed caller.
- **Behaviour narrowed to dodge** (`class: spec`, severity `high`) — the change silences a symptom instead of fixing the cause: feature short-circuited, input rejected, case dropped, output special-cased.
- **Test weakened to pass** (`class: test`, severity `high`) — assertion deleted or loosened, test disabled/skipped, expected value updated to match broken output, tolerance widened.
- **New test proves nothing** (`class: test`) — an added test that cannot fail for the behaviour it names: tautological, asserts the DTO not the framework's real output, happy-path-only where the change is about the edge.
- **Documented-rule breach in changed lines** (`class: compliance`) — the changed hunks violate an applicable CLAUDE.md-chain / rules / glossary rule you can quote.
- **Unrelated churn riding the change** (`class: scope`) — reformat, rename, or refactor of lines the remediation didn't need to touch.
- **Smell introduced by the change** (`class: smell`) — near-copy of an existing helper, copy-paste leaving a drifted twin, dead code, debug artifacts, ownerless TODO; hardcoded secret/config is `class: correctness`, severity `critical`.

Plus PRECEDENCE.md's open-question slot, scoped to the delta.
