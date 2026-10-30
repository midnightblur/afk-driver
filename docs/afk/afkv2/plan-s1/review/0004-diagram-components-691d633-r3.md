# Review of 0004-diagram-components, round 3

Telemetry only. The review record is pull request 155.

policy: lean · activated: delta-sweep, logic-correctness (owner of the fixed high finding), test-veracity (the change touches tests) · skipped: spec-fidelity, scope-and-impact, refactor-safety (no trigger in this delta) · deferred: agents-md-compliance, code-quality, design-quality, resilience (→ feature gate)
verified: no design-level finding, so no verify pass ran. Caller set: no pre-existing public symbol changed, so no coverage ledger exists.

Diff 691d6334..4fbcfecd.

Verdict: advisory, 0/0/4/1 (critical/high/medium/low). Under owner ruling R-2 these findings stay on the pull request with no fix and no dispute round, and the gate passes. The high finding of round 1 about a map held in a card stays open on the pull request, deferred to slice 0005 by orchestrator ruling D-43.

- r-001 medium compliance .claude/wiring-ious.md:13: The rewritten IOU row starts with a symbol and not with an artifact path, so `hooks/wiring-gate.sh` cannot see it and its final mode passes while the row is open.
- r-002 medium test afkv2/tests/engine/test_diagram_components.py:508: The `right` case of the taller-box test cannot fail, and no new test proves the straight first leg in direction right.
- r-003 medium test afkv2/tests/engine/test_diagram_components.py:510: In direction right, no new test proves the straight first leg: the `right` case of the taller-box test and all 60 `right` fuzz seeds pass on the old code.
- r-004 medium test afkv2/tests/engine/test_diagram_components.py:542: No test ties the label of a curved arrow to its arrow, so a label 2000px away passes every test.
- r-005 low test afkv2/tests/engine/test_diagram_components.py:491: `sampled` takes 21 points for each path segment at any length, so a long segment can step over a box.
