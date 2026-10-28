# Review — 0001-diagnosis-format-190105b-r2

- policy: lean · delta round · activated: delta-sweep, logic-correctness (fix owner of a high), test-veracity (delta touches tests) · scope-and-impact: inline Scope grep, no hit · deferred: code-quality, agents-md-compliance (→ feature gate)
- logic-correctness: no findings
- head: 60325bcd7894b60b3392adefcb7702bef655047e · mutation probe: 22 run, 16 killed
- counts: crit=0 high=0 med=1 low=5

## r-001 · medium · test · `skills/utils/diagnose/scripts/check_diagnosis.py:78`
No test feeds check_diagnosis an Outside writes line that is not a list item; the new `not a list item` branch is unpinned.

- Why: Replacing the message with None survives all tests; refusal of a prose line in Outside writes is never asserted.
- Fix: Add a test with an Outside writes line without a dash; assert not ok and a problem containing `not a list item`.
- Concern: test-veracity (assertion-strength: happy-path-only (Meszaros))

## r-002 · low · correctness · `skills/utils/diagnose/scripts/outside_writes.py:123`
Line-end detection uses splitlines(keepends=True), which also breaks on form feed, \x1c-\x1e, \x85, U+2028/2029; an entry ending in such a character gets the new entry glued onto its physical line.

- Why: append on `- ticket: 12\x0c\n` yields `- ticket: 12\x0c- in-review: 12\x0c\n`: two entries on one physical line.
- Fix: Split lines on \n only in _read_lines; test a form feed at the end of the last entry.
- Concern: delta-sweep (New defect in the change)

## r-003 · low · smell · `skills/utils/diagnose/scripts/diagnosis_file.py:16`
BOM is a literal invisible U+FEFF inside the quotes, not an escape.

- Why: A tool that strips zero-width characters turns BOM into an empty string and the BOM logic misbehaves silently.
- Fix: BOM = "\ufeff"
- Concern: delta-sweep (Smell introduced by the change)

## r-004 · low · test · `scripts/tests/test_check_diagnosis.py:219`
The BOM test puts the BOM before `# Diagnosis`, not a `## ` heading, so the BOM never touches the code under test.

- Why: Removing the BOM strip in sections() and repeated() both survive.
- Fix: Put the BOM directly before a `## ` heading and assert ok.
- Concern: test-veracity (assertion-strength: test does not exercise the behaviour it names)

## r-005 · low · test · `skills/utils/diagnose/scripts/check_diagnosis.py:97`
No test gives a State row whose Read from names only a backticked non-kind word (a typo).

- Why: Dropping `& kinds` survives; a typoed kind would match nothing instead of failing the format.
- Fix: Add a _format_with case swapping a kind for an unknown backticked word; expect exit 2.
- Concern: test-veracity (assertion-strength: happy-path-only (Meszaros))

## r-006 · low · test · `scripts/tests/test_outside_writes.py:216`
read_first tests never assert Outcome.attempts; the read-first path's attempts=0 is unpinned.

- Why: `_read(read_back, 0)` -> `_read(read_back, 1)` survives.
- Fix: Assert outcome.attempts == 0 in the find-unlisted-write test.
- Concern: test-veracity (assertion-strength: weak assertion)
