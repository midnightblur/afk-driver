# Review — 0005-bug-mode-b1842ac-r6

- policy: lean · delta round (base b1842ac) · activated: delta-sweep, test-veracity (tests touched), refactor-safety (modified lines) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- head: 6679da4a2e622f1928e4c17984feddb7321088bc
- counts: crit=0 high=0 med=1 low=2

## r-001 · medium · test · `scripts/tests/test_publish_bug_mode.py:959`
The other-case test cannot fail on any CI platform: on Windows resolve() already returns the stored case, on Linux it skips

- Why: D-35 adds _stored_name because resolve() keeps typed case on macOS only, but CI runs ubuntu+windows, so wiring _stored_name into _preflight (publish_bug_mode.py:382) is guarded only by the direct unit test of the helper.
- Fix: In this test, monkeypatch mode.Path.resolve to `lambda self, strict=False: self.absolute()` (simulates macOS) before the run with `other`, so the marker assertion depends on the folder-listing lookup.
- Concern: test-veracity (Mock echo / tautology)

## r-002 · low · test · `scripts/tests/test_publish_bug_mode.py:984`
No test covers _stored_name's no-match fallthrough when the folder exists but lists no matching entry

- Why: Every assertion either finds a match or hits the scandir OSError branch, so the final `return path.name` (publish_bug_mode.py:594) can change without any test noticing.
- Fix: Add `assert mode._stored_name(tmp_path / "Export" / "missing.md") == "missing.md"`.
- Concern: test-veracity (Happy-path-only)

## r-003 · low · correctness · `skills/afk/to-ticket/scripts/publish_bug_mode.py:590`
_stored_name's fallback matches by same file (inode), so a hard-linked sibling can be returned instead of the case-variant name, giving one file two work ids

- Why: When the typed name is not listed (case-blind FS where resolve() keeps typed case, i.e. macOS per D-35), the first listed entry that is the same file wins, and a hard link with a different name is the same file, so `A.md` can hash as `0.md` while `a.md` hashes as `a.md` - the exact one-file-two-ids outcome D-35 says it closes.
- Fix: Before the samefile loop, prefer a listed name whose casefold()/unicodedata NFC form equals path.name's; use samefile only as the last resort.
- Concern: delta-sweep (New defect in the change)
