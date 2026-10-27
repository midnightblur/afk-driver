# Review — 0003-repository-list — round 6 (delta 4452828..73bb386)

Verdict: advisory · critical 0 · high 0 · medium 2 · low 2
Roster: delta-sweep · delta triggers: test-veracity (test code; 8 of 10 sampled mutants killed, 1 equivalent), logic-correctness (10 files), scope-and-impact (`plan/DECISIONS.md` outside Scope; no finding) · deferred: code-quality (lean policy → feature gate)

| id | severity | class | location | finding |
|---|---|---|---|---|
| r-001 | medium | correctness | scripts/repo_list.py:373 | a list file that is a folder is refused on read only; add, remove and repoint still raise a raw error |
| r-002 | low | correctness | scripts/repo_list.py:113 | `find_entry` still reads a blank path or root as the current folder |
| r-003 | medium | test | scripts/repo_list.py:386 | removing the retry wait survives: the tests zero the wait |
| r-004 | low | test | scripts/repo_list.py:384 | the other-read-error branch is not reached by a test on Windows |

Findings JSON: `0003-repository-list-73bb386-r6.findings.json`.
