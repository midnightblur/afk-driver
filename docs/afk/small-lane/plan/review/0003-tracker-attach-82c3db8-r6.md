# Review — 0003-tracker-attach-82c3db8-r6

- policy: lean · delta round after the adversary fix 297ef3c · activated: delta-sweep, test-veracity (delta touches tests), refactor-safety (modified lines)
- verdict: findings — 1 medium, 1 low; both fixed in 396d378
- mutation probe run by hand on each new test: each fails without its fix
- head: 297ef3c29620b1d8c05b7101a954e2da19771f0f
- counts: crit=0 high=0 med=1 low=1

## r-001 · medium · test · `scripts/tests/test_tracker_attach.py:115`
The UTF-8 regression test passes without the fix on any host whose locale is already UTF-8.

- Why: Deleting encoding="utf-8" from _gh leaves the test green on Linux, macOS and UTF-8 Windows, so CI's Linux job does not guard the bug.
- Fix: Assert the adapter passes encoding utf-8 to subprocess.run, or force a cp1252 default so the unfixed code fails everywhere.
- Concern: test-veracity (Mutation probe (test passes without the fix))

## r-002 · low · test · `scripts/tests/test_tracker_attach.py:664`
No test covers a read-back list holding non-object entries or a non-object fields value.

- Why: The malformed read-back test uses a string, which the isinstance(listed, list) clause already rejects; removing the all(isinstance(a, dict)) clause leaves every test green.
- Fix: Add cases with attachment ["x"] and a non-object fields value, expecting read_back false and ok true.
- Concern: test-veracity (Missing negative case)
