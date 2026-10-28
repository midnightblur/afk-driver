# Review — 0003-repository-list — round 2 (delta 8891f99..8af71c5)

Verdict: blocking · critical 0 · high 1 · medium 5 · low 3
Roster: delta-sweep · fix-owner specialists: domain-alignment, logic-correctness, spec-fidelity, test-veracity · delta trigger: scope-and-impact (delta touches `.claude/wiring-ious.md`, outside Scope) · deferred: code-quality (lean policy → feature gate)

| id | severity | class | location | finding |
|---|---|---|---|---|
| r-001 | medium | correctness | scripts/repo_list.py:171 | an OSError or RepositoryListError from the release step escapes after the entry is already dropped |
| r-002 | medium | spec | scripts/repo_list.py:171 | a refused release leaves a marker with no entry and blocks the short name, with no decision record |
| r-003 | medium | scope | docs/afk/setup-per-repo/plan/DECISIONS.md:112 | D-16 points callers at `main_checkout`, which is in neither Produces nor 0004's Consumes |
| r-004 | medium | scope | scripts/repo_list.py:336 | the marker rollback is a second call to the safe writer's private replace |
| r-005 | low | spec | docs/afk/setup-per-repo/plan/DECISIONS.md:126 | D-18 narrows AC-003 and the glossary's "main checkout" yet records "Supersedes: none" |
| r-006 | medium | compliance | .claude/wiring-ious.md:11 | the IOU quotes 0010's Acceptance as naming remove and repoint, which it does not |
| r-007 | low | design | scripts/repo_list.py:221 | `_apart_main` uses a coined word for "separate git folder" |
| r-008 | high | test | scripts/repo_list.py:229 | the `core.worktree` branch survives being turned off: no test adds a linked worktree of a submodule |
| r-009 | low | test | scripts/repo_list.py:240 | the gone check at the end of the separate-git-folder path is never reached by a test |

Findings JSON: `0003-repository-list-8af71c5-r2.findings.json`.
