# Review — 0003-tracker-attach-82c3db8-r2

- policy: lean · delta round · activated: delta-sweep, test-veracity (delta touches tests), logic-correctness (delta over 150 lines), refactor-safety, api-contract
- verdict: findings — 2 medium, 6 low; all fixed in 20b3e5e
- mutation probe not run (tests run in CI on the human's call)
- head: 7feb708b999a000c311436ba3aa79aa89561cffc
- counts: crit=0 high=0 med=2 low=6

## r-001 · medium · correctness · `adapters/tracker/jira/api.py:777`
A failed read-back GET (stored = {error:...}) is treated as an empty attachment list, so every uploaded file is reported as a mismatch with stored filename/mimeType None.

- Why: Input: upload succeeds, GET /issue/P-1?fields=attachment returns 500 or a network error. Output: each file gets a 'was sent as X and is stored as `None` (None)' note posted in the ticket comment and a false entry in `mismatches`. The files are fine; the read-back simply failed.
- Fix: If `stored` is an error dict, skip the comparison and add one 'read-back failed, stored names not verified' note (and a field on the answer) instead of per-file mismatches.
- Concern: logic-correctness (error and rollback paths / partial-failure handling)

## r-002 · medium · test · `scripts/tests/test_tracker_attach.py:619`
The new unreadable-versions path is tested only on tracker_create; the tracker_edit branches that now write with fix_version_warning (versions unreadable, project unreadable) have no test.

- Why: The edit path was changed from refuse-on-error to write-with-warning, and a regression there (warning dropped, or a write skipped) would pass the suite.
- Fix: Add a tracker_edit test with unreadable project/versions asserting the PUT happens and fix_version_warning is set.
- Concern: delta-sweep,test-veracity (New test proves nothing)

## r-003 · low · design · `adapters/tracker/jira/api.py:667`
tracker_edit also writes with fix_version_warning when the issue's project cannot be read (or the issue GET errors), yet the docs only say 'when the project's versions cannot be read'.

- Why: The documented trigger is narrower than the real one, so callers cannot tell why the unchecked write happened.
- Fix: Word the CONTRACT.md/ADAPTERS.md line as 'when the project or its versions cannot be read'.
- Concern: api-contract (Wrong protocol semantics (warning documented narrower than behaviour))

## r-004 · low · correctness · `adapters/tracker/jira/api.py:733`
When the post-create transitions read fails, status_warning shows only the bare HTTP status (e.g. '404'); the error body and reason are dropped for the 'status' branch.

- Why: Input: tracker_create with status=in-review and the transitions GET returning an HTTP error. Output: warning reads 'was created; not moved to `in-review`: 403', which gives the caller no cause.
- Fix: Include the body or reason alongside the status, e.g. why.get('reason') or f"HTTP {why.get('status')}: {why.get('body')}".
- Concern: logic-correctness (error and rollback paths)

## r-005 · low · design · `adapters/tracker/jira/api.py:794`
A mismatch for a file missing from the upload answer is {id: None, stored: None}, a different meaning from the 'stored name/type differs' entries, and ADAPTERS.md/CONTRACT.md do not name the stored-null/id-null form.

- Why: A consumer iterating mismatches that reads mismatch['stored']['filename'] raises on the null entry.
- Fix: Document the stored: null / id: null form in jira CONTRACT.md and the MCP tool description, or add a distinguishing key such as reason.
- Concern: api-contract (Easy to misuse / error contract (inconsistent mismatch entry shape))

## r-006 · low · design · `mcp-servers/tracker/server.py:173`
tracker_create/tracker_edit/tracker_attach tool descriptions omit the new answer fields (refused, fix_version_warning, status_warning, comment_error, attached object shape); only tracker_transition was updated.

- Why: MCP callers read tool docstrings, not ADAPTERS.md, so a warning-carrying success (create/edit written despite unchecked version, issue left in first state) is easy to miss.
- Fix: Add one sentence per tool naming refused:true, fix_version_warning, status_warning and, for attach, the attached/comment_error shape.
- Concern: api-contract (Undocumented surface)

## r-007 · low · test · `scripts/tests/test_tracker_attach.py:569`
One test checks both the known-status transition and the unknown-status warning, and the unknown-status case reuses the same fake with its routes still registered.

- Why: A failure does not say which behaviour broke, and the two cases share fixture state.
- Fix: Split into two tests, one per behaviour.
- Concern: test-veracity (obscure test (eager test))

## r-008 · low · test · `scripts/tests/test_tracker_attach.py:605`
No test covers the changed _resolve_transition branch where the transitions read itself fails. The `isinstance(listed, dict)` fallback and `dict(why, operation=...)` are untested.

- Why: The refactor changed that return shape (dict error vs text reason), and a regression there would go unnoticed.
- Fix: Add a test with no transitions route (404) asserting tracker_transition answers an error with operation=tracker_transition and no write.
- Concern: test-veracity (missing negative case)
