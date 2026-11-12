# The diagnosis loop

Prove the cause of a bug before the page round. Change no product code in this loop: a probe is a test, a log line or a run that you remove again.

## The steps

1. **The merge first.** The bug started after a merge: read the diff of that merge before anything else.
2. **A fast loop.** Make 1 pass/fail check that runs in seconds and shows the symptom: a test, a request or a script.
3. **The exact symptom on a clean base.** Reproduce the symptom of the report, word for word, on a clean checkout of the base. A nearby failure is not the bug.
4. **The path.** Trace the path from the entry point to the symptom. Cite each file and line.
5. **Hypotheses.** Write 3 to 5 hypotheses, ranked by likelihood, each with the probe that would disprove it.
6. **1 change per probe.** Run the probes in rank order. Change 1 thing per probe, and keep the fast loop the judge.
7. **The verdict.** End in 1 of the 5 verdicts below, and record it with `diagnose`.

## The 5 verdicts

| Verdict | Meaning | Next |
|---------|---------|------|
| `one-fix` | 1 proven cause and 1 fix | the page round shows the fix |
| `several-fixes` | 1 proven cause and more than 1 fix | the page round shows each fix as 1 option |
| `spec-gap` | the spec does not say what is right | the page round names the gap and its writer; no fix before the developer decides |
| `works-as-specified` | the code does what the spec says | the page round says so; a change is an enhancement |
| `cannot-reproduce` | the symptom does not show on a clean base | the page round shows each probe and what it found |
