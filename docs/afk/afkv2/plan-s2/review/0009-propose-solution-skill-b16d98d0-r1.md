# Review 0009-propose-solution-skill, round 1

Policy: lean. Activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (the slice has a consumer, complexity complex). Skipped: refactor-safety, domain-alignment, api-contract (no trigger; all code is new). Deferred to the feature gate: code-quality, agents-md-compliance, design-quality, resilience.

Verdict: blocking. Critical 0, high 2, medium 12, low 10.

## r-001 high correctness (logic-correctness)
`afkv2/skills/propose-solution/scripts/design_round.py:104`

`_live` treats a carried card as not waiting, whatever the carrier is. A carrier with no `aspect`, `layer` or `locked` tag leaves the node looking settled, so the aspects-first guard and the sign-off check both pass.

Why: The build never requires a carrier to keep the node of the card it carries, so the gate can pass on a sign-off the human never gave.

Fix: In `_tagged` or `_check_order`, refuse a card whose `carries` names a card of node N unless the new card also has node N. Alternatively, make `is_settled` require a live carrier on the same node.

Evidence: `return waiting and not rd._carried(doc, item, round_n)`. Check with a throwaway doc: round 1 holds `signoff` s1 on `locked-hl-1`, state open. Round 2 holds a `confirm` card c2 with no tag, text 'Carries s1.', settled_by_mark. Result: `is_settled(doc,'locked-hl-1')` is True, `unfinished` lists no HL failure, and `_register_problems` returns [] for a `| HL-1 | §4 | signed | me / 2026-10-30 | sign |` row. Second check: 11 aspect cards, `keys` left open, then an untagged carrier of `keys`; `next_step` phase turns 'draft' and the layer cards are accepted.

## r-002 high correctness (logic-correctness)
`afkv2/skills/propose-solution/scripts/design_files.py:170`

The open-question check matches the Blocks cell only when it is exactly `yes`. The cell form the repo's own SDD uses, `<yes|no>: <reason>`, passes as non-blocking when it reads `yes: <reason>`.

Why: The gate exists to stop a blocking open question. A row such as `yes: needs the schema` in L2 to L7 or L9 slips through, which SDD-FORMAT.md:10 says must fail.

Fix: Match the cell by prefix with `re.match(r'(?i)yes\b', cells[2])`. Also accept layer cells that start with L<n>, for example `L3 (data)`.

Evidence: `if len(cells) > 2 and cells[1] in BLOCKING_LAYERS and cells[2].lower() == "yes":`. docs/afk/afkv2/SDD.md:489 uses `no: day-1 live check with a named fallback`. A throwaway §13 table gave: `| Q1 | L3 | yes: needs the schema |` not flagged, `| Q2 | L3 | Yes |` flagged, `| Q3 | L3 (data) | yes |` not flagged.

## r-003 medium spec (spec-fidelity)
`afkv2/skills/propose-solution/scripts/design_files.py:193`

The gate counts a signoff card settled by an agent-read note as a signature, not only one settled by a `sign` mark.

Why: `apply-readings` `settle` accepts a signoff card in `needs_reading`, so a `changes` mark plus a note can end as `settled_by_note` and still pass the gate for a `signed` §0 row.

Fix: In `_register_problems`, require the node's newest signoff card to be `settled_by_mark` with `settled.signal == 'sign'`; add a test that a note-settled signoff keeps the gate closed.

Evidence: design_files.py:193 `if not dr.is_settled(doc, node):` and design_round.py:102-104 `_live` treats only open/blocked/needs_reading as waiting, versus DRAFT.md:56 "A `sign` mark signs. A note that changes the wording returns the point" and DRAFT.md:58 "Without a human there is no signature." The test at test_propose_solution.py `test_a_changes_mark_on_a_signoff_keeps_the_gate_closed_until_a_sign` only uses the `open` reading, never `settle`.

