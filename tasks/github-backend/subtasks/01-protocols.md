## Goal

Introduce the `IssueTracker` and `Scm` Protocol declarations that decouple `runner.py` from concrete tracker/SCM implementations. These are pure-type modules with no I/O — the foundation every later SubTask depends on.

## Design refs

- SDD: `../SDD.md` §3 row "tracker_protocol / scm_protocol" — Strategy-pattern seam at the runner boundary.
- SDD: `../SDD.md` §8 module table rows "tracker_protocol" and "scm_protocol" — public-interface signatures.
- SDD: `../SDD.md` §9 Strategy classDiagram — the two Protocols + four future impls.
- ADR: `../adr/0001-skill-seam-mcp-server.md` — protocols power the driver-side dispatch (skills go via MCP, not protocols).

## Scope

- `src/afk_driver/tracker_protocol.py`
- `src/afk_driver/scm_protocol.py`
- `tests/test_protocols.py`

## Acceptance

- [ ] `tracker_protocol.py` declares `class IssueTracker(Protocol):` with the 11 methods named in SDD §8 row "tracker_protocol" — `list_pickable`, `get_parent`, `start_designing`, `start_developing`, `request_cr_merge`, `revert_to_pending`, `close`, `comment`, `splice_notes_block`, `get_target_branch`, `list_stuck_subissues` (SDD §8 row "tracker_protocol")
- [ ] `scm_protocol.py` declares `class Scm(Protocol):` with the 4 methods named in SDD §8 row "scm_protocol" — `find_open_pr_by_parent`, `open_draft_pr`, `update_pr_description`, `splice_pr_block` (SDD §8 row "scm_protocol")
- [ ] Both Protocols are `runtime_checkable` so `isinstance(x, IssueTracker)` works for tests (SDD §9 Strategy classDiagram)
- [ ] Method signatures use the data shapes implied by the existing `IssueSummary`/`Transition`/`MRInfo` dataclasses for return types where applicable; new shapes (`SubIssueRef`, `ParentRef`, `PrRef`) are declared in the same Protocol module (SDD §6 erDiagram)
- [ ] No I/O imports (`subprocess`, `urllib`, `requests`, `gh`, etc.) in either file — pure type module per the onion architecture (SDD §8 dependency DAG)
- [ ] Tests assert that `JiraClient` (existing) does NOT yet conform — this SubTask only declares the Protocols; ST02 makes legacy adapters conform (SDD §8 row "jira_client")
- [ ] Tests pass via `pytest tests/test_protocols.py` (SDD §10 NFRs)

## Produces

- `src/afk_driver/tracker_protocol.py#class IssueTracker(Protocol):` — Strategy interface for issue trackers (Jira, GitHub).
- `src/afk_driver/scm_protocol.py#class Scm(Protocol):` — Strategy interface for SCM/PR providers (GitLab, GitHub).
- `src/afk_driver/tracker_protocol.py#class SubIssueRef:` — value object for sub-issue/sub-task references across backends.
- `src/afk_driver/tracker_protocol.py#class ParentRef:` — value object for parent (Enhancement/Issue) references.
- `src/afk_driver/scm_protocol.py#class PrRef:` — value object for MR/PR references.

## Test command

```
pytest tests/test_protocols.py
```

## Parent PRD

`tasks/github-backend/PRD.md`

## Parent SDD

`tasks/github-backend/SDD.md`

## Blocked by

(none)

## Conflict procedure

If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, exit with `design-conflict` status quoting the SDD section + the conflict. Do NOT override silently. Route back to `/afk:architect-grill` for a superseding ADR.

## Implementation Notes (auto-maintained)

<!-- AFK appends one bullet per completed SubTask -->
