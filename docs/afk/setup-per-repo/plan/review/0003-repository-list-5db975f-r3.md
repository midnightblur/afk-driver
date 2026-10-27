# Review — 0003-repository-list — round 3 (delta 8af71c5..5db975f)

Verdict: advisory · critical 0 · high 0 · medium 1 · low 2
Roster: delta-sweep · fix-owner specialist: test-veracity · delta trigger: scope-and-impact (delta touches `.claude/wiring-ious.md` and `plan/DECISIONS.md`, outside Scope; no finding) · deferred: code-quality (lean policy → feature gate)

| id | severity | class | location | finding |
|---|---|---|---|---|
| r-001 | low | correctness | scripts/repo_list.py:302 | listing a left marker's folder can raise a raw OSError out of remove |
| r-002 | low | test | scripts/tests/test_repo_list.py:625 | the assertion that a far worktree resolves through `main_checkout` was deleted |
| r-003 | medium | test | scripts/tests/test_repo_list.py:170 | no test removes an unlisted name whose marker is unreadable; the `not held` mutant survives |

Findings JSON: `0003-repository-list-5db975f-r3.findings.json`.
