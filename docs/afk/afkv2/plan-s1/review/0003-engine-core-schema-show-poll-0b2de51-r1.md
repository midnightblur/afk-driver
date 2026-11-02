# Review of 0003-engine-core-schema-show-poll, round 1

Telemetry only. The review record is pull request 155.

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (lean trigger: later slices consume this one), refactor-safety (trigger: the slice edits hooks.json), api-contract (trigger: the page schema is a public document shape) · skipped: domain-alignment (no trigger) · deferred: agents-md-compliance, code-quality, design-quality, resilience (→ feature gate)
verified: no finding of a design-level concern at medium or above was promoted to a fix, and the design-class medium findings stay advisory under R-2, so no verify pass ran. Caller set: no pre-existing public symbol changed, so no coverage ledger exists.

Diff 0b2de51a..e39818dc.

Verdict: blocking, 0/3/18/10 (critical/high/medium/low). The 3 high findings are one fix for table cells and one fix for map entries.

- r-001 high correctness afkv2/engine/components/base_table.py:38: Components held in table cells skip the component schema, so a malformed cell crashes check with no JSON answer.
- r-002 high correctness afkv2/engine/engine.py:70: describe() crashes on a non-object map entry, so check prints a traceback instead of a refusal.
- r-003 high correctness afkv2/engine/registry.py:78: Components held in props (table cells) never pass the component-shell schema, so check accepts bad cells and check or render crashes.
- r-004 medium design afkv2/engine/components/base_card.py:93: Possible leak: page-assembly types `card` and `round-banner` are public registry names that take loose props.
- r-005 medium correctness afkv2/engine/engine.py:144: The saved-copy key uses abspath, but render saves under the resolved path, so the rewrite check can silently turn off.
- r-006 medium correctness afkv2/engine/engine.py:157: A saved copy outlives its document and has no identity check, so a restored or recreated document at the same path is refused with no way out.
- r-007 medium correctness afkv2/engine/engine.py:213: The duplicate-session glob matches other sessions whose id ends with this id.
- r-008 medium correctness afkv2/engine/engine.py:225: Only Refusal is caught, so an OSError or KeyError in render or in the saved copy gives a traceback, not one JSON object.
- r-009 medium spec afkv2/engine/engine.py:307: main() catches only Refusal; any other exception ends in a traceback with no JSON object.
- r-010 medium design afkv2/engine/launcher.py:399: Possible loss of prompt boundaries: poll joins several host prompts into one `raw` string with a line break.
- r-011 medium correctness afkv2/engine/schema/page-v0.schema.json:78: Item id allows spaces and '|', but the response grammar splits a line on spaces.
- r-012 medium correctness afkv2/engine/shell/tips.js:37: The tooltip wrapper replaces text inside SVG text elements with HTML span elements.
- r-013 medium test afkv2/hooks/codex_stop.py:70: The Stop hook as Codex runs it (stdin, stdout, exit 0) is tested only with no record; the never-fail-the-stop path is unexercised
- r-014 medium design afkv2/hooks/hooks.json:25: Possible cost on every Codex turn end: the new Stop entry starts bare `python` even when no page waits.
- r-015 medium test afkv2/tests/engine/test_engine_core.py:580: test registers the type name "map", which slice 0004 owns
- r-016 medium test afkv2/tests/engine/test_engine_core.py:583: Map node validation has one valid example and no refusal case
- r-017 medium test afkv2/tests/engine/test_engine_core.py:664: Browser draft behaviour is tested by string search in runtime.js, not by running it
- r-018 medium test afkv2/tests/engine/test_engine_core.py:743: Launcher grammar has no negative case for extra or conflicting open flags, or for poll and end argument counts
- r-019 medium test afkv2/tests/engine/test_engine_core.py:976: Codex waiting-record clearing by a foreground poll is tested for feedback only
- r-020 medium test afkv2/tests/engine/test_engine_core.py:1053: No test pins the 5-second retry sleep for non-waiting statuses in the Stop-hook wait
- r-021 medium test afkv2/tests/engine/test_engine_core.py:1104: The only test of the real host and of the Windows .cmd job binding is skipped in CI
- r-022 low spec afkv2/engine/components/base_card.py:79: A blocked card gets the round chip, though it takes no mark and is not flagged as required.
- r-023 low design afkv2/engine/engine.py:254: Success answers carry fields (`saved_copy`, `url`, `status`, `waiting_record`, `prompts`, `session_ended`) that no doc or caller names.
- r-024 low design afkv2/engine/engine.py:298: `show --no-open` and `--reopen` have no consumer outside the tests.
- r-025 low correctness afkv2/engine/launcher.py:283: Host stderr goes to DEVNULL, so a node crash gives an empty reason.
- r-026 low correctness afkv2/engine/schema/invariants.py:125: A note whose target is a map node cannot settle a card, though SDD lets a note target any element id.
- r-027 low correctness afkv2/engine/schema/validate.py:98: A schema with additionalProperties set to a schema object is accepted by check_schema but never applied.
- r-028 low design afkv2/hooks/codex_stop.py:45: Possible tight retry: a `browser_disconnected` poll answer is retried every 5 s for up to an hour.
- r-029 low test afkv2/tests/engine/test_engine_core.py:899: A loop with an if verb == "poll" branch steers setup inside one test body
- r-030 low test afkv2/tests/engine/test_engine_core.py:1088: Hook timeout test hard-codes 3600 instead of tying to codex_stop.WAIT_SECONDS
- r-031 low scope afkv2/tests/live/CODEX-LIVE-CHECKS.md:41: Pre-existing live-check file is edited but no ## Scope glob of 0003 names it.
