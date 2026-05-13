## Goal

Extend `digest_writer.py` to add `backend` and `repo` columns on per-parent and per-sub-issue rows, render GitHub identifiers as `owner/repo#N`, render PR links as clickable URLs, and prepend the sweeper-warnings block emitted by ST08. Single unified digest file across both backends in one run.

## Design refs

- SDD: `../SDD.md` §5 observability table — digest rows, sweeper warnings, per-session logs.
- SDD: `../SDD.md` §7 use-case 4 — end-of-run digest unchanged in shape, new columns added.
- SDD: `../SDD.md` §8 module table row "digest_writer (modified)".
- PRD: `../PRD.md` §"Observability" user-stories 39-41 — single file across backends, GitHub URL formatting.

## Scope

- `src/afk_driver/digest_writer.py`
- `tests/test_digest_writer.py`

## Acceptance

- [ ] Per-parent digest rows include a `Backend` column (`jira` | `github`) and a `Repo` column (Jira project key or `owner/repo`) (SDD §8 row "digest_writer (modified)")
- [ ] Per-sub-issue rows render the issue identifier as `P2P-1234` (Jira) or `owner/repo#42` (GitHub) so the user can copy-paste into chat (PRD §"Observability" — User Story 41)
- [ ] PR / MR links rendered as clickable Markdown links (`[#42](https://github.com/owner/repo/pull/42)`) (PRD §"Observability" — User Story 41)
- [ ] Sweeper warnings (from ST08's `_run_sweeper`) prepended as a `## Sweeper warnings` block above the per-parent rollup, with one bullet per reset issue (SDD §5 observability table row "Sweeper warning bullets in digest")
- [ ] Mixed Jira+GitHub run produces one file in `~/.afk-driver/digests/{date}.md`, not two (PRD §"Observability" — User Story 39: "single file")
- [ ] Empty-sweeper case: omit the `## Sweeper warnings` block entirely rather than rendering an empty section (SDD §11 — design-level "no event-bus / message-queue introduction" implies clean omission, not placeholder)
- [ ] Golden-file tests added for: GitHub-only run, mixed Jira+GitHub run, multi-repo GitHub run with three repos (PRD §"Testing Decisions" — digest_writer extension scenarios)
- [ ] Existing golden-file tests for Jira-only runs continue to pass byte-identical — new columns absent on pure-Jira runs OR present with empty-string values, decided per existing template style (PRD §"Backend abstraction" — "byte-for-byte unchanged")
- [ ] Tests pass via `pytest tests/test_digest_writer.py` (SDD §10 NFRs)

## Produces

- `src/afk_driver/digest_writer.py#def write_digest(record, out_path)` — entrypoint extended with backend + repo column rendering (signature unchanged externally; record shape grew).
- `src/afk_driver/digest_writer.py#def _render_sweeper_warnings(record)` — new helper for the prepended block.

## Test command

```
pytest tests/test_digest_writer.py
```

## Parent PRD

`tasks/github-backend/PRD.md`

## Parent SDD

`tasks/github-backend/SDD.md`

## Blocked by

- 07-runner-refactor

## Consumes

- 07-runner-refactor `src/afk_driver/runner.py#class RepoFailed:` — run-record entry digest_writer renders as a per-repo row.
- 07-runner-refactor `src/afk_driver/runner.py#class Runner:` — runner exports the structured record (`RunRecord`) digest_writer consumes; backend + repo fields populated post-refactor.

## Conflict procedure

If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, exit with `design-conflict` status quoting the SDD section + the conflict. Do NOT override silently. Route back to `/afk:architect-grill` for a superseding ADR.

## Implementation Notes (auto-maintained)

<!-- AFK appends one bullet per completed SubTask -->
