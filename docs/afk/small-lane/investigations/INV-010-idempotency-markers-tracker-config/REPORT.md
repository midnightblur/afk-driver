# INV-010 — re-run safety of tracker and forge writers; tracker config and identity

feat-small-lane@d346cfb · partial · ledger: COVERAGE.json (validator exit 0, 2712 nodes, 54 claims)

## Answer

Only the review and rationale ledger is idempotent end to end; most tracker and forge writes have no re-run guard.

- **PRD block** (`publish_prd.py`): region between `afk:prd:start` (prefix, :159) and `afk:prd:end` (exact, :164), replaced in place (:174). Missing end marker drops everything after start (:176). Old figures deleted before the y/N prompt (:289, :334). `--changes` delta comment has no marker; every run re-posts (:340).
- **Meetings** (`publish_meeting.py`): exact expand-title match, only within the run of expands after the heading (:89-98); a renamed title or an interleaved node duplicates.
- **Spinoff stubs**: only guard is the local GRILL-LOG `filed` row (`to-ticket/SKILL.md:95`); `:96` passes `epic`, which `tracker_create` does not accept (`server.py:149`).
- **/afk:bug** (`publish_bug.py`): no marker; bug type (:157) and transition id 12463 (:67) hard-coded; create and comment unchecked (:228, :278); only guard local `state.json`.
- **Review/rationale ledger** (`forge_ledger.py`): rebuilds state from trusted `afk:finding|record|settle v1` markers (:829-844); stops on edited marker, unknown author, duplicate origin (:841, :875, :897); reuses findings by fingerprint (:1330-1360); refuses on truncated comment list (:1920); skips posted entries (:1927); reuses a valid receipt (:1960).
- **change-update-body** (github `forge.sh:412`, gitlab `:440`): replaces the whole body; the `afk:subtasks` block is kept only by agent instructions (`execute/SKILL.md:63`); no verb returns the current body. **Correction (INV-018, 2026-10-16):** wrong for GitHub — `change-fetch` returns the body (github `forge.sh:315,331`); `change-view` omits it (`:146`); GitLab unverified live.
- **No guard**: Jira create/comment (`api.py:540`, `:580`); github-issues create/comment (`:245`, `:311`, parent task-list comment `:332`); forge create-draft, comment, thread-reply. report-issue dedups by fingerprint (`publish.sh:217`) but posts "Seen again" every run (`:267`).
- **Jira keys read**: `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` (`api.py:107`; env → `~/.claude.json` → `~/.codex/config.toml`, `:112-136`), `JIRA_DEFAULT_PROJECT` (`:503`); Basic auth as that email. No code reads `jira.issue-types` or `jira.transitions`; `jira.project` read only by `comment-gate.sh:13`; `credentials-env` shape-checked only (`afk-config.py:656`). `CONFIG.md:294`, jira `CONTRACT.md:26-31`, `adapter.json:22-25` are wrong.
- **github-issues keys read**: `repo` (fallback `GH_REPO`, `:79`), `state-labels` (`:84`); writes as the `gh` login.
- **Forge identity**: `gh` / `glab` login; the ledger trusts the current login (`forge_ledger.py:830`).

## Inferred

- A retried bug publish can file a second Bug (`:107`, `bug/SKILL.md:78`).
- A crash between creating a spinoff stub and recording it files it twice.

## Unverified

- Import-alias and wire name forms unsearched (B1 and inheritors); B3, B5, B6, B7, B10 no method.
- Tracker MCP server handling of the undeclared `epic` argument.
- Test directories outside `scripts/tests` for the PRD/meeting merge code.
- Plugin defect: `merge_fragments.py:116-134` treats seed placeholder `unverified` as conflicting; the seed never folds clean.

## Frontier

Live Jira, GitHub, GitLab behaviour (POST committed on 5xx, transition availability, search index lag).

Written by the orchestrator from the investigation's reply; the investigation's own REPORT.md write was refused.
