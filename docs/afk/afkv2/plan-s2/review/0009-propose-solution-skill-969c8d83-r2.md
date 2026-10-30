# Review 0009-propose-solution-skill, round 2

Policy: lean, delta round. Activated: delta-sweep, logic-correctness (fix owner), test-veracity (the change touches tests). Reviewed range: 969c8d83..27564e9b.

Verdict: advisory. Critical 0, high 0, medium 6, low 0.

## r-001 medium correctness (delta-sweep)
`afkv2/skills/propose-solution/scripts/design_round.py:120`

An item with no id now crashes the build with KeyError instead of a Refusal. `_check_carriers` reads item["id"] before the grill builder checks ids.

Why: `_tagged` lets an id-less dict through, and `round_document.py:95` used to refuse it as `bad-item`. `_check_carriers` now runs first and breaks that refusal path.

Fix: Use item.get("id") in the nodes map, or skip items without an id and let the grill builder refuse them.

Evidence: nodes.update({item["id"]: item.get("node") for item in items}) | round_document.py:95 `if not isinstance(raw, dict) or not raw.get("id"): raise Refusal("bad-item", ...)`

## r-002 medium correctness (logic-correctness)
`afkv2/skills/propose-solution/scripts/design_round.py:124`

_check_carriers accepts a carrier of kind `info` on a layer or locked node, so the node settles with no asking card left.

Why: Only aspect nodes limit card kinds to confirm/debate (ASPECT_KINDS), and `info` is not in ASKING, so `_live` is false for both the carried card and the carrier, and the check's stated aim 'so the node stays open' fails.

Fix: Also refuse a carrier whose kind is not in rd.ASKING when it carries a card on a reserved node (or require the carrier kind to be an asking kind).

Evidence: Probe: round 1 `{id:l-2, layer:L2, kind:confirm}`, round 2 `{id:c-1, layer:L2, kind:info, carries:[l-2]}` builds without refusal, and `is_settled(doc,'layer-l2')` returns True. Check: `if nodes.get(carried) in reserved and item.get("node") != nodes[carried]` tests the node only.

## r-003 medium correctness (logic-correctness)
`afkv2/skills/propose-solution/scripts/design_files.py:171`

The §13 blocking check reads only the start of the Layer cell, so a blocking row whose cell lists several layers or wraps the layer is not found.

Why: `BLOCKING_LAYER.match` anchors at the cell start, so a row for L3 that starts with L1, or has markup before the layer, passes the executor gate although it blocks.

Fix: Use `BLOCKING_LAYER.search` on the cell with a lookbehind that rejects a letter or digit (e.g. `(?<![\w])L[2-79]\b`), and strip markup characters first.

Evidence: re.compile(r"L[2-79]\b").match on 'L1, L3', 'L1-L9' and '`L3`' returns None, so `| Q | L1, L3 | yes | o | d |` raises no problem. Line: `BLOCKING_LAYER.match(cells[1]) and BLOCKING_ANSWER.match(cells[2])`.

## r-004 medium test (test-veracity)
`afkv2/tests/skills/test_propose_solution.py:763`

The carry-node refusal is tested only for an `aspect` node carried from an earlier round; layer, locked and same-round carried cards are untested.

Why: `_check_carriers` guards all three reserved groups and merges same-round items via `nodes.update`, so a break in either branch would leave every test green.

Fix: Add cases where the carried card is a layer card, a signoff card, and a card in the same round as the carrier.

Evidence: `carrier = {"id": "c-1", "kind": "confirm", "carries": ["a-entities"], ...}` vs design_round.py:119-125 `nodes.update({item["id"]: item.get("node") for item in items})` and `reserved = _reserved_nodes()`

## r-005 medium test (test-veracity)
`afkv2/tests/skills/test_propose_solution.py:774`

Neither carrier test asserts that the aspect stays open; the refuse test only checks the error code, and the accept test only checks the returned item ids.

Why: The behaviour named (`so the old node stays open`) is not observed, so the tests pass even if the node settles after a same-node carrier.

Fix: After the same-node build, run `next` and assert `entities` is in `aspects_open`; in the refuse test, assert the document still has no round-2 item.

Evidence: `assert answer["items"] == ["a-entities-2"]` and `assert "aspect-entities" in answer["error"]["reason"]`

## r-006 medium test (test-veracity)
`afkv2/tests/skills/test_propose_solution.py:782`

The new regexes `L[2-79]\b` and `yes\b` are tested at L3 only, so neither the class edges (L2, L9) nor the word-boundary negatives (L10, L20, `yesterday`) are covered.

Why: A typo such as `[2-7]` or a dropped `\b` would keep every test green.

Fix: Add blocking cases L2 and L9 and harmless cases L10, L20, `yesterday`, `yes` in a layer-less cell.

Evidence: `[("L3", "yes: needs the schema"), ("L3", "Yes"), ("L3 (data)", "yes")]` and `[("L3", "no: a named fallback exists"), ("L8", "yes: a font"), ("L1", "yes")]`