## r-004 medium spec (spec-fidelity)
`afkv2/skills/propose-solution/ADR-FORMAT.md:51`

Bullets 1 and 3 give opposite `Audited:` rules for a record a human settled by mark, and the fixture ADR follows bullet 1 although its fork was a human option mark.

Why: An executor cannot tell whether a human-marked fork record carries an `Audited:` line, and the line's meaning ("presence says the agent decided") is false under bullet 1.

Fix: Merge bullets 1 and 3 into one rule for a human-settled record, and align the fixture ADR with it.

Evidence: ADR-FORMAT.md:49 "The human accepted the card: `Status: Accepted`, and `Audited:` the accept date." vs ADR-FORMAT.md:51 "The human decided it, as on a fork: `Status: Accepted`, and no `Audited:` line. The line's presence says the agent decided." Fixture adr/0001-join-table-for-export-runs.md:5 has `> Audited: 2026-01-06` with `> Forks: f-relations`.

## r-005 medium scope (scope-and-impact)
`afkv2/skills/propose-solution/scripts/design_files.py:255`

The slice calls underscore-private helpers of two sibling skills: grill_log._doc_failures, grill_start._raw_pending, prd_files._section, rd._drop_unanswered_round and rd._carried. No test of the grill or to-prd skill names any of them.

Why: A rename or signature change in the grill or to-prd scripts passes their own tests and breaks propose-solution at run time, so the caller set of those helpers is invisible to their owners.

Fix: Ask the owning skills to expose public names for these helpers, or add a test in test_grill.py and test_to_prd.py that pins each name this slice uses.

Evidence: failures = [*grill_log._doc_failures(doc), *dr.unfinished(doc), ...]  (design_round.py:98 `rd._drop_unanswered_round(doc)`, :104 `rd._carried(doc, item, round_n)`; design_files.py:94 `grill_start._raw_pending(raw_file, doc)`, :168/:177/:210 `prd_files._section(...)`). rg of tests/skills/test_grill.py and test_to_prd.py for these names finds no match.

## r-006 medium test (test-veracity)
`afkv2/tests/skills/test_propose_solution.py:730`

The only test that runs a built document through the real engine is skipped in this tree and covers round 1 only.

Why: The fake `check` accepts any body with a `type`, so the component schemas, table row width, global id uniqueness and map-node rules are never exercised here.

Fix: Extend the skipped test to a draft round (L1-L9 cards, a sign-off card, a fork) and keep a plan or CI line that makes it run once the engine merges.

Evidence: @pytest.mark.skipif(not ENGINE.exists(), reason="page engine not merged yet; the fake engine checks") ... world.build(started, json.loads((FIXTURES / "design" / "round-1.json").read_text("utf-8")))  [my check: I built round 1 and a draft round with layers, sign-off and a fork, then ran `git archive origin/feat/afkv2-s1` engine.py check on each: both ok. So no hidden failure now, but the guard is absent]

## r-007 medium test (test-veracity)
`afkv2/tests/skills/test_propose_solution.py:266`

The side-by-side test asserts the same `-opt-<letter>` ids that fork_cards.py writes; nothing checks that the engine reads them as option marks.

Why: fake_engine.py accepts any `option:<x>` token with no link to card options, so a wrong cell id or an `option:c` on a 2-option fork would still pass.

Fix: Put the real card rule (fullmatch `<item id>-opt-([a-z])` over the body tree) into the fake or a test helper, assert it returns [a, b] for a built fork, and assert an unknown option token is refused.

Evidence: assert [cell["id"] for cell in cells] == ["f-store-opt-a", "f-store-opt-b"]  /  marks = {"signoff": "sign", "debate": "option:a"}  [my check: real base_card.py debate_options on a built fork returns ['a','b']]

## r-008 medium test (test-veracity)
`afkv2/tests/skills/test_propose_solution.py:549`

No test shows that a sign-off card settled by a note, or by any mark other than `sign`, does not count as a signature.

