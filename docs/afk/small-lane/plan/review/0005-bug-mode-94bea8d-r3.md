# Review — 0005-bug-mode-94bea8d-r3

- - policy: lean · delta round (base 94bea8d) · activated: delta-sweep, logic-correctness (delta over 150 lines), test-veracity (tests touched), refactor-safety (modified lines), scope-and-impact (Scope grep hit) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- head: 6285caca04a3a5f3dbd7994f0b88cae65c6a9a66
- counts: crit=0 high=0 med=3 low=3

## r-001 · medium · test · `scripts/tests/test_publish_bug_mode.py:866`
The 'take the recorded spelling' branch (D-31 b) is untested: every case records an already-canonical key

- Why: Mutation probe on a temp copy deleting publish_bug_mode.py:412-413 (`given = recorded`) left the suite green, because in both parameter rows key_of(recorded) == recorded, so a hand-recorded `#5` or `proj-5` that would be treated as a different ticket (new `-{key}` evidence marker, extra `ticket:` line) is never exercised.
- Fix: Add rows where the recorded key is non-canonical (GitHub recorded "#5" given "5"; Jira recorded "proj-5" given "PROJ-5") and assert one comment and no `ticket:` line.
- Concern: test-veracity (Happy-path-only (Meszaros))

## r-002 · medium · correctness · `skills/afk/to-ticket/scripts/publish_bug_mode.py:379`
The slugged description work id maps distinct file names in one folder to the same id, so the second description is never filed and the run still exits 0

- Why: `_slug` folds case and turns every non-`[a-z0-9-]` run into `-`, so `bug-report.md`, `bug report.md`, `bug.report.md` and `Bug-Report.md` all share the create marker `afk-evidence adhoc_bug-report ticket`. The read-first search then answers the second run with the first ticket. Before this delta, `bug.report` and `Bug-Report` gave distinct ids and `bug report` was refused.
- Fix: Keep the id collision-free: refuse a stem whose slug differs from the stem, or add a short hash of the raw stem when the slug changed it.
- Concern: delta-sweep,logic-correctness,refactor-safety (New defect in the change)

- Also at this line (delta-sweep, medium): The slugged description work id maps distinct file names in one folder to the same id, so the second description is never filed and the run still exits 0

- Also at this line (delta-sweep,logic-correctness, medium): The slugged description work id maps distinct file names in one folder to the same id, so the second description is never filed and the run still exits 0

## r-003 · medium · test · `skills/afk/to-ticket/scripts/publish_bug_mode.py:535`
No test proves _hold keeps two same-named proof files apart; flattening the per-file subfolder survives the suite

- Why: Mutation probe on a temp copy (drop `os.mkdir(spot)` and join to plan.staged directly, or use one fixed subfolder) left all bug-mode tests green, yet the second `run.png` then overwrites the first and both uploads carry the same bytes; test_two_proof_files_with_one_name_upload_under_two_names writes distinct contents (b"a", b"b") but asserts only the basenames.
- Fix: In the two-same-name test, have the stub read each attached file's bytes at tracker_attach time and assert they are [b"a", b"b"] in order.
- Concern: test-veracity (Happy-path-only (Meszaros))

## r-004 · low · scope · `scripts/tests/test_outside_writes.py:331`
Out-of-Scope edit to the outside-writes helper and its tests goes past the bound D-30 recorded, and no decision extends it

- Why: D-30 lifts Scope for test_outside_writes.py for 'two tests only' and for outside_writes.py for the rename plus retry, yet this delta adds a third test and changes replace_text's handling of tries<=0, while D-31 names only publish_bug_mode.py and BUG-MODE.md.
- Fix: Amend the record: append a decision (or extend D-31's Supersedes) that names the tries clamp in outside_writes.py:160 and the third test in test_outside_writes.py:331.
- Concern: scope-and-impact (every changed path matches a ## Scope glob (out-of-scope file = finding))

## r-005 · low · test · `scripts/tests/test_publish_bug_mode.py:742`
The patched _resolve_folder is never called by any command-line test, so main's new `resolve=_resolve_folder` is unproven

- Why: Mutation probe on a temp copy reverting publish_bug_mode.py:856 to omit `resolve=` left the suite green: no command-line test creates a ticket (all pass --key, dry-run, or are refused), so no folder move runs and the patch guards nothing.
- Fix: Add a command-line test without --key that creates a ticket and asserts the diagnosis landed at tmp_path/docs/<created key>/DIAGNOSIS.md through the patched resolver.
- Concern: test-veracity (Mock echo / tautology (Meszaros))

## r-006 · low · correctness · `skills/afk/to-ticket/scripts/publish_bug_mode.py:148`
On GitHub, a given key that normalises to empty (`#`, `owner/repo#`) is dropped silently, and the run creates a new ticket

- Why: `key_of` returns `""` for these, `given` becomes falsy, and the run falls through to the recorded key or to a create. Before this delta, the raw key went to `tracker_get` and was refused.
- Fix: Refuse when `--key` was passed but `key_of(key)` is empty: "`--key` names no ticket".
- Concern: delta-sweep (New defect in the change)
