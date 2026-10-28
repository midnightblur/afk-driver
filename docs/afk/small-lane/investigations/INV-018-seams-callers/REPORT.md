# INV-018 — L9 seams: callers of the fix (execute, hands-off authorization, preflight, smoke gate, journal)

`d346cfb · partial · boundaries 0/14 closed · 513 nodes · 36 claims · 1 load-bearing unverified` (ledger `COVERAGE.json`). Frontier B14: live `gh pr edit --body` / `glab mr update --description`, change-description readers in other repositories. Written by the orchestrator from the run's reply; the run's own write was refused.

Seed narrowed to `afk:subtasks` + `change-update-body` (a wider seed ran >30 min, killed); other sites from direct reads + concept search. Fragments: tracer p1 (all classes) + blind counter-search cs1 (B1, B4, B13).

## Seam rows (draft)

| Seam | Existing contract | Planned change | Impacted | Verdict |
|---|---|---|---|---|
| execute Steps 8/10/10.5/14 + out-of-slice sibling | Step 8 red → one retry → `/afk:fix`, `design_conflict` → Step 14 (`execute/SKILL.md:67`); Step 10 routes by class (`:77-79`); 10.5 remediates (`:93`); statuses `:120-133`, cited `CITED-MODE.md:144-161`; out-of-Scope → `blocked`, no Step 14 row (`:79,147`; INV-005); no tracker (`:12`); one worktree (`:16`); push "this branch" (`:30`); "only context that commits" (`:142`); owns checklist block, JOURNAL, DECISIONS (`:151`) | Steps point at shared fix procedure; sibling file: diagnosis, verdict routes, second worktree off base, cherry-pick, dependency block, journal lines | `test_execute_step_pointers.py:44` (dead step numbers fail); `test_fail` text "/afk:fix pass" (`:123`); mission-control insights regex (`insights.py:23`, `test_insights.py:18`) | reworked |
| hands-off authorization | `DECISIONS.md:23` external write disqualifies two-way door; `:25` hard boundaries "merge, Jira, branches beyond the feature branch"; `:8` automation stops at consent boundaries (covering B-9 inferred); autopilot "no Jira" (`autopilot/SKILL.md:24,64`; `SUBAGENT-PROMPT.md:28-29`); execute driven "this branch" (`execute/SKILL.md:30`) | AC-028 prior approval covers ticket + separate-change writes | lines: `DECISIONS.md:23,25`, `autopilot:24,64`, `SUBAGENT-PROMPT:28-29`, `execute:12,30,142`, README `:127,860-861`; `to-ticket/SKILL.md:99` (no driven mint — bug mode own rule); AGENTS.md:195 names execute + smoke-test, not autopilot (corrects AUDIT-L9 chain #1); no tests pin | reworked |
| preflight PF-3/PF-4 + change-description blocks | PF-3 / PF-4 route correctness/spec → `/afk:fix` (`preflight/SKILL.md:99,125`), no fix result routed, fixed park reasons (`:70-169`), PF-3 outside cap (`:233-240`); PF-5 owns `afk:preflight-evidence`, "each writer owns exactly one block" (`:181-186`); `change-update-body` replaces whole body (github `forge.sh:412`, gitlab `:440`, Draft restore `:445-458`); body only from `change-fetch` (github `:315,331`), not `change-view` (`:146`) — INV-010 REPORT.md:14 wrong for GitHub; no read-before-update in execute `:63,81` or PF-5 | execute-owned dependency block; change-fetch before update (D-20); procedure results → PF park reasons | second execute block breaks "exactly one block per writer" (`:186`) | extends |
| smoke gate in-place fix (B-6) | owns gate surface, journal, INDEX row (`smoke-test/SKILL.md:77`); no Jira (`:78`); authors no specs (`:79`); never patches to green (`:80`); "not by patching here", "no silent retry" (`:53`); autopilot `:67`; `fix/SKILL.md:10` already names smoke follow-up | call shared procedure per failing scenario | commit authorization (autopilot per-subtask only `:24`; by-hand run none); no slice review/adversary covers it (only preflight PF-3 feature review) | reworked |
| autopilot report + journal grammar | report `autopilot/SKILL.md:49-58` (`parked:`, `decisions:`, `issues:`), no separate-change line; subagent report verbatim, only `OUTCOME:` parsed (`SUBAGENT-PROMPT.md:41`); events `JOURNAL-FORMAT.md:31-37`, none for ticket written / separate change / defect parked (`:33`) | new events + report line | mission-control parser generic (`mc/journal.py:10-13`); grammar pinned (`test_contract.py:90,306`) | extends |

## Landmines

- Second worktree via `scripts/create-worktree`, never bare `git worktree add` (`:16`); branch passes `git.branch-pattern` + gate.
- Commit gates 600000 ms timeout; never `--no-verify`/`--force` (`:61,145`).
- Recorded reasons live under the per-worktree git dir (`forge_ledger.py:1681-1683`); B-9 worktree reasons never reach the feature worktree's `rationale-verify` (`:106`) → post on the separate change (inferred).
- Cherry-pick commit prefix: keeping `[{NNNN-slug}]` joins the slice review diff (`review/SKILL.md:22`) → out-of-Scope files raise `scope` → `blocked` (`:79`); without it only the feature review sees it. Design must pick.
- Re-run from Step 8 after the cherry-pick. Draft assignee from `mrAssignee` (`:17`). A finding outside the slice diff cannot close the settle loop (INV-005, `forge_ledger.py:1534`). `design_conflict` cited-mode only → V-4 uncited needs `needs_decision`.
- Hands-off: keep "never merge", "no force push"; each auto decision gets `D-{n}` in `plan/DECISIONS.md` + `decision(D-{n})` journal line (`:35-48`).
- PF-3: V-2, V-3, V-5 have no fitting park reason (`review_stalemate` wrong); V-4 → settle-loop dispute (inferred). Same read-before-write gap today for checklist + evidence blocks. No test names `change-update-body`, `afk:subtasks`, `preflight-evidence`.
- Smoke: comment gate + rationale add/post/verify; rebuild the app (reuse flag invalid after a code change, `autopilot:36`); full re-run before stamping (scoped never stamps, `:29`); B-7 vs "no silent retry" (`:53`); new journal events (`JOURNAL-FORMAT.md:35`).
- New execute journal token = same-commit edit to JOURNAL-FORMAT; AGENTS.md lists its writer set.

## Existing drift (independent of the design)

AGENTS.md:179, README:838 omit the preflight-evidence block; JOURNAL-FORMAT:51-55 omits `unhomed_product_debt` (`preflight:169`); "only execute auto-commits" (`execute:142`, README:860) already false — PF-4b commits (`preflight:132-133`).

## Unverified

Load-bearing: GitLab `glab mr view -F json` (`forge.sh:324`) holds `description` — not checked live. B1 partial (alias/wire forms); B3, B5–B7, B10 no method; seed boundary statuses won the fold.

## Fold notes (plugin defects)

296 seed placeholders dropped; 15 sites found by both fragments under different `query_id` refused — cs1 copies dropped.