Why: `_register_problems` accepts `signed` when `dr.is_settled` is true, and `round_document._settle` can settle a signoff card by note, so the gate can pass on a signature the human never gave, against DRAFT.md.

Fix: Add a case where HL-1 is settled_by_note and the register says signed; expect a gate failure, and fix the check to require a settled_by_mark `sign`.

Evidence: design_files.py: `if not dr.is_settled(doc, node): problems.append(f"{key}: signed, but no card holds its signature")`; DRAFT.md: "A `sign` mark signs. A note that changes the wording returns the point"; test only covers the no-card case: `test_a_signed_row_needs_a_settled_card` (HL-2)

## r-009 medium test (test-veracity)
`afkv2/tests/skills/test_propose_solution.py:219`

No test refuses a layer asked before the layer above it, or an aspect skipped across rounds.

Why: `_check_order` has a layer branch and a cross-round `asked` set; both can break unseen, while the plan and DRAFT.md state a fixed top-down order.

Fix: Add two cases: L2 before L1 in a built session whose aspects are settled, and keys asked in round 2 after only entities in round 1; expect `out-of-order`.

Evidence: rg of the test file finds `refused.value.code == "out-of-order"` only at the two aspect tests (lines 197 and 210); `test_a_layer_card_waits_for_every_aspect` asserts only `aspects-first`

## r-010 medium test (test-veracity)
`afkv2/tests/skills/test_propose_solution.py:635`

SDD-FORMAT.md lists the blocker tokens; tests cover only TBD, TODO and the template placeholders, and the template test asserts only that some problem exists.

Why: A regex typo in FIXME, XXX, ???, (decide later), (unresolved) or (open) would pass every test, and `assert blocker_problems(template)` stays true if one token works.

Fix: Parametrize `blocker_problems` over every token the format file names, and assert the problem names that token.

Evidence: assert design_files.blocker_problems(template), "a copy of the template with placeholders must not pass"; param list: ["{who}", "{system}", "<NNNN>", "<service>", "ADR-NNNN", "<?>", "FILL_IN", "<TODO>"]

## r-011 medium test (test-veracity)
`afkv2/tests/skills/test_propose_solution.py:567`

The test says the gate stays closed until a sign, but it never signs and never runs the gate after the new card.

Why: The last assertion reads `next` output only, so reopening the gate after a real `sign` mark is unproven.

Fix: Answer `sign-hl-2-b: sign`, then assert the gate has no failure naming HL-2 (with the register row set to signed).

Evidence: world.build(started, round_of({**sign("sign-hl-2-b"), "carries": ["sign-hl-2"]}))\n    assert world.run("next", doc=started["doc"])["locked_open"] == [{"key": "HL-2", "label": "API surface"}]

## r-012 medium correctness (logic-correctness)
`afkv2/skills/propose-solution/scripts/design_files.py:193`

A `signed` register row passes when the sign-off card was settled by a note. `is_settled` only checks that no card waits, not that a `sign` mark settled it.

Why: DRAFT.md:56 says only a `sign` mark signs and a note that changes wording returns the point. `apply-readings settle` allows a sign-off card to settle by note.

Fix: For a `signed` row, require the card to be `settled_by_mark` with a sign signal, or refuse the note-settled form.

Evidence: A doc with `{kind:'signoff',state:'settled_by_note',node:'locked-hl-1',settled:{by:'note',...}}` gave `is_settled` True and no `_register_problems` entry for a `| HL-1 x | §4 | signed | me / 2026-10-30 | fine |` row. Code: `if not dr.is_settled(doc, node):`.

## r-013 medium correctness (logic-correctness)
`afkv2/skills/propose-solution/scripts/design_round.py:80`

Only `aspect` cards have their kind restricted. A `layer` card may be `info`, which asks nothing, so `is_settled` counts the layer as settled with no human answer.

