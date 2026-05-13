## Goal

Wire `cli.py` to `backend_select` at entrypoint, add multi-repo CLI flag, implement per-backend pre-flight (Jira: token + reachability; GitHub: `gh auth status`, sub-issue REST probe, `claude mcp list | grep github`), and add the pre-flight sweeper that resets crashed-mid-flight sub-issues to `afk:pending`.

## Design refs

- SDD: `../SDD.md` §3 — backend dispatch via `backend_select` at entry.
- SDD: `../SDD.md` §5 observability table row "Pre-flight diagnostic".
- SDD: `../SDD.md` §7 use-case 1 sequenceDiagram — pre-flight + queue discovery flow.
- SDD: `../SDD.md` §7 use-case 3 sequenceDiagram — pre-flight sweeper.
- SDD: `../SDD.md` §8 module table row "cli (modified)".
- SDD: `../SDD.md` §10 NFRs row "Pre-flight total time" / "claude mcp list probe time".
- ADR: `../adr/0005-crash-recovery-sweeper-resets-to-pending.md` — sweeper recovery posture.

## Scope

- `src/afk_driver/cli.py`
- `tests/test_cli.py`

## Acceptance

- [ ] `main(argv)` resolves the backend via `backend_select.resolve(cwd, config)` before constructing the `Runner` (SDD §8 row "cli (modified)")
- [ ] CLI gains `--github-all-repos` flag that overrides `[github] mode` to `"all-repos"` for one invocation; `--cwd-only` overrides to `"cwd"` (SDD §5 feature-flags table row `[github] mode`)
- [ ] Pre-flight on GitHub backend runs in this order: (1) `gh auth status` exits 0, (2) `claude mcp list` output contains `github`, (3) sub-issue REST probe (`gh api /repos/{any_queued_owner}/{repo}/issues/{any_N}/sub_issues`) returns 200, (4) sweeper. Any non-zero halts before runner is invoked (SDD §7 use-case 1 + ADR-0005 flowchart)
- [ ] Pre-flight on Jira backend unchanged (existing checks: `JIRA_API_TOKEN` env present, base URL reachable) (PRD §"Pre-flight checks" — Jira unchanged)
- [ ] Sweeper invokes `tracker.list_stuck_subissues()` and for each match calls `tracker.revert_to_pending(id)` + `tracker.comment(id, "AFK: previous run did not complete; reset to afk:pending for re-pickup")` — reuses ADR-0004's verify-3x machinery via the tracker (ADR-0005 flowchart)
- [ ] Sweeper actions are summarised at the top of the morning digest as `## Sweeper warnings` bullets (SDD §5 observability table row "Sweeper warning bullets in digest")
- [ ] `claude mcp list | grep github` probe times out at 2 000 ms; on timeout halts with diagnostic (SDD §10 NFRs row "claude mcp list probe time")
- [ ] Total pre-flight time stays under 5 000 ms in the happy path with ≤ 50 stuck issues for the sweeper (SDD §10 NFRs row "Pre-flight total time")
- [ ] Existing tests in `test_cli.py` continue to pass; new tests cover: GitHub backend dispatch, multi-repo flag wiring, sweeper invocation, MCP-probe absence → halt, sub-issue REST 4xx → halt (SDD §7 failure-recovery matrix)
- [ ] Tests pass via `pytest tests/test_cli.py` (SDD §10 NFRs)

## Produces

- `src/afk_driver/cli.py#def main(argv: list[str]) -> int:` — entrypoint refactored to use `backend_select`.
- `src/afk_driver/cli.py#def _preflight_github(tracker, scm, config)` — GitHub-specific pre-flight including MCP + REST probes.
- `src/afk_driver/cli.py#def _run_sweeper(tracker)` — pre-flight sweeper that resets stuck sub-issues.
- `src/afk_driver/cli.py#class PreflightError(RuntimeError):` — typed error raised on any pre-flight failure (extends or re-uses existing if compatible).

## Test command

```
pytest tests/test_cli.py
```

## Parent PRD

`tasks/github-backend/PRD.md`

## Parent SDD

`tasks/github-backend/SDD.md`

## Blocked by

- 04-github-issues-client
- 06-backend-select-and-config
- 07-runner-refactor

## Consumes

- 04-github-issues-client `src/afk_driver/github_issues_client.py#def list_stuck_subissues(self) -> list[SubIssueRef]:` — sweeper's view of crashed-mid-flight sub-issues.
- 06-backend-select-and-config `src/afk_driver/backend_select.py#def resolve(cwd: Path, config: DriverConfig) -> Backend:` — entrypoint dispatch.
- 06-backend-select-and-config `src/afk_driver/backend_select.py#class Backend:` — dataclass cli unpacks for runner construction.
- 07-runner-refactor `src/afk_driver/runner.py#class Runner:` — accepts `(tracker, scm, repo_clone_manager)` from cli.

## Conflict procedure

If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, exit with `design-conflict` status quoting the SDD section + the conflict. Do NOT override silently. Route back to `/afk:architect-grill` for a superseding ADR.

## Implementation Notes (auto-maintained)

<!-- AFK appends one bullet per completed SubTask -->
