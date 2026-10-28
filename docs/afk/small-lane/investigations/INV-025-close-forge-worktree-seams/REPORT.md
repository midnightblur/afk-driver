midnightblur/afk-driver@d346cfb5b3957f410119b4199dc2184f890d341a · closed-with-frontier · boundaries 13/14 · unverified 3 (load-bearing 0) · ledger: docs/afk/small-lane/investigations/INV-025-close-forge-worktree-seams/COVERAGE.json

## Seam rows

| seam | existing contract | planned change | impacted | verdict |
|---|---|---|---|---|
| `/afk:fix` standalone, worktree via `create-worktree` | fix orchestrates, diagnose applies the fix (`skills/afk/fix/SKILL.md:12,31`); `--name` keeps case (`scripts/create-worktree:152-160`), only `{user}` lower-cased (`:210`); no fetch, `--base` only `rev-parse --verify` (`:422`), no `--base` = session HEAD (`:389-395`); owner record only with `--name` (`:443-445`); `remove-worktree` acts only on an owner record (`scripts/remove-worktree.py:397-407`), keeps dirty or unpushed (`:121-202`), defers when the caller is inside (`:322-329`), always exit 0 (`:518`) | lower-case name, fetch base, `--name` + `--base`, retire through `remove-worktree` | `skills/afk/fix/SKILL.md:8`; `skills/afk/execute/SKILL.md:67,77,93,123`; `skills/afk/preflight/SKILL.md:99,125`; `AGENTS.md:117`; `README.md:741,743`; pattern `.afk/config.yaml:19-20` refuses upper case | reworked |
| forge scripts: `ci-wait`, `change-create-draft` | `ci-wait` 0/1/2/3 + one stdout object (`adapters/forge/github/forge.sh:681-722`, `adapters/forge/gitlab/forge.sh:717-764`); dispatch failure 2 + empty stdout (`hooks/lib/adapter.sh:40-49,103-106`); `none` 3 unsupported (`adapters/forge/none/forge.sh:10-11`); create `{url,id,draft}` no `ok` (`github/forge.sh:374-388`); ready `{ok,id,draft:false}` (`:390-397`); `Adapter.call` raises on non-zero, 120 s, one line (`skills/afk/review/scripts/forge_ledger.py:740-787`); rationale-post Draft has no assignee (`:1900-1904`) | ship script opens the change first, routes `ci-wait` on exit + stdout, refuses empty id | `skills/afk/preflight/SKILL.md:197-231` (numbers match); `change-reviewers` only caller `skills/afk/bug/FIXER-PROMPT.md:33` | extends |
| feature-branch landing through `afk_adapter` push | no `git push` form is a guard mutation (`hooks/lib/shell_mutations.py:23-24,386-431`); no pre-push hook (`hooks/install-git-hooks.sh:101-102`); no forge `push` verb: `afk_adapter forge push` = unsupported, exit 3 (`github/forge.sh:724-726`) | fetch, fast-forward check, push `-u`, refuse protected target | executor branch left behind: `skills/afk/execute/SKILL.md:63`, `skills/afk/preflight/SKILL.md:75` | fits (push is plain git, not an adapter verb) |
| outside-writes helper over `tracker_api` | `load` reads config per call, exits on unknown kind (`scripts/tracker_api.py:20-50`); importers `skills/afk/bug/scripts/publish_bug.py:56`, `skills/afk/to-ticket/scripts/publish_prd.py:67`; MCP server has its own loader (`mcp-servers/tracker/server.py:54-77`); `{error}` exit 0 (`adapters/tracker/jira/api.py:666`, `adapters/tracker/github-issues/api.py:382`); `{unavailable}` exit 0 (`github-issues/api.py:95`) vs `ADAPTERS.md:32` exit 4; create may return empty key, no error (`:321-326`) | one helper appends and reads back before retry | `scripts/tests/test_publish_bug.py:25,33` deleted = `tracker_api` untested; `ADAPTERS.md:51` | fits |

## Landmines

- `glab mr update --reviewer` replaces reviewers (`adapters/forge/gitlab/forge.sh:420`); `gh pr edit --add-reviewer` adds (`adapters/forge/github/forge.sh:402`).
- GitLab branch with 2+ MRs: `glab mr view` errors when not a terminal, `missing` false (`gitlab/forge.sh:219,287`) -> `forge_ledger.py:703-706` raises, `_writable_change` (`:1836`) lets it through, rationale-post blocks. GitHub picks newest open, else newest closed (live probe).
- GitHub head with no checks: `ci-wait` exit 3, never 0 (`github/forge.sh:243-248,700-706`); `none` exit 3 at once. GitLab skipped/manual status polls to budget, exit 2 (`gitlab/forge.sh:751-763`, inferred).
- `/afk:gc` (`skills/afk/gc/SKILL.md:76-82`) and `/afk:settle-change` (`skills/utils/settle-change/SKILL.md:102`) remove worktrees with raw git: SDD:551 "retired only by remove-worktree" is false plugin-wide.
- Codex registers no WorktreeCreate/WorktreeRemove; SessionEnd removal deadline 2 s (`hooks/hooks.codex.json:139-148`). Harness WorktreeCreate passes no base (`hooks/worktree-create.sh:19-25`).
- A 5th plugin-source gate breaks the 4-name pins `scripts/tests/test_plugin_source_gates.py:33,313`, `scripts/tests/test_behavior_registry_gate.py:70`.
- Docs refuted: `CONFIG.md:136` (every change assigned) vs rationale-post Draft; `adapters/forge/github/CONTRACT.md:71` (fork unsupported, never answered); tracker CONTRACT stdin promise vs argv-only `jira/api.py:659-661`.
- `skills/afk/to-sdd/scripts/check_sdd_investigations.py:117-122` loads this ledger: keep one `INV-025-*` directory.

## Frontier (B14)

Live GitLab (`mr view` with several MRs, `--ready` on a non-draft MR, whether `--reviewer` clears Draft); live `gh pr ready` on a ready PR (a write); live CI; forge-side branch protection; other repositories.

## Unverified (not load-bearing)

Windows payload via environment (SDD:580) vs argv/stdin (`github/forge.sh:28-34`); `glab --reviewer` Draft effect; tracker search sees a fresh marker before retry.
