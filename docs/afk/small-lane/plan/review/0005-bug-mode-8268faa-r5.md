# Review — 0005-bug-mode-8268faa-r5

- policy: lean · delta round (base 8268faa) · activated: delta-sweep, test-veracity (tests touched), refactor-safety (modified lines) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- head: b1842ac6e99ba7b4bfbd7754bf49cf0572a3e74c
- counts: crit=0 high=0 med=1 low=1

## r-001 · medium · correctness · `skills/afk/to-ticket/scripts/publish_bug_mode.py:381`
Path.resolve() returns the stored letter case only on Windows; on a case-insensitive POSIX file system (default macOS, which bootstrap.sh supports) two spellings of one description file still get two work ids, so a re-run files a second ticket

- Why: D-34 rests on 'the resolved path carries the stored spelling', but posixpath.realpath only follows symlinks and keeps each part exactly as typed, so the round-4 case-insensitivity fix holds on Windows alone and the new test fails on macOS instead of skipping (`other.exists()` is True there).
- Fix: Take the stored names from the directory itself, e.g. pick the os.scandir(parent) entry for which os.path.samefile(entry, source) is true (same for the folder), rather than relying on resolve() to normalise case.
- Concern: delta-sweep,refactor-safety,test-veracity (New defect in the change)

- Also at this line (delta-sweep, medium): Path.resolve() returns the stored letter case only on Windows; on a case-insensitive POSIX file system (default macOS, which bootstrap.sh supports) two spellings of one description file still get two work ids, so a re-run files a second ticket

- Also at this line (delta-sweep,test-veracity, medium): Path.resolve() returns the stored letter case only on Windows; on a case-insensitive POSIX file system (default macOS, which bootstrap.sh supports) two spellings of one description file still get two work ids, so a re-run files a second ticket

## r-002 · low · test · `scripts/tests/test_publish_bug_mode.py:958`
One test checks two behaviours and a mid-body `if ... pytest.skip` decides whether the second (the only half that guards the delta) runs

- Why: The first half (same path re-run) passed before this delta too, so on a case-sensitive file system the test reports `skipped` after asserting nothing the delta changed, and a reader cannot tell from the name which half guards D-34.
- Fix: Split into a plain same-path re-run test and a case-variant test whose case-sensitivity check sits in a `skipif`/fixture before any assertion.
- Concern: test-veracity (Conditional test logic)
