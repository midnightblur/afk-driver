# Review — 0005-bug-mode-6285cac-r4

- policy: lean · delta round (base 6285cac) · activated: delta-sweep, test-veracity (tests touched), refactor-safety (modified lines) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- head: 8268faa08761049dd08a7880033219e0ddb1ceb0
- counts: crit=0 high=0 med=3 low=3

## r-001 · medium · test · `scripts/tests/test_publish_bug_mode.py:878`
No test re-runs one description file, so D-33's 'a re-run of the same file gets the same id' is unproven, and a duplicate ticket slips through

- Why: The new hash covers the unresolved `source.name` (publish_bug_mode.py:382). A probe on a copy of HEAD, on Windows, ran docs/Export/DESCRIPTION.md and then the same file as docs/Export/description.md. It printed work ids `export_description-e09bf8f8` and `export_description-dd31686b`, and the stub held issues ['1', '2']: two tickets for one file. The added tests only show that different files get different ids.
- Fix: Add a test that runs one description file twice, once through another spelling of its path (skip where the file system tells case apart), and assert a single ticket.
- Concern: test-veracity (open-question)

## r-002 · medium · correctness · `skills/afk/to-ticket/scripts/publish_bug_mode.py:382`
Description work id hashes the caller's spelling of the file name, so a re-run of the same file through a differently-cased path files a duplicate ticket

- Why: The folder half comes from `source.resolve()` (on-disk case) but the hashed file name is the unresolved `source.name`; on a case-insensitive filesystem (Windows, default macOS) the same file gets a new digest, the marker search misses, and a second ticket is created; the D-31 slug form lower-cased both halves so this is a regression, and it contradicts D-33 'A re-run of the same file gets the same id'.
- Fix: Resolve once (`resolved = source.resolve()`) and hash `f"{resolved.parent.name}/{resolved.name}"` (slug `resolved.stem`), plus a test that re-runs the file via a differently-cased path.
- Concern: delta-sweep,refactor-safety (New defect in the change)

- Also at this line (delta-sweep, medium): Description work id hashes the caller's spelling of the file name, so a re-run of the same file through a differently-cased path files a duplicate ticket

## r-003 · medium · correctness · `skills/afk/to-ticket/scripts/publish_bug_mode.py:416`
The new 'names no ticket' refusal skips an empty `--key`, which still silently creates a new ticket

- Why: `if key and not given` treats `key=""` as no key at all, so `--key "$KEY"` with an empty variable creates (and moves the spec folder for) a fresh ticket instead of refusing, while `--key " "` and `--key #` are refused — the fix covers one sibling input and not the other.
- Fix: Test `key is not None` (`if key is not None and not given: raise Refused(...)`) and add `""` to the parametrized refusal test.
- Concern: delta-sweep (New defect in the change)

## r-004 · low · test · `scripts/tests/test_publish_bug_mode.py:161`
StubGitHub rewrites `ticket_key` before the shared stub records the call, so `stub.calls` no longer shows the key the code sent. Its copy of the adapter's `_number` is hand-written

- Why: A test reading `stub.calls` cannot tell whether the code sent `#5` or `5`. The hand copy can drift from `adapters/tracker/github-issues/api.py:_number`, which also strips leading `#`.
- Fix: Record the raw payload and normalize only for the stub's own lookup, or import the adapter's `_number` for the normalization.
- Concern: test-veracity (Fragile test)

## r-005 · low · test · `scripts/tests/test_publish_bug_mode.py:919`
The 'names no ticket' refusal is tested only on GitHub spellings; the edge values (an empty `--key ""`, a blank Jira key) are not tested

- Why: The new check is `if key and not given:` (publish_bug_mode.py:416). An empty string skips it without any test noticing. A probe found that a Jira `--key "   "` is refused, but no test pins that.
- Fix: Add `""` and a Jira blank key to the cases, and assert either a refusal or the documented no-key behaviour, plus no writes.
- Concern: test-veracity (Happy-path-only)

## r-006 · low · spec · `skills/afk/to-ticket/scripts/publish_bug_mode.py:417`
New pre-write refusal is missing from BUG-MODE.md's 'Refusals, before any write' list

- Why: The documented refusal list is the reader's enumeration of exit-1 causes (AGENTS.md Freshness: no plugin-source artifact may go stale); a `--key` that normalises to nothing never reaches the tracker, so 'a given or recorded key the tracker does not return' does not describe it.
- Fix: Add 'a `--key` that names no ticket in the tracker's spelling (empty, `#`, `owner/repo#`)' to BUG-MODE.md 'Refusals, before any write'.
- Concern: delta-sweep (Documented-rule breach in changed lines)
