# Review — 0001-diagnosis-format-60325bc-r3

- policy: lean · delta round · activated: delta-sweep, test-veracity (delta touches tests) · no fix-owner specialists (no critical/high remediated in r2) · scope-and-impact: inline Scope grep, no hit
- test-veracity: no findings; mutation probe 5 run, 5 killed
- head: 6e182ba2ae1b6cbfab5495fa4f5b88ce0f56213b
- counts: crit=0 high=0 med=0 low=1

## r-001 · low · correctness · `skills/utils/diagnose/scripts/diagnosis_file.py:33`
The appender splits lines at \n only, but the checker side (diagnosis_file.py:33 and :44) still uses str.splitlines(), which also breaks on \x0c, \x85, \u2028 and a lone \r.

- Why: A form feed or Unicode line separator inside an entry is one line to append_outside_write and listed, but two lines to the checker, so the checker can flag or miss an entry the writer just appended.
- Fix: Share one line-splitting helper in diagnosis_file.py and call it from both modules.
- Concern: delta-sweep (New defect in the change (sibling path keeps old behaviour))
