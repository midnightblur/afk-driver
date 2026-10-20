# Review — 0001-diagnosis-format-3efbfeb-r1

- policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (complex), design-quality + resilience (opt-in) · skipped: refactor-safety, domain-alignment, api-contract (no trigger) · deferred: code-quality, agents-md-compliance (→ feature gate)
- verified: 1 upheld / 1 downgraded / 0 dropped (r-007 refuted on its design half; logic-correctness co-owns it, so it is posted and disputed)
- head: 190105b16b7156b17fbeb3871fceaf7163147077 · mutation probe: 29 run, 28 killed
- counts: crit=0 high=1 med=5 low=9

## r-001 · high · correctness · `skills/utils/diagnose/scripts/outside_writes.py:130`
_section ignores code fences, unlike diagnosis_file.sections, so a fenced `## Outside writes` or `## ...` line in Reproduction misplaces the append

- Why: A Reproduction fence holding pasted output with a `## Outside writes` line makes start point inside the fence, so the entry is inserted into Reproduction while the checker still sees Outside writes empty (a re-run repeats the outside write).
- Fix: Track fences in _section exactly as sections() does (share one scanner in diagnosis_file.py).
- Concern: logic-correctness (boundary inputs: fenced blocks)

## r-002 · medium · test · `scripts/tests/test_check_diagnosis.py:126`
No test lists both a push and a change entry, so the first-match order of Shipped before Landed is unpinned.

- Why: The format file's State table says the first matching row wins, and a swap of the push and change rows in STATE_BY_KIND passes every test.
- Fix: Add a parametrized case with Outside writes holding both `- push: ...` and `- change: ...` that expects Shipped (and push+in-review expecting In review).
- Concern: test-veracity (Happy-path-only / missing boundary cases)

## r-003 · low · design · `skills/utils/diagnose/scripts/check_diagnosis.py:24`
Possible information leakage: State table order and kind/verdict mappings live in DIAGNOSIS-FORMAT.md and again as hardcoded STATES/STATE_BY_KIND/STATE_BY_VERDICT, though the docs say scripts read the tables, never a copy.

- Why: A state-row change needs lockstep edits in two places and only the order is test-guarded, so mappings can drift silently. (verify pass: downgraded; the Read from column is prose, so the defect is the overstated never-a-copy claim)
- Fix: Derive precedence and mappings from table(fmt, State), or make the tuple the single owner and drop the claim.
- Concern: design-quality (Information Leakage (APoSD))

## r-004 · medium · correctness · `skills/utils/diagnose/scripts/check_diagnosis.py:49`
File read as plain utf-8 keeps a leading U+FEFF, so the first heading never matches

- Why: A DIAGNOSIS.md saved with a BOM starts `\ufeff## Work id`, HEADING fails, and the checker refuses it with `missing: Work id`; outside_writes._section has the same blind spot on line 1.
- Fix: Read with encoding="utf-8-sig" (check, listed, append; preserve the BOM on write).
- Concern: logic-correctness (boundary inputs: BOM)

## r-005 · medium · design · `skills/utils/diagnose/scripts/outside_writes.py:60`
A re-run after a crash between a successful write and its append repeats the write

- Why: The helper writes first and reads back only after a failure, so an unlisted write that took effect is sent again on the re-run (SDD §4: a re-run reads back the rest before retrying).
- Fix: Offer a read-back-first mode the re-run path uses.
- Concern: resilience (idempotency)

## r-006 · medium · correctness · `skills/utils/diagnose/scripts/outside_writes.py:68`
Docstring says any non-failed read-back answer means 'took effect', but failed() treats every non-dict answer as 'cannot tell'

- Why: A read_back returning a truthy string/True/list (e.g. the found key) is classified as failure, so the write is neither retried nor recorded; a search answer `{"issues": []}` (zero hits, a dict) counts as 'took effect'.
- Fix: Define read_back as None or an object, test only dict error/unavailable/unsupported for 'cannot tell', and document that an empty search must be mapped to None by the caller.
- Concern: logic-correctness (error paths: read-back contract)

## r-007 · medium · correctness · `skills/utils/diagnose/scripts/outside_writes.py:106`
Append is an unlocked read-modify-write; atomic replace does not prevent lost updates