Why: The gate's `layer ... is not settled` check passes for a layer the human never vetted, against the 'human vets the draft' rule of DRAFT.md:3.

Fix: Refuse `info` (and `signoff`) on a `layer` card, or have `is_settled` ignore non-asking cards.

Evidence: `if group == "aspect":` is the only kind check. `_live` is `waiting = item["kind"] in rd.ASKING ...`, and `rd.ASKING = KINDS - {"info"}`. `is_settled` is `bool(cards) and not any(...)`, so a lone `info` card gives True.

## r-014 medium correctness (logic-correctness)
`afkv2/skills/propose-solution/SKILL.md:33`

On `resume` the skill sends the agent to step 3. When the current round is built but unanswered, `next` reports its open cards as `aspects_open` and `layers_open` to return, and `next` has no field saying the round is unanswered.

Why: The next `build` is refused with `round-not-sent`. The only exit is `--replace`, which discards a page the human may be answering.

Fix: Make `next` return `current_round_state` (unanswered, answered, needs_reading). Make the resume text say: unanswered, go to step 5 `present` or step 6 `wait`; answered, go to step 7.

Evidence: SKILL.md:33 `resume` true: read `doc`, honour every steer in it, and continue at step 3. round_document.py:198 `raise Refusal("round-not-sent", f"round {current['n']} has no answer yet; ingest its answer first")`. grill/SKILL.md:33 says 'continue at the first unfinished step of the current round'.

## r-015 low spec (spec-fidelity)
`afkv2/skills/propose-solution/SKILL.md:17`

The Input table says a missing requirement ADR set stops the skill and names `/afkv2:to-prd`, but `start` checks only PRD.md.

Why: The documented stop row has no code behind it, and a feature may legitimately have no requirement ADRs (INDEX shows `—`), so the table row is wrong or the check is missing.

Fix: Change the table row to PRD.md only, and say the requirement ADRs are read when they exist.

Evidence: SKILL.md:17 "| `PRD.md` and the requirement ADRs | written by `/afkv2:to-prd` | stop and name the file and `/afkv2:to-prd` |" vs design_files.py:82-83 `if not prd.is_file(): raise Refusal("missing-input", ... writer=TO_PRD)` with no check of `adr/requirements`.

## r-016 low scope (scope-and-impact)
`afkv2/skills/propose-solution/scripts/design_files.py:16`

The slice imports scripts of afkv2/skills/grill/scripts (grill_common, grill_log, grill_start, round_document) and afkv2/skills/to-prd/scripts (prd_files). The contract `## Consumes` names only `afkv2/skills/to-prd/SKILL.md#name: to-prd`, and `## Blocked by` names only 0008.

Why: The seam to the grill scripts is declared nowhere, so a consumer preflight cannot catch a break in it.

Fix: Add Consumes lines for the grill and to-prd script anchors in the contract, or record the coupling as a decision in plan-s2/DECISIONS.md.

Evidence: sys.path.insert(0, str(SKILL.parent / "to-prd" / "scripts")) / sys.path.insert(0, str(SKILL.parent / "grill" / "scripts"))  vs  "## Consumes\n- 0008-to-prd-jira-publish afkv2/skills/to-prd/SKILL.md#name: to-prd"

## r-017 low test (test-veracity)
`afkv2/tests/skills/test_propose_solution.py:319`

4 bad-fork inputs run in a for loop in one test.

Why: A failure does not say which input, and the first failing case hides the rest.

Fix: Use pytest.mark.parametrize with the four cards.

Evidence: for card in ({"id": "f", "fork": fork, "body": {"type": "text"}}, ... {"id": "f", "fork": "A or B?"}):\n        with pytest.raises(Refusal) as refused:

## r-018 low test (test-veracity)
`afkv2/tests/skills/test_propose_solution.py:529`

The `signed` case blanks signer and wording together, and no case covers `n/a` with an empty reason.

