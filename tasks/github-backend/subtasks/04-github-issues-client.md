## Goal

Implement the `IssueTracker` Protocol for GitHub via `gh` CLI subprocess + `gh api` for sub-issue endpoints the native CLI doesn't wrap. Owns: queue search, sub-issue CRUD, mutually-exclusive phase-label transitions with verify-after-write retry, comment posting, issue-body splicing, target-branch label resolution, stuck-issue listing for the sweeper.

## Design refs

- SDD: `../SDD.md` §3 — `gh` CLI subprocess + `gh api` for sub-issues.
- SDD: `../SDD.md` §3 sequenceDiagram "phase transition with verify-3x" — the binding wire shape.
- SDD: `../SDD.md` §5 idempotency table — sub-issue create, phase transition, comment dedup contracts.
- SDD: `../SDD.md` §5 retry table — `gh issue edit`/`view`/`comment` retry budgets + timeouts.
- SDD: `../SDD.md` §6 invariants table — "at most one `afk:*` label" guarded by `transition_phase`.
- SDD: `../SDD.md` §6 phase-label state machine.
- SDD: `../SDD.md` §8 module table row "github_issues_client".
- ADR: `../adr/0001-skill-seam-mcp-server.md` — driver-side path uses gh CLI, not MCP.
- ADR: `../adr/0002-phase-labels-not-projects-v2.md` — labels are the phase representation.
- ADR: `../adr/0004-phase-transition-verify-after-write.md` — retry-3x policy.

## Scope

- `src/afk_driver/github_issues_client.py`
- `tests/test_github_issues_client.py`

## Acceptance

- [ ] `class GitHubIssuesClient(IssueTracker):` — implements every method on the Protocol (SDD §8 row "github_issues_client")
- [ ] Phase transitions implemented as a single `gh issue edit --remove-label afk:pending,afk:designing,afk:developing,afk:cr-merge --add-label afk:{new}` followed by `gh issue view --json labels` verification; mismatch triggers retry up to 3 attempts with backoff `0/200/600 ms` (ADR-0004)
- [ ] On 3rd-retry failure: posts an abort comment ("AFK: phase transition failed; aborting") on the issue and raises `PhaseTransitionError` (ADR-0004)
- [ ] `list_pickable` issues a single `gh search issues --owner @me state:open label:afk-agents label:afk:pending` call, parses JSON, returns `list[SubIssueRef]` (SDD §3 sequenceDiagram queue-discovery)
- [ ] `list_stuck_subissues` issues `gh search issues label:afk:designing OR label:afk:developing OR label:afk:cr-merge assignee:@me` — used by the pre-flight sweeper (ADR-0005)
- [ ] Sub-issue creation goes through `gh api -X POST /repos/{owner}/{repo}/issues/{N}/sub_issues` with body `{"sub_issue_id": M}`; response 201 verified before the call returns (SDD §3 sequenceDiagram "sub-issue created by prd-to-subtasks")
- [ ] `splice_notes_block(parent_id, body)` and `splice_pr_block`-equivalent for the `## PRD` section reuse the existing `section_splice` module's marker-pair scheme — `<!-- afk:notes:start --> ... <!-- afk:notes:end -->` — unchanged (SDD §8 row "section_splice (existing, unchanged)")
- [ ] `get_target_branch(parent_id)` reads the `target:{branch}` label on the parent issue, falls back to `gh repo view --json defaultBranchRef` if absent (PRD §"GitHub data model" — target-branch label)
- [ ] `comment(issue_id, body)` deduplicates by content-hash: searches the issue's recent comments for an identical body before posting (SDD §5 idempotency table row "Comment on sub-issue")
- [ ] Injected `GhRunner: Callable[[list[str]], CompletedProcess]` for test stubbing — mirrors `GlabRunner` (SDD §3 — "subprocess pattern parallels glab")
- [ ] No HTTP libraries imported — all GitHub I/O is via `gh` subprocess (ADR-0001 — "driver path uses gh CLI / gh api")
- [ ] Tests cover: queue search call shape, sub-issue REST envelope (success + 404 + malformed JSON), phase-label swap atomicity (single edit call with both `--remove-label` and `--add-label`), verify-after-write retry sequence (success after retry 2, failure after retry 3), comment dedup, target-branch label read with default-branch fallback, missing/malformed label edge case (PRD §"Testing Decisions" — github_issues_client coverage list)
- [ ] Tests pass via `pytest tests/test_github_issues_client.py` (SDD §10 NFRs)

## Produces

- `src/afk_driver/github_issues_client.py#class GitHubIssuesClient(IssueTracker):` — GitHub-side IssueTracker implementation.
- `src/afk_driver/github_issues_client.py#class PhaseTransitionError(RuntimeError):` — typed error raised when verify-after-write retries are exhausted.
- `src/afk_driver/github_issues_client.py#def transition_phase(self, issue_id, target_label):` — single entrypoint for phase changes; encapsulates the retry-3x policy.
- `src/afk_driver/github_issues_client.py#def list_stuck_subissues(self) -> list[SubIssueRef]:` — sweeper's view; returns issues at any non-pending afk:* phase.

## Test command

```
pytest tests/test_github_issues_client.py
```

## Parent PRD

`tasks/github-backend/PRD.md`

## Parent SDD

`tasks/github-backend/SDD.md`

## Blocked by

- 01-protocols

## Consumes

- 01-protocols `src/afk_driver/tracker_protocol.py#class IssueTracker(Protocol):` — Protocol GitHubIssuesClient implements.
- 01-protocols `src/afk_driver/tracker_protocol.py#class SubIssueRef:` — return type for `list_pickable` / `list_stuck_subissues`.
- 01-protocols `src/afk_driver/tracker_protocol.py#class ParentRef:` — return type for `get_parent`.

## Conflict procedure

If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, exit with `design-conflict` status quoting the SDD section + the conflict. Do NOT override silently. Route back to `/afk:architect-grill` for a superseding ADR.

## Implementation Notes (auto-maintained)

<!-- AFK appends one bullet per completed SubTask -->