- Why: Two writers appending `push:` and `evidence:` at once both read the old file and the later os.replace drops the earlier entry, so a re-run repeats that outside write.
- Fix: Hold an exclusive sidecar lock (O_EXCL) around read..replace, or re-read and verify the entry after replace.
- Concern: logic-correctness,resilience (concurrency/ordering)

## r-008 · low · scope · `docs/afk/small-lane/plan/DECISIONS.md:7`
D-1 narrows the state derivation, but its Supersedes line says none and the Acceptance bullet citing the §6 Read from table stands unamended

- Why: DECISIONS.md: a Supersedes line overrides the exact passage it quotes; D-1 quotes none, so the contract bullet still demands every §6 row.
- Fix: Record the superseded passage (contract Acceptance bullet + SDD §6 rows Fixed and grill return) in a new ledger entry.
- Concern: scope-and-impact (open-question)

## r-009 · low · correctness · `skills/utils/diagnose/scripts/check_diagnosis.py:105`
STATE_BY_VERDICT is a hardcoded copy; a verdict row added to the format table raises KeyError, short table rows raise IndexError, both outside the (OSError, UnicodeDecodeError, ValueError) handler

- Why: A V-6 row in 'Required parts per verdict' passes the required check then crashes with a traceback (exit 1, no DIAGNOSIS line) instead of exit 2.
- Fix: Derive the verdict-to-state map from the State table, or catch KeyError/IndexError and exit 2.
- Concern: logic-correctness (error paths: uncaught exit code)

## r-010 · low · correctness · `skills/utils/diagnose/scripts/diagnosis_file.py:26`
A repeated heading resets the part (last wins) while outside_writes._section uses the first

- Why: Two `## Outside writes` headings: the checker reads only the second (dropping earlier entries and the derived state) while the helper appends to the first; a duplicate empty `## Approval` erases a filled one.
- Fix: Report a duplicate part heading as a problem in check and use one scanner in both files.
- Concern: logic-correctness (duplicate headings)

## r-011 · low · design · `skills/utils/diagnose/scripts/outside_writes.py:22`
Possible information leakage: the Outside writes entry grammar is re-implemented in two modules (ENTRY regex in each) and the evidence-marker grammar is enforced only by the appender, so the checker accepts entries the appender refuses.

- Why: One format decision has two owners that can diverge, and the validator is weaker than the writer.
- Fix: Move the entry regex and evidence check into diagnosis_file.py; both modules call them.
- Concern: design-quality (Information Leakage (APoSD))

## r-012 · low · design · `skills/utils/diagnose/scripts/outside_writes.py:36`
Possible divergent change: one module holds the DIAGNOSIS.md appender and the generic adapter-answer failed() test plus retry loop, which share no data and change for different reasons.

- Why: Slices 0005 and 0007 use retry/failed with no diagnosis file yet import a module named for diagnosis writes.
- Fix: Split retry_with_read_back/failed into their own module if SDD 8 allows; keep both entry points.
- Concern: design-quality (Divergent Change (Fowler) / Grab-bag cohesion (CC2))

## r-013 · low · correctness · `skills/utils/diagnose/scripts/outside_writes.py:108`
splitlines then join rewrites every earlier line break

- Why: A file with a form feed, U+2028, NEL, lone CR or mixed LF/CRLF inside a pasted reproduction is normalized to one newline style (CRLF if any CRLF exists), breaking 'earlier lines are never changed'.
- Fix: Split on \r\n|\n only, keep each line's own terminator, insert the new line with the section's terminator.
- Concern: logic-correctness (append-only: earlier lines never changed)

## r-014 · low · correctness · `skills/utils/diagnose/scripts/outside_writes.py:141`
mkstemp makes a 0600 file that replaces the diagnosis, losing its original mode

- Why: On POSIX a committed 0644 DIAGNOSIS.md becomes 0600 after one append, showing as a mode change in git.
- Fix: shutil.copymode(path, tmp) before os.replace.
- Concern: logic-correctness (file mode on replace)

## r-015 · low · design · `skills/utils/diagnose/scripts/outside_writes.py:145`
An os.replace failure after a successful outside write leaves the write unrecorded

- Why: The caller gets an exception, the entry is missing, and a re-run repeats the write.
- Fix: Document the caller's recovery: read back before re-sending.
- Concern: resilience (failure story)
