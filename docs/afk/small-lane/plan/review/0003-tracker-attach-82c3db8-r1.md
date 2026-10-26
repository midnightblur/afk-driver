# Review — 0003-tracker-attach-82c3db8-r1

- policy: lean · full-unit round · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (complex slice with a consumer), refactor-safety (modified lines), api-contract (public surface) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verdict: findings — 8 medium, 6 low; all fixed in 7feb708
- mutation probe not run (tests run in CI on the human's call)
- head: 2fe97a96392fd5e3dba5e8b578b79d2fe3f6eb09
- counts: crit=0 high=0 med=8 low=6

## r-001 · medium · design · `adapters/tracker/github-issues/api.py:390`
A missing file (also empty `files`) answers error without `refused: true` on GitHub and Jira, while ADAPTERS.md says a missing file is refused before any write and refusals carry `refused: true`.

- Why: A caller testing `refused` to tell 'nothing written' from a failure mid-write gets the wrong signal.
- Fix: Add "refused": True to these pre-write answers in both adapters (and the files-validation answer).
- Concern: api-contract (Wrong protocol semantics / error contract)

## r-002 · medium · design · `adapters/tracker/github-issues/api.py:419`
`attached` is a list of path strings on GitHub but a list of {file,id,filename,mimeType} objects on Jira; ADAPTERS.md does not fix the element shape.

- Why: The verb is meant to be the same on every kind, yet a caller reading `attached` must branch on tracker kind.
- Fix: Use one element shape (e.g. {file,...}) on all kinds and state it in ADAPTERS.md.
- Concern: api-contract (Easy to misuse / inconsistent answer shape across kinds)

## r-003 · medium · correctness · `adapters/tracker/jira/api.py:687`
Possible regression: tracker_create with fix_version now needs a successful GET of project versions first; any read failure of that call (e.g. a login that can create but not read versions) returns the error and the issue is never created, where before the POST was sent unchecked.

- Why: _check_fix_versions returns the GET's error dict unchanged, and _op_create returns it, so a read-only failure on a side lookup blocks a write that used to succeed (the to-ticket spinoff create at skills/afk/to-ticket/SKILL.md:96 passes fix_version).
- Fix: Refuse only on a successful versions read that lacks the name; on a read error proceed with the POST (or surface a warning), and pin that with a test.
- Concern: refactor-safety,scope-and-impact (behaviour-preservation of changed pre-existing method (Jira _op_create))

## r-004 · medium · correctness · `adapters/tracker/jira/api.py:723`
tracker_create with status 'Nope': the issue IS created, but status_warning reads "...has no transition `Nope`; it offers: ...; nothing was written" because _resolve_transition reuses _refused's suffix.

- Why: The warning tells the caller nothing was written when the issue already exists, so a caller may retry the create and make a duplicate.
- Fix: Build the create-path warning without the _refused suffix (e.g. return the bare reason from _resolve_transition and add the suffix only in _refused callers that precede a write).
- Concern: logic-correctness (error and rollback paths / partial-failure handling)

## r-005 · medium · correctness · `adapters/tracker/jira/api.py:770`
zip(files, uploaded) truncates silently: if Jira returns fewer attachment objects than files, the extra files appear in neither `attached` nor `unsupported_files` and the answer is ok:true.

- Why: The answer shape gives the caller no signal that a file was uploaded or dropped unreported; the code comment itself says part-order is unverified.
- Fix: If len(uploaded) != len(files), answer error naming the count mismatch, or match by filename and list unmatched files as mismatches.
- Concern: api-contract,logic-correctness (Wrong protocol semantics — silent partial result)

## r-006 · medium · design · `mcp-servers/tracker/server.py:126`
tracker_transition docstring still says 'by transition id (from tracker_transitions)' though it now takes a state-map key, name or id; param still named transition_id.

- Why: The MCP tool description is the only contract agents read, so the new key/name input and the refused:true answer are undiscoverable there.
- Fix: Update the docstring to list the three accepted forms and the refused answer.
- Concern: api-contract (Vocabulary drift / Undocumented surface)

## r-007 · medium · test · `scripts/tests/test_tracker_attach.py:233`
The jira fixture stubs `transitions_config`, so the real `jira.transitions` read (afk-config load/get/project_root, the unreadable-config branch) is never run. Jira `tracker_create` with `status` (the `status_warning` path from D-9 a) has no test either.

- Why: A broken config read or a wrong create-time transition match would pass every test while the in-review move, the slice's headline use, fails live.
- Fix: Add one test that writes a .afk/config.yaml with jira.transitions and calls tracker_transition unstubbed, one for the unreadable-config error, and one for tracker_create with a known and an unknown `status`.
- Concern: test-veracity (Happy-path-only / Mock echo)

## r-008 · medium · test · `scripts/tests/test_tracker_attach.py:261`
The comment-body assertion only checks that `mediaSingle` and `mediaGroup` appear somewhere in the node kinds. It does not check which file went inline and which became a card, nor the media `id`/`collection` attrs.

- Why: A mutation that puts the .txt inline, or drops a card, or sends the wrong uuid still passes, yet the contract says images and videos are inline and other files are cards.
- Fix: Assert the full content list: two mediaSingle nodes wrapping a media node (png, mp4) and a mediaGroup holding exactly one media node (txt), with id equal to the extracted uuid.
- Concern: test-veracity (Mock echo / weak assertion on real serialized output)

## r-009 · low · design · `ADAPTERS.md:47`
The partial-failure answer (Jira files uploaded but comment failed: error + comment_error + attached) and the Jira create-time `status_warning` exception to 'refused before any write' are not stated in the tracker section; the latter appears only in jira/CONTRACT.md.

- Why: ADAPTERS.md claims an unknown value is refused before any write on every kind, which Jira create status contradicts.
- Fix: Add one sentence each to ADAPTERS.md for the partial-failure shape and the Jira create status exception.
- Concern: api-contract (Error contract absent)

## r-010 · low · spec · `ADAPTERS.md:58`
ADAPTERS.md and the CHANGELOG say every unknown-value refusal carries `refused: true`, but GitHub Issues `tracker_transition` (unchanged `_op_transition`, adapters/tracker/github-issues/api.py:221-225) still answers only `{error: True, reason}` with no `refused` or `operation`, while its sibling `_op_create` and Jira's `_refused` do add `refused: true`.

- Why: A caller (bug mode) that tells a refusal from a transport error by `refused` sees different shapes for the same in-review refusal on the two trackers, contrary to the one-verb-set promise (ADR-0004/0009) and the new doc line.
- Fix: Add `"refused": True, "operation": "tracker_transition"` to the not-in-labels return and assert `refused` in test_github_transition_to_an_unknown_state_makes_no_gh_call.
- Concern: spec-fidelity (Acceptance 5: in-review key matched against tracker's transitions; unknown key refused before any write (documented refusal shape))

## r-011 · low · correctness · `adapters/tracker/jira/api.py:559`
Possible regression: tracker_transition by raw id, and tracker_create status by name, now depend on reading .afk/config.yaml (transitions_config) before the issue's transitions are listed; an unreadable config refuses a transition that used to be posted by id with no config.

- Why: The old _op_transition posted the id directly and the old create-status matched by name from the GET alone; neither read config.
- Fix: On a config read error fall back to configured = {} and continue with name/id matching, noting the read problem in the answer.
- Concern: refactor-safety (behaviour-preservation of changed pre-existing method (Jira _op_transition and create status))

## r-012 · low · test · `scripts/tests/test_tracker_attach.py:101`
New GitHub `_op_attach` branches have no test: the `#`-in-path alt-text exclusion, an uppercase extension (`.PNG`), duplicate paths collapsed by `dict.fromkeys`, and the 2.99.0 boundary from below (only 2.99.0 and 2.92.0 are tried). Each of READ, TRIAGE and NONE is not tried either (only READ is).

- Why: The new comparisons `version < ATTACH_FLOOR` and `.lower() in ATTACHABLE` have no off-boundary cases, so an off-by-one in the floor or a case-sensitivity regression passes.
- Fix: Parametrize: version 2.98.9 refused and 2.100.0 accepted; `x#1.png` goes to unsupported; `A.PNG` is attached; a path listed twice yields one --attach.
- Concern: test-veracity (Happy-path-only (negative and boundary cases))

## r-013 · low · test · `scripts/tests/test_tracker_attach.py:283`
The failure paths of Jira `_op_attach` are untested: the upload HTTPError, the comment POST failing after a successful upload (the `comment_error` answer), and `resolve_media_uuid` raising (the 'attached but not embedded' note). The GitHub `gh issue comment` failure answer has no test either.

- Why: These carry the 'files are attached, comment failed' contract. The answer shape is documented, but nothing pins it.
- Fix: Add a route that 500s the comment POST and assert `error`, `comment_error` and the populated `attached`; add an upload 4xx case asserting no comment POST was made.
- Concern: test-veracity (Happy-path-only)

## r-014 · low · test · `scripts/tests/test_tracker_attach.py:356`
The test overwrites `api.transitions_config` and `api.state_labels` by direct assignment instead of monkeypatch. It works only because `load()` builds a fresh module each time.

- Why: If the fixture ever caches the module, the override leaks into later tests and produces order-dependent failures.
- Fix: Use monkeypatch.setattr for these overrides.
- Concern: test-veracity (Fragile test (global patching))
