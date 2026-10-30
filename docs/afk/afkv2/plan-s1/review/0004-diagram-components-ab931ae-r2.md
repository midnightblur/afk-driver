# Review of 0004-diagram-components, round 2

Telemetry only. The review record is pull request 155.

policy: lean · activated: delta-sweep, logic-correctness and spec-fidelity (owners of the fixed high findings), test-veracity (the change touches tests) · skipped: scope-and-impact (the one new out-of-Scope path is the IOU file, the standing exception), refactor-safety (no pre-existing line changed in this delta) · deferred: agents-md-compliance, code-quality, design-quality, resilience (→ feature gate)
verified: no design-level finding, so no verify pass ran. Caller set: no pre-existing public symbol changed, so no coverage ledger exists.

Diff ab931ae0..691d6334.

Verdict: blocking, 0/3/10/3 (critical/high/medium/low). All 3 high findings are fixed in 01d5e325, with 2 medium and 1 low findings that the same change closes. The other findings stay on the pull request as advice under owner ruling R-2.

- r-001 high compliance .claude/wiring-ious.md:13: The new IOU anchors on the 0005 contract, but that contract does not name the symbol or the held-map work. [fixed(01d5e325)]
- r-002 high correctness afkv2/engine/shell/diagram_boxes.py:142: A forward arrow still passes behind a box: the lane check reads only the ranks between the two ends, so a taller box in the source rank hides the curve and the picture shows a false connection. [fixed(01d5e325)]
- r-003 high test afkv2/tests/engine/test_diagram_components.py:481: The long-label canvas test uses only a forward arrow, and a long label on a self arrow in the down direction leaves the canvas at the top. [fixed(01d5e325)]
- r-004 medium design afkv2/engine/shell/diagram_boxes.py:147: Each lane stays apart from every earlier lane, also when the 2 arrows share no rank, so render time grows by about the cube of the arrow count and the canvas grows with it. [dismissed(advisory under owner ruling R-2)]
- r-005 medium spec afkv2/engine/shell/diagram_boxes.py:258: A back arrow runs behind the next box in its stack, so it can look as if it starts at that box; one box below is enough, not only the 'tall stack' that D-42 records. [dismissed(advisory under owner ruling R-2)]
- r-006 medium correctness afkv2/engine/shell/diagram_boxes.py:291: A label with many long words or with wide glyphs is taller than the estimate, so labels land on labels and on boxes and go past the canvas, which the remediation says no longer happens. [dismissed(advisory under owner ruling R-2)]
- r-007 medium correctness afkv2/engine/shell/diagram_boxes.py:302: In direction right, an arrow label can land on a group title and hide its text, because the taken set holds boxes only. [dismissed(advisory under owner ruling R-2)]
- r-008 medium correctness afkv2/engine/shell/diagram_boxes.py:313: The fix keeps a label on the canvas on the cross axis only: on the main axis, a long label on a self-loop in direction down starts above the canvas. [fixed(01d5e325)]
- r-009 medium test afkv2/tests/engine/test_diagram_components.py:397: `turns` drops the minus sign, so the `0 <= x` and `0 <= y` half of the canvas assertion can never fail. [fixed(01d5e325)]
- r-010 medium test afkv2/tests/engine/test_diagram_components.py:426: Every lane test skips exactly one rank that holds one box, so a box in a later skipped rank is not tested. [dismissed(advisory under owner ruling R-2)]
- r-011 medium test afkv2/tests/engine/test_diagram_components.py:429: No test pins the route of a lane arrow, so a diagonal first leg, the farthest lane and a label away from its lane all pass. [dismissed(advisory under owner ruling R-2)]
- r-012 medium test afkv2/tests/engine/test_diagram_components.py:449: The lane test stops at 2 parallel arrows and proves only that 2 lanes differ, so lane reach, lane spacing and canvas growth for lanes are not tested. [dismissed(advisory under owner ruling R-2)]
- r-013 medium test afkv2/tests/engine/test_diagram_components.py:469: The label-collision tests do not exercise the `_Taken` cell lookup or its sort order, because no fixture has labels of different sizes on one arrow gap. [dismissed(advisory under owner ruling R-2)]
- r-014 low spec afkv2/engine/shell/diagram_boxes.py:247: A forward arrow from a short box can still pass behind a taller box of its own rank, but D-42 says the gap is closed for forward arrows. [fixed(01d5e325)]
- r-015 low test afkv2/tests/engine/test_diagram_components.py:432: Possible conditional test logic: an `if direction` branch selects the asserts inside one test body. [dismissed(advisory under owner ruling R-2)]
- r-016 low test afkv2/tests/engine/test_diagram_components.py:492: Possible weak test: the max-content test greps the CSS source, and its pattern also matches `max-width: max-content`. [dismissed(advisory under owner ruling R-2)]
