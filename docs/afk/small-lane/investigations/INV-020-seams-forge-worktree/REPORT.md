# INV-020 — L9 seams: forge ship script, feature-branch landing, diagnose worktree, outside-writes helper

Verdict: `partial` @ d346cfb (ledger `COVERAGE.json`, validator exit 0; 4/14 classes closed, 5137 nodes, 69 claims). Frontier B14: live gh/glab behaviour, other repositories. Written by the orchestrator from the run's reply; the run's own write was refused.

## Seam rows (draft)

| Seam | Existing contract | Impacted | Verdict |
|---|---|---|---|
| fix ship script open/ready/land | `afk_adapter` passes exit + stdout (`hooks/lib/adapter.sh:29-62,108-113`), dispatch failure exit 2, empty stdout (`:40-49`); only Python dispatcher `forge_ledger.py Adapter.call` (`:760-771`) raises on non-zero, 120 s timeout (`:740`), one stdout line (`:691-694`) → cannot route ci-wait; importable by path (`test_forge_adapters.py:942-945`) | `execute:17`; `preflight:192-235`; `FIXER-PROMPT.md:31-33` (removed); `forge_ledger.py:1901`; `gc-check.sh:136` | extends |
| feature-branch landing | `git push` (all forms) not a guard mutation (`shell_mutations.py:23-24,431`); `rebase`/`update-ref` judged at their worktree (`protected_branch_guard.py:291,309,575`); backstop reads `rebase-merge/head-name` only (`git-backstop.py:51-84`); branch-name gate skips remotes (`branch-name-gate.sh:63-65`); no pre-push hook (`install-git-hooks.sh:101-102`) | executor's local feature branch after landing (`execute/SKILL.md:63`) | fits + must-dos |
| diagnose worktree | `create-worktree --name N --base REF`; placeholders take N verbatim, else `worktree-N` (`:208-218`); base only `rev-parse --verify`, never fetches (`:420-429`); lock, owner record, provision, `WORKTREE_PATH=` (`:361-516`); here `feat/{ticket_lower}` → `feat/bug-foo` matches (`.afk/config.yaml:19-20`) | remove-worktree keep rules (`:121-205,210,291-296`); `/afk:gc` needs PLAN.md (`gc-check.sh:99-143`); raw `worktree remove` in `gc/SKILL.md:76`, `settle-change:102` | extends |
| shared outside-writes helper | modules loaded by path (`publish_bug.py:50-56`; importlib `contract.py:195`); cross-skill precedents (`validate_plan.py:190-203`, `check_sdd_investigations.py:57-77`); root from `AFK_PLUGIN_ROOT` else self (`contract.py:187-191`); shebang check J (`native-contract-gate.sh:403,453`) | FRESHNESS row same commit (`FRESHNESS.md:16-18`) | fits |

## Forge answer fields (github | gitlab)

- change-create-draft `{url,id,draft}`, no `ok` (`forge.sh:374-387` | `:391-405`); change-ready `{ok,id,draft:false}` (`:390-397` | `:408-415`); change-reviewers `--add-reviewer` | `--reviewer` (`:399-408` | `:417-426`); change-comment `{ok,inline:false,comment,url}` (`:426-442` | `:470-489`).
- change-view sets `missing:true` only on confirmed absence; state `open` | `opened` (`:262` | `:182`). note-list `{notes,count}`, gitlab drops system + inline notes (`:571`). change-fetch body only in `files.metadata`.
- ci-wait exit 0/1/2/3 (`ADAPTERS.md:112-115`), budget 5400 / interval 180; GitHub with no CI exits 3. Every other verb: exit 0 + `{"error":true}` on failure.
- Collisions: ci-wait 2 = dispatch failure; 3 = `unsupported` (`none/forge.sh:10-11`). Route on stdout + exit together.

## Landmines

- `forge_ledger.py:1901-1904` opens a Draft with no assignee vs `CONFIG.md:136` every change gets one — rationale-post before the script's create leaves the Draft unassigned.
- `mrReviewer: none` returns the literal string (`afk-config.py:830-831` maps `none` only for mrAssignee).
- Payload as argv from native Windows loses quotes — use stdin (`github/CONTRACT.md:42-46`); long body as one argv (inferred: OS limit).
- Nothing local refuses `push origin X:main`; `protected-lookup.py` has no push caller. `update-ref refs/heads/<other>` from an owned worktree moves another worktree's branch.
- After landing, the executor's local feature branch is behind origin; execute Step 7 pushes without sync (inferred: rejected non-fast-forward).
- create-worktree: name not lower-cased (`:233`); ticket-shaped pattern refuses `bug-*` (`test_create_worktree_name.py:141-151`); harness WorktreeCreate takes no base (`worktree-create.sh:19-25`), codex has no handler; only `--name` writes an owner record.
- Redaction credential rules share one list with URL/identity stripping (`redact.py:456,627`) — sharing means extracting. `publish_bug._request` retry (`:69-118`) has no read-back (≠ D-17). Importing `publish_bug` loads config at import (`:58`).

## Must-dos

- Ship script: look up change by branch first, merged/closed not writable (`forge_ledger.py:1832-1840`); push before create + remote head = HEAD (`:1818-1829`); refuse empty id (`:1906-1909`); assignee from `afk-config.py resolve` (`:1301-1319`); no reviewer or `none` → no ready flip; ci-wait tracked background task, exit 2 resumes via ci-status, exit 3 never a verdict; add `skills/afk/fix` to `MANIFEST.md:413,427`.
- Landing: fetch first (`preflight:59`); ancestry check, never force (`:62,71-75`); `-u` upstream to the feature branch (rationale-post resolves via `branch.<local>.merge`, `forge_ledger.py:1729-1741`); refuse a protected target explicitly; never mutate the executor's worktree.
- Diagnose worktree: fetch base; lower-case slug; parse `WORKTREE_PATH=`; pass `--session`/owner; absolute paths.
- Helper: no import-time config; tests in scripts/tests (`tests.yml:20-26,64`).

## Tests

Covered: ci-wait stdout, create assignee, view missing (`test_forge_adapters.py:595-680,804-817`); plain push (`test_shell_mutations.py:43`). Not covered: change-ready, change-reviewers, ci-status, view by branch; push force forms; unprotected rebase; `--name` + `--base`, remote-ref base, branch survival after push.

## Unverified

- B1 alias/wire forms not enumerated → B2, B4, B8, B9, B11, B12, B13 partial. B5 partial (gc-check reader unread). P3 pytest run timed out.
- Live, load-bearing: glab `--reviewer` add vs replace; `change-ready` on an already-ready change; which change `view <branch>` picks among several; whether `worktree add -b X origin/<f>` sets upstream.

## Fold notes (plugin defects)

4165 seed placeholders dropped; 47 node ids in two fragments with different content, first partition wins; hand fixes in reconcile.py (B2/B13 sites, B3 closed, B5 partial, B6/B7/B10 n/a, 3 hooks.json traced, B1/B13 off the case-blind check).
