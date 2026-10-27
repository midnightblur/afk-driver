# Review — 0003-repository-list — round 8 (delta f0ef895..9e64d3c)

Verdict: advisory · critical 0 · high 0 · medium 1 · low 3
Roster: delta-sweep · delta triggers: test-veracity (test code; 7 of 7 sampled mutants killed), logic-correctness (fix-owner of round-7 medium findings) · skipped: scope-and-impact (no path outside Scope) · deferred: code-quality (lean policy → feature gate)

| id | severity | class | location | finding |
|---|---|---|---|---|
| r-001 | medium | correctness | scripts/repo_list.py:385 | the catch around every list write also renames a marker or folder failure as a list-file failure |
| r-002 | low | smell | scripts/repo_list.py:181 | remove's release catch still lists an error the list writer can no longer raise |
| r-003 | low | correctness | scripts/repo_list.py:384 | same as r-001, seen from the change sweep |
| r-004 | low | test | scripts/tests/test_repo_list.py:762 | the dangling-link test does not check the link survives the write |

Findings JSON: `0003-repository-list-9e64d3c-r8.findings.json`.
