# Review 0007-grill-skill, round 2 (delta over e344a1cb)

Policy: lean. Delta roster: delta-sweep, logic-correctness (owner of the fixed high findings), test-veracity (the delta touches tests). Verified: 0 upheld / 0 downgraded / 0 dropped (no design-level finding of medium or above).

Verdict: advisory. Critical 0, high 0, medium 3, low 5. Under owner ruling R-2 these stay open on the pull request.

## r-001 medium correctness (logic-correctness)
`afkv2/skills/grill/scripts/round_document.py:216`

`--replace` treats a round as unseen when it has no `responses`, but the SKILL allows it only after `check` or `render` failed; the code does not check that `show` never ran.

Why: After `present` succeeded and the human is answering on the page (or answered but `ingest` has not run), `responses` is still empty, so `build --replace` deletes the round the human is answering.

Fix: Record a shown marker in the document when `show` succeeds and refuse `--replace` once it is set, or have `present` clear it on a check or render refusal only.

## r-002 medium correctness (logic-correctness)
`afkv2/skills/grill/scripts/grill_log.py:189`

The redefine pattern stops at any line that starts with a backtick, so a definition whose first line starts with a backtick is not replaced.

Why: For `**X**:\n`foo` is a thing.\n`Related:` Y` the header consumes `**X**:\n`, the lookahead then fails on the definition line, and the new text is written above the old definition, which stays as stale text.

Fix: Consume the first line after the header unconditionally as the definition, then stop only at label lines like `^`\w+:``.

## r-003 medium test (test-veracity)
`afkv2/tests/skills/test_grill.py:696`

No test covers the changed term-line regex `:[^\n]*\n`, which lets a definition sit on the same line as the term.

Why: A copy under C:/t/gmut2 with the regex changed back to `:\n(?:(?!`)...` still passed all 3 term tests, so that branch has no real test.

Fix: Add a glossary case with `**Alpha**: First.` on one line and assert that the upsert replaces the whole entry.

## r-004 low correctness (delta-sweep)
`afkv2/skills/grill/scripts/round_document.py:130`

`carries` is checked against `known_ids`, which holds component ids, map-node ids and same-round card ids as well as old card ids. It is not type-checked as a list of old card ids.

Why: A self-carry, a component id or a node id passes the check and writes a false `Carries <id>.` line onto the card. A string value is split into characters, and a nested list raises TypeError.

Fix: Require a list of str, and require each id to be a card id of a round before the one being built.

## r-005 low correctness (delta-sweep)
`afkv2/skills/grill/scripts/round_document.py:218`

`_drop_unanswered_round` removes only the round. The document-level `maps` that the dropped round wrote stay.

Why: If the corrected round input omits `maps`, the map state of the discarded round survives the replace, so the document is not back to its state before that round.

Fix: Rebuild `doc["maps"]` from the kept rounds, or make `--replace` require `maps` in the input, or state in SKILL.md that a replacing input must repeat `maps`.

## r-006 low test (delta-sweep)
`afkv2/tests/skills/test_grill.py:744`

`test_replace_restores_the_round_before_and_closes_it_again` asserts only the round states `[settled, current]` and that `present` runs. It never checks that the new text replaced the old text, or that the old round-2 ids were freed.

Why: A replace that kept stale round-2 content while restoring the states would still pass.

Fix: Assert "Two, corrected." is in the current round and the first "Two." text is not.

## r-007 low correctness (logic-correctness)
`afkv2/skills/grill/scripts/round_document.py:230`

On replace, `_apply_maps` compares against the dropped round's maps, so a node the correction returns to its pre-round state is stamped with the new round.

Why: Round 3 moved node X from A to B (stamp 3); replace input keeps X at A: `before` holds B/3, states differ, so X gets round 3 instead of its round-2 stamp. If the input omits `maps`, the dropped round's maps also stay in the document.

Fix: Snapshot `doc["maps"]` before building a round and restore it in `_drop_unanswered_round`.

## r-008 low test (test-veracity)
`afkv2/tests/skills/test_grill.py:723`

No negative test for `--replace` when no round is current, such as a missing doc.

Why: With the `current is None` guard in `_drop_unanswered_round` changed to `if False:`, all 3 replace tests still passed, so the `round-not-replaceable` refusal is unproven.

Fix: Add a test that runs `build --replace` on a fresh doc and asserts code `round-not-replaceable`.
