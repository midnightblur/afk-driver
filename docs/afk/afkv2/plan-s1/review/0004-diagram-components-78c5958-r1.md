# Review of 0004-diagram-components, round 1

Telemetry only. The review record is pull request 155.

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity (always under lean), logic-correctness (0005 consumes this slice), refactor-safety (a pre-existing line changed) · skipped: domain-alignment, api-contract (no trigger) · deferred: agents-md-compliance, code-quality, design-quality, resilience (→ feature gate)
verified: no design-level finding, so no verify pass ran. Caller set: no pre-existing public symbol changed, so no coverage ledger exists.

Diff 78c59586..ab931ae0.

Verdict: blocking, 0/3/10/4 (critical/high/medium/low). 2 high findings are fixed in b56ca907, with a medium and a low finding that the same change closes. The third high finding goes to slice 0005 by orchestrator ruling D-43. The other findings stay on the pull request as advice under owner ruling R-2.

- r-001 high correctness afkv2/engine/components/diagram_map.py:17: A map held in a card or a table cell emits data-afkv2-element for node ids that engine._element_ids never reads, so `check` passes duplicate element ids, and no plan step owns the fix. [deferred(0005-notes-ingest-live-test, orchestrator ruling D-43)]
- r-002 high spec afkv2/engine/shell/diagram_boxes.py:197: An arrow that skips a rank is not visible: on edges a->c, c->b, a->b the a->b arrow runs behind box c and on top of the other two arrows, so the picture shows only a->c->b. [fixed(b56ca907)]
- r-003 high correctness afkv2/engine/shell/diagram_boxes.py:200: Edge labels of one source land on each other, and the opaque later label hides the text of the earlier one. [fixed(b56ca907)]
- r-004 medium correctness afkv2/engine/shell/diagram_boxes.py:101: In direction right, a long edge label on the top row runs above the canvas, and the top lines cannot be reached by scrolling. [fixed(b56ca907)]
- r-005 medium spec afkv2/tests/engine/test_diagram_components.py:150: The unit tier does not hold the render snapshots that the contract row says it proves; the only whole-output check compares 2 renders in one run. [dismissed(advisory under owner ruling R-2)]
- r-006 medium test afkv2/tests/engine/test_diagram_components.py:164: The styling test matches a class name as a substring, so a class with no rule passes when a longer class name starts with it. [dismissed(advisory under owner ruling R-2)]
- r-007 medium test afkv2/tests/engine/test_diagram_components.py:172: The escape test misses the group label and the 2 id attributes. [dismissed(advisory under owner ruling R-2)]
- r-008 medium test afkv2/tests/engine/test_diagram_components.py:192: BAD_PROPS has no off-boundary or wrong-type row for many schema rules. [dismissed(advisory under owner ruling R-2)]
- r-009 medium test afkv2/tests/engine/test_diagram_components.py:316: No test reads the path of an arrow: the arrow assert only echoes the from and to ids of the input. [dismissed(advisory under owner ruling R-2)]
- r-010 medium test afkv2/tests/engine/test_diagram_components.py:325: The group frame assert runs only in direction `right`, with short group labels. [dismissed(advisory under owner ruling R-2)]
- r-011 medium test afkv2/tests/engine/test_diagram_components.py:338: No test asserts the box and gap sizes that come from the label: the layout tests check only that boxes do not overlap. [dismissed(advisory under owner ruling R-2)]
- r-012 medium test afkv2/tests/engine/test_diagram_components.py:345: No test asserts rank order when a node has 2 incoming paths of different length. [dismissed(advisory under owner ruling R-2)]
- r-013 medium test afkv2/tests/engine/test_diagram_components.py:397: The sequence tests do not prove that an actor stands in the column of its messages. [dismissed(advisory under owner ruling R-2)]
- r-014 low correctness afkv2/engine/components/diagram_map.py:16: A map held in a card takes a node round past the last round and draws it. [dismissed(advisory under owner ruling R-2)]
- r-015 low correctness afkv2/engine/shell/diagram_boxes.py:212: In direction down, a back-arrow label wraps in a column of about 38px, one or two words per line. [fixed(b56ca907)]
- r-016 low test afkv2/tests/engine/test_diagram_components.py:142: The 'own module' test does not link the registry entry to the module. [dismissed(advisory under owner ruling R-2)]
- r-017 low test afkv2/tests/engine/test_diagram_components.py:175: Possible conditional test logic: an if/elif/else on the type name builds the input inside the escape test. [dismissed(advisory under owner ruling R-2)]
