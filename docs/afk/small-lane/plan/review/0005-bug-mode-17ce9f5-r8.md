# Review — 0005-bug-mode-17ce9f5-r8

- policy: lean · delta round (base 17ce9f5) · activated: delta-sweep, test-veracity (tests touched), refactor-safety (modified lines) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- head: 3f83acf4f8424b463591a5a41b0f5539b914f10a
- counts: crit=0 high=0 med=1 low=0

## r-001 · medium · test · `scripts/tests/test_publish_bug_mode.py:1018`
No test lists a fold-matching name that is a different file, so the same-file check in _stored_name is unpinned

- Why: Mutants `os.path.samefile(path, path)` and `if _fold(name) == fold or os.path.samefile(...)` at publish_bug_mode.py:592 pass all 88 tests, yet on this machine's NTFS (case-blind, normalization-sensitive) they return a different file's spelling, which changes the work id D-35 says must stay one per file.
- Fix: Add a case whose listing holds a fold-matching decoy that is a different file (e.g. listed ('e\u0301.md', '\u00e9.md'), typed '\u00c9.md', samefile true only for '\u00e9.md') and assert the result is '\u00e9.md'.
- Concern: test-veracity (Happy-path-only)

- Also at this line (test-veracity, medium): No test lists a fold-matching name that is a different file, so the same-file check in _stored_name is unpinned
