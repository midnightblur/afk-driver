## Goal

Implement the `Scm` Protocol for GitHub PRs via `gh` CLI. Owns: find-by-branch, find-by-parent-issue, idempotent Draft PR creation, PR body splicing through the existing `section_splice` marker scheme, `Closes #N` line management.

## Design refs

- SDD: `../SDD.md` §3 — `gh` CLI subprocess for PR ops.
- SDD: `../SDD.md` §5 idempotency table row "PR create" / "Find PR by parent issue" — search-then-filter pattern.
- SDD: `../SDD.md` §5 retry table — `gh pr create` / `gh pr edit` budgets.
- SDD: `../SDD.md` §6 invariants table row "At most one Draft PR per Parent" — guarded by `find_open_pr_by_parent` before `create`.
- SDD: `../SDD.md` §8 module table row "github_pr_client".
- ADR: `../adr/0001-skill-seam-mcp-server.md` — driver-side path uses gh CLI.

## Scope

- `src/afk_driver/github_pr_client.py`
- `tests/test_github_pr_client.py`

## Acceptance

- [ ] `class GitHubPrClient(Scm):` — implements every method on the Protocol (SDD §8 row "github_pr_client")
- [ ] `find_open_pr_by_branch(branch)` runs `gh pr list --head {branch} --state open -F json`; returns the single matching PR or `None` (SDD §5 idempotency table row "PR create")
- [ ] `find_open_pr_by_parent(parent_issue_number)` runs `gh pr list --search "[#{N}]" --state open -F json --limit 100`, then filters client-side for titles containing `[#{N}]` to avoid description-only matches; raises ambiguous error on >1 hit, returns `None` on 0 (SDD §5 idempotency table row "Find PR by parent issue" — mirrors `gitlab_client.find_open_mr_by_parent_key`)
- [ ] `open_draft_pr(spec)` checks `find_open_pr_by_branch` first; if a PR exists, returns it unchanged (idempotent re-open); otherwise runs `gh pr create --draft --base {target} --head {source} --title "[#{N}] {title}" --body {body}` and returns the new PR (SDD §5 idempotency table row "PR create")
- [ ] `update_pr_description(branch, body)` runs `gh pr edit {branch} --body {body}` with retry-2x on transient failure (SDD §5 retry table row "gh pr edit")
- [ ] `splice_pr_block(branch, items)` reuses the existing `section_splice` marker-pair scheme — `<!-- afk:subtasks:start --> ... <!-- afk:subtasks:end -->` — to maintain a sub-issue checklist + `Closes #N` lines in the PR body (SDD §8 row "section_splice (existing, unchanged)")
- [ ] PR body always includes `Closes #{parent}` and `Closes #{sub}` lines for each landed sub-issue, so human merge auto-closes the issue tree (PRD §"How are GitHub issues closed when work completes" — driver closes SubTask, parent via PR Closes)
- [ ] Injected `GhRunner` for test stubbing — mirrors `GlabRunner` (SDD §3)
- [ ] Tests cover: find-by-branch (single match, none, multiple → error), find-by-parent (search filtering, ambiguity error), open-draft-PR (idempotent re-open), splice (round-trip with empty/single/multi sub-issue list), update-description (success + retry path) (PRD §"Testing Decisions" — github_pr_client coverage list)
- [ ] Tests pass via `pytest tests/test_github_pr_client.py` (SDD §10 NFRs)

## Produces

- `src/afk_driver/github_pr_client.py#class GitHubPrClient(Scm):` — GitHub-side Scm implementation.
- `src/afk_driver/github_pr_client.py#def find_open_pr_by_parent(self, parent_issue_number` — title-prefix search for the parent's open Draft PR.
- `src/afk_driver/github_pr_client.py#def open_draft_pr(self, spec)` — idempotent Draft PR creation.

## Test command

```
pytest tests/test_github_pr_client.py
```

## Parent PRD

`tasks/github-backend/PRD.md`

## Parent SDD

`tasks/github-backend/SDD.md`

## Blocked by

- 01-protocols

## Consumes

- 01-protocols `src/afk_driver/scm_protocol.py#class Scm(Protocol):` — Protocol GitHubPrClient implements.
- 01-protocols `src/afk_driver/scm_protocol.py#class PrRef:` — return type for find/open methods.

## Conflict procedure

If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, exit with `design-conflict` status quoting the SDD section + the conflict. Do NOT override silently. Route back to `/afk:architect-grill` for a superseding ADR.

## Implementation Notes (auto-maintained)

<!-- AFK appends one bullet per completed SubTask -->
