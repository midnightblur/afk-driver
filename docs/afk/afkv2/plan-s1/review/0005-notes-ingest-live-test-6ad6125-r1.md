# Review of 0005-notes-ingest-live-test, round 1

Telemetry only. The review record is pull request 155. Keys f001 to f023 on the unit are r-001 to r-023 in the same order.

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (Complexity complex), refactor-safety (the slice changes existing lines) · skipped: api-contract, domain-alignment (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (to the feature gate)
verified: no skeptic ran; the one design-level finding (r-004) stays as advice under R-2. Caller set: engine._element_ids has 2 callers in engine.py, read by refactor-safety; no coverage ledger exists.

Diff 6ad61252..b5a4069c.

Verdict: blocking, 0/1/11/11 (critical/high/medium/low). The orchestrator raised r-001 from medium to high: the reviewer's own failing input is a real bug on a reachable path. The fix is in the commit with `Settles: 0005-notes-ingest-live-test/f001`. Under owner ruling R-2 the medium and low findings stay on the pull request as advice.

- r-001 high correctness afkv2/engine/shell/notes.js:235: Edit and Delete on one sent note share an entry, so the second click does the wrong thing. Edit then Delete queues no delete and the prefilled edit goes out unchanged. Delete then Edit throws a TypeError.
- r-002 medium correctness afkv2/engine/ingest.py:284: Ingest writes the document first and the settled-round copy second, with no rollback. A failure in the copy write leaves a changed settled round that no longer matches the saved copy, and every later check refuses the document.
- r-003 medium correctness afkv2/engine/engine.py:210: Possible latent break: `_check_changed` passes the in-memory `doc` as the `raw` argument of `_content_problems`, and ingest then writes that `doc` back over the file.
- r-004 medium design afkv2/engine/engine.py:209: Possible guard loss: ingest skips the whole settled-round compare and then re-saves the copy, so any unintended edit to a settled round becomes the new baseline.
- r-005 medium test afkv2/tests/engine/test_ingest.py:785: Possible tautology: the test for the notes script's contract with the runtime only checks that attribute names occur as text in notes.js.
- r-006 medium test afkv2/tests/engine/test_ingest.py:777: The only automated test of the AC-041 draft key (session id + round, cleared on send) asserts that a constant copied from notes.js occurs in notes.js.
- r-007 medium test afkv2/tests/engine/test_engine_core.py:610: After the rewrite, the slot test no longer shows that the slot draws the registered component, which D-54 requires.
- r-008 medium test afkv2/tests/engine/test_ingest.py:441: Possible weak steer-home test: the linked-card and node-holder preferences cannot be told apart from the current-round order in any test.
- r-009 medium test afkv2/engine/ingest.py:239: No test edits or deletes a note whose target is a steer (a map node, or the map).
- r-010 medium test afkv2/engine/ingest.py:282: No test makes the check after the change (`check_changed`) refuse, so the guarantee that ingest writes only a valid document has no failing test.
- r-011 medium test afkv2/engine/ingest.py:98: No test sends an option letter that the debate card does not offer, or any mark on an info card.
- r-012 medium test afkv2/tests/live/test_page_live.md:560: The Result table of the live test has no row. The file holds no record of a pass, the commit tested, the layout audit, or the lavish-axi version.
- r-013 low scope .claude/wiring-ious.md:13: The diff edits .claude/wiring-ious.md, which matches no glob in the 0005 `## Scope`.
- r-014 low spec docs/afk/afkv2/plan-s1/0005-notes-ingest-live-test.md:43: The acceptance bullet and the Verification row name Playwright MCP. The slice drives Edge through a raw DevTools-protocol Node driver (D-53). The contract text was not amended.
- r-015 low spec afkv2/engine/ingest.py:232: A reopen is written into the signals of the current round only. For a settled card of the current round the reopen is not recorded in the next round. The carry of the card to the next round is left to a caller.
- r-016 low spec afkv2/engine/ingest.py:57: For an open or blocked point, conflicting signals go to needs_reading, not open. The contract bullet and PRD AC-037 say 'stays open'. Only a settled point goes to open.
- r-017 low spec afkv2/engine/ingest.py:147: When no item has a free note for the round, a steer is folded into a card note, and the stored note target becomes the item id. No test shows that a folded second note moves the target (D-50).
- r-018 low test afkv2/tests/engine/test_ingest.py:765: The test that long text wraps checks only that 2 CSS strings occur in notes.css.
- r-019 low test afkv2/engine/engine.py:122: No test puts an entry in the `maps` list whose type is not `map`, so the `root_is_map` branch has no coverage.
- r-020 low test afkv2/tests/engine/test_ingest.py:564: The last assertion of the map-in-a-label test is always true, and the `capsys` argument is unused.
- r-021 low test afkv2/tests/engine/test_ingest.py:349: The test of 'the agent returns an unclear point to open' sets the state by hand and then checks the fixture it just built.
- r-022 low test afkv2/tests/live/test_page_live.md:350: 4 driver steps pass a constant `true`, so the step line records a pass whatever happened.
- r-023 low test afkv2/engine/engine.py:221: No test covers the branch where the data folder is missing and ingest skips saving the settled copy without a message.