Why: A check that tests only one of the two cells, or a missing `n/a needs its reason` branch, would still pass.

Fix: Add one case per cell, and an n/a row with an empty reason.

Evidence: ('| signed | owner / 2026-01-06 | "sign" (R-4) |', "| signed | — | — |", "HL-1: signed needs who, date and the human's words")

## r-019 low test (test-veracity)
`afkv2/tests/skills/test_propose_solution.py:189`

A test named for "no other file" scans only SKILL.md for two labels.

Why: DRAFT.md or SDD-FORMAT.md could copy the aspect list without failing it (my rg of the skill folder found no such copy today).

Fix: Scan every file of the skill folder except ASPECTS.md for the labels in CAT_A_LABELS.

Evidence: skill = SKILL_MD.read_text("utf-8")\n    assert "Data migration" not in skill and "Large data" not in skill

## r-020 low test (test-veracity)
`afkv2/tests/skills/test_propose_solution.py:652`

The PRD fixture is only checked with startswith; the round input is a hand-written file, so no step shows a PRD yielding the round.

Why: The plan's integration row says a PRD fixture gives a round document; the test proves only that the scripts accept a pre-written round.

Fix: Say in the test docstring that the agent step is out of reach, or assert that the round input cites facts from the PRD fixture (entity names).

Evidence: assert (world.repo / started["prd"]).read_text("utf-8").startswith("# PRD — order export")

## r-021 low test (test-veracity)
`afkv2/tests/skills/test_propose_solution.py:715`

The end of the dry run expects the signed HL-1 map node to read `focus`.

Why: The test records the stale state of a node whose card was signed as the expected result, so a later refresh of the map would break it.

Fix: Assert `settled` after a rebuild, or drop the assertion.

Evidence: assert nodes_of(doc, "m-locked")["locked-hl-1"]["state"] == "focus"

## r-022 low correctness (logic-correctness)
`afkv2/skills/propose-solution/scripts/fork_cards.py:37`

`recommended not in LETTERS[:len(options)]` is a substring test. A multi-letter value such as 'ab' is accepted, and `recommended` set to `""` is also accepted.

Why: The card then shows 'Recommended: AB.' naming no single option.

Fix: Check `isinstance(recommended, str) and len(recommended) == 1 and recommended in LETTERS[:len(options)]`.

Evidence: `build_fork_card('f1','q',[3 options],'w',recommended='ab')` returned body text `q Recommended: AB.`

## r-023 low correctness (logic-correctness)
`afkv2/skills/propose-solution/scripts/design_files.py:63`

After a passed gate, a re-run starts a blank page document. The new gate then needs a card for every aspect and layer, and a card for every `signed` register row kept from the earlier session.

Why: A one-layer change forces a re-ask of all 11 aspects and 9 layers, and a re-sign of unchanged human-locked rows. A kept `signed` row without a new card is refused.

Fix: Either state in SKILL.md that a change session re-asks everything, or let the gate accept a `signed` row whose card is in an earlier passed session document.

Evidence: `return sessions[-1] if sessions and not gate_passed(log, sessions[-1]) else None` (new session, empty doc); design_files.py:193 `if not dr.is_settled(doc, node): problems.append(f"{key}: signed, but no card holds its signature")` reads only the new session's doc.

## r-024 low correctness (logic-correctness)
`afkv2/skills/propose-solution/scripts/design_files.py:263`

`gate` writes the `design gate passed` log row before it updates INDEX.md. If `set_row` refuses, the answer is a failure but the session is already closed.

Why: The next `start` opens a new session because the gate row exists, so the half-done pass cannot be resumed.

Fix: Update INDEX.md first, or write the gate row last and roll it back on error.

Evidence: `_write_section(log, head, [*rows, f"{GATE_PASSED} {today} {session}"], tail)` comes before `prd_files.set_row(index, "SDD", SDD_NAME, "draft")`, which can raise `bad-index`.
