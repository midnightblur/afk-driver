## Goal

Make the existing `JiraClient` and `GitLabClient` formally conform to `IssueTracker` and `Scm` Protocols respectively. No behaviour change — this SubTask only normalises method names / adds explicit Protocol nominal-subtype declarations so `runner.py` can be refactored against the protocols in ST07 without a flag day.

## Design refs

- SDD: `../SDD.md` §3 — runner depends on protocols, never concretes.
- SDD: `../SDD.md` §8 module table rows "jira_client" and "gitlab_client" — "implements `tracker_protocol` / `scm_protocol`".
- SDD: `../SDD.md` §9 Strategy classDiagram — `IssueTracker <|.. JiraClient`, `Scm <|.. GitLabClient`.
- ADR: `../adr/0001-skill-seam-mcp-server.md` — driver-side dispatch is via protocols.

## Scope

- `src/afk_driver/jira_client.py`
- `src/afk_driver/gitlab_client.py`
- `tests/test_jira_client.py`
- `tests/test_gitlab_client.py`

## Acceptance

- [ ] `JiraClient` declared as `class JiraClient(IssueTracker):` — explicit Protocol nominal subtype (Python permits this for `runtime_checkable` Protocols) (SDD §8 row "jira_client")
- [ ] `GitLabClient` declared as `class GitLabClient(Scm):` (SDD §8 row "gitlab_client")
- [ ] Method-name aliases added where existing names diverge from the Protocol (e.g. existing `transition(key, name)` exposed as `start_designing` / `start_developing` / `request_cr_merge` / `revert_to_pending` named methods that delegate); existing methods kept as-is for back-compat (SDD §9 row "implicit state machine")
- [ ] `mypy --strict` (or equivalent) passes against both modules with the Protocols imported; structural compliance verified (SDD §8 dependency DAG)
- [ ] Existing tests in `test_jira_client.py` + `test_gitlab_client.py` continue to pass unchanged — proves no behaviour drift (PRD §"Backend abstraction" — "byte-for-byte unchanged when auto-detect picks Jira")
- [ ] New tests assert `isinstance(JiraClient(...), IssueTracker)` and `isinstance(GitLabClient(...), Scm)` succeed (SDD §9 Strategy classDiagram)
- [ ] No call site of `JiraClient` / `GitLabClient` outside this SubTask is modified — runner refactor is ST07's job (SDD §8 dependency DAG)
- [ ] Tests pass via `pytest tests/test_jira_client.py tests/test_gitlab_client.py` (SDD §10 NFRs)

## Produces

- `src/afk_driver/jira_client.py#class JiraClient(IssueTracker):` — JiraClient adopts the IssueTracker Protocol.
- `src/afk_driver/gitlab_client.py#class GitLabClient(Scm):` — GitLabClient adopts the Scm Protocol.
- `src/afk_driver/jira_client.py#def start_designing(self` — method alias for `transition(key, "Start Designing")`.
- `src/afk_driver/jira_client.py#def request_cr_merge(self` — method alias for `transition(key, "Request CR & Merge")`.

## Test command

```
pytest tests/test_jira_client.py tests/test_gitlab_client.py
```

## Parent PRD

`tasks/github-backend/PRD.md`

## Parent SDD

`tasks/github-backend/SDD.md`

## Blocked by

- 01-protocols

## Consumes

- 01-protocols `src/afk_driver/tracker_protocol.py#class IssueTracker(Protocol):` — Strategy interface JiraClient must conform to.
- 01-protocols `src/afk_driver/scm_protocol.py#class Scm(Protocol):` — Strategy interface GitLabClient must conform to.

## Conflict procedure

If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, exit with `design-conflict` status quoting the SDD section + the conflict. Do NOT override silently. Route back to `/afk:architect-grill` for a superseding ADR.

## Implementation Notes (auto-maintained)

<!-- AFK appends one bullet per completed SubTask -->
