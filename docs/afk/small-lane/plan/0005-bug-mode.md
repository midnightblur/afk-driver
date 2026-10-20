## Goal
Add the bug and ad-hoc mode to `/afk:to-ticket`: a sibling file plus one script that creates or updates a ticket from a diagnosis file or a description file, moves it to the configured in-review state, posts evidence comments and proof files, and backfills the Jira fix version — through tracker adapter verbs, as named steps that skip listed outside writes and read back before each retry.

## Complexity
complex

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — API contract row "`/afk:to-ticket` bug and ad-hoc mode"
- SDD: SDD.md#§5 L4 — Cross-Cutting & Quality Attributes — AuthZ row "Create or update a ticket, post evidence"; Idempotency rows "Ticket create", "Evidence comment, attach"
- SDD: SDD.md#§6 L5 — Domain Model — invariants "Ticket key set only while empty", "A tracker write runs only with a person present or a covering prior approval", "The bug mode writes a ticket description only on a ticket it created"
- SDD: SDD.md#§7 L6 — Process & Coordination — failure rows owned by the bug mode
- SDD: SDD.md#§8 L7 — Module Decomposition — row "bug-mode sibling + script"
- ADR: adr/design/0009-bug-mode-drives-tracker-adapter-verbs.md — one script over adapter verbs, not `publish_prd`
- ADR: adr/design/0003-outside-writes-run-as-named-steps-with-read-back.md — named steps, skip listed, read back before retry
- ADR: adr/design/0004-proof-on-the-ticket-through-tracker-attach.md — proof files, read-back, unique names

## Scope
- skills/afk/to-ticket/SKILL.md
- skills/afk/to-ticket/BUG-MODE.md
- skills/afk/to-ticket/scripts/publish_bug_mode.py
- AGENTS.md
- scripts/tests/test_publish_bug_mode.py
- CHANGELOG.md

## Seams
- implement: `/afk:to-ticket` bug mode, not through `publish_prd` — the new script and sibling file; owns their stub-tracker tests (INV-024)
- implement: `/afk:to-ticket` existing modes: `publish_prd`, `publish_meeting`, spinoff — the PRD block and Meeting Summaries stay untouched by the new mode (INV-024)
- use: tracker adapters: `tracker_create`, `upload_attachment`, `fixVersions`, `state-labels` — calls `tracker_attach` and relies on the in-review and fix-version refusals (INV-024)

## Acceptance
- [ ] When the diagnosis's Outside writes list a change link, the evidence comment carries it; a stub-tracker test asserts the link (PRD AC-020)
- [ ] The mode creates or updates a bug or ad-hoc ticket from a diagnosis file, or from a description written to a file first, on Jira and on GitHub Issues, and prints `TICKET: <key> <link>` (PRD AC-031)
- [ ] An optional type (bug or enhancement) is checked before any write: the GitHub Issues type label must exist, and the Jira issue type is checked, which the old publisher never did (design ADR-0009)
- [ ] A given ticket key must be one the tracker returns, else the run is refused with no write (SDD §3)
- [ ] The diagnosis summary becomes the description only of a ticket the mode creates; on an existing ticket the mode only comments, and it never touches the `afk:prd` block or the Meeting Summaries region (SDD §6)
- [ ] The diagnosis's ticket key is set only while empty; a later different key is listed in Outside writes (SDD §4)
- [ ] After creating a ticket, the mode re-resolves the spec folder with the new key and git-moves the folder when the path differs (SDD §4)
- [ ] The in-review key must be configured and match a tracker transition by name or id, else the run is refused with no write; tracker kind `none` is refused before the first write (PRD AC-032)
- [ ] On Jira the mode asks for the fix version and backfills it, refusing an unknown one before any write; on GitHub Issues it does not ask (PRD AC-034)
- [ ] A tracker write runs only with a person present or under a prior approval that covers ticket writes; otherwise the run is refused with no write (PRD AC-036)
- [ ] Evidence goes on the ticket as comments built from the diagnosis and the proof, each with the visible evidence marker; proof files go through `tracker_attach`, and an unsupported or mismatched file is named in the comment (PRD AC-033)
- [ ] Proof file names carry the diagnosis id, the kind and the step (design ADR-0004)
- [ ] A stopped diagnosis (works as specified, cannot reproduce) is posted as one evidence comment and read back by its marker before any retry (SDD §7)
- [ ] Every write is appended to Outside writes through the outside-writes helper; a re-run skips listed writes, retries a failed one at most twice after a read-back, and creates no duplicate ticket when the read-back finds the earlier one (SDD §10)
- [ ] The run is dry-run first, and keeps the old publisher's safeguards: fix-version check, 4xx bodies shown, 5xx retried (SDD §14 row "`/afk:to-ticket` bug mode, not through `publish_prd`")
- [ ] The script drives adapter verbs through `tracker_api.load(("call",))`, and its test covers that load (SDD §14 row "`/afk:to-ticket` bug mode, not through `publish_prd`")
- [ ] `AGENTS.md`'s description-ownership rules gain one sentence: the bug mode writes a description only on a ticket it creates (SDD §14 row "`/afk:to-ticket` bug mode, not through `publish_prd`")
- [ ] PRD mode and meeting mode behave as before; spinoff stubs pass through the changed adapter create (SDD §14 row "`/afk:to-ticket` existing modes: `publish_prd`, `publish_meeting`, spinoff")
- [ ] Implements the public interface of SDD §8 row "bug-mode sibling + script" unmodified (SDD §8)

## Produces
- skills/afk/to-ticket/BUG-MODE.md#Bug and ad-hoc mode — the mode's steps, refusals and write order
- skills/afk/to-ticket/scripts/publish_bug_mode.py#def run_bug_mode( — diagnosis path or description file + optional type and key in → `TICKET:` line

## Consumes
- 0001-diagnosis-format skills/utils/diagnose/scripts/outside_writes.py#def append_outside_write( — list each write after it succeeds
- 0001-diagnosis-format skills/utils/diagnose/scripts/outside_writes.py#def retry_with_read_back( — retry a failed write after a read-back
- 0001-diagnosis-format skills/utils/diagnose/DIAGNOSIS-FORMAT.md#Evidence marker grammar — marker on each evidence comment
- 0002-developer-settings CONFIG.md#Developer settings (K1–K5) — the assignee key and its `none` rule
- 0003-tracker-attach adapters/tracker/jira/api.py#"tracker_attach": — Jira upload with read-back
- 0003-tracker-attach adapters/tracker/github-issues/api.py#"tracker_attach": — GitHub Issues inline attach

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash hooks/plugin-source-gates.sh --staged`; grep each ## Produces anchor | gates pass; declared symbols present |
| unit | `afk-python -m pytest scripts/tests/test_publish_bug_mode.py -q` — stub Jira and stub GitHub Issues: change link in the evidence comment, create, update of an existing ticket (comment only), configured in-review move, evidence comments, fix-version backfill, every refusal with zero writes, re-run with no duplicate | the mode's writes as the stub tracker records them |
| integration | `afk-python -m pytest scripts/tests/test_publish_bug_mode.py -q -k load` asserts the script loads the adapter through `tracker_api.load(("call",))` and the stub tracker receives the real `tracker_attach` payload | the adapter seam carries our values |
| integration | `afk-python -m pytest scripts/tests -q` and `bash hooks/tests/hook-smoke.sh`, on Windows and WSL | PRD and meeting modes and everything else unchanged |

## Context excerpts
> (SDD §3) | `/afk:to-ticket` bug and ad-hoc mode, with a diagnosis file path or a description written to a file first, an optional type (bug or enhancement) and an optional ticket key | a developer; a run under prior approval that covers ticket writes | every other caller; a run with neither a person present nor that approval: refused, no write | the in-review key must be configured and match a transition (name or id), else refused with no write; Jira: an unknown fix version refused before any write; GitHub Issues: the type label must exist; a given key must be one the tracker returns; tracker kind `none` → refused before the first write | `TICKET: <key> <link>`, created or updated | refused (unknown state, unknown key, unknown fix version, tracker kind none), or the adapter error after the retries, with no further write after it | listed outside writes are skipped; a failed write retried at most twice, each after a read-back shows it did not take effect; dry-run first | new mode; writes the diagnosis summary as the description only on a ticket it creates, comments only on an existing ticket; PRD and meeting modes unchanged; spinoff tickets on Jira gain formatted text and the unknown-fix-version refusal through the adapter |
> (SDD §4) | Work id | text | no | ticket key, else `bug-{slug}` | — | changes only when the folder moves after a ticket is created | unique per spec folder | the bug mode re-resolves the folder with the key and git-moves it when the path differs |
> (SDD §4) | Ticket key | text | yes | empty | — | set by the bug mode only while empty; a later different key goes into Outside writes | — | — |
> (SDD §5) | Ticket create | evidence marker in the ticket body, searched by tracker search | the life of the diagnosis | Outside writes: ticket key |
> (SDD §5) | Evidence comment, attach | visible evidence marker per comment | the life of the ticket | Outside writes: marker |
> (SDD §7) | Ticket create fails | adapter `error` or `unavailable` answer, or an empty key (exit 0, INV-025) | read-back by marker search; ≤2 retries at 5 s / 20 s | close a duplicate by hand | bug mode |
> (SDD §7) | Proof post or upload fails | adapter error / unsupported per file / stored name or type differs | read-back of comments and attachments; unsupported or mismatched file named in the comment | delete comment or attachment; add a named file by hand | bug mode |
> (SDD §7) | In-review move fails | adapter error; unconfigured key refused before write | read-back of state | move back by hand | bug mode |
> (SDD §7) | Stopped diagnosis post | adapter error | read-back by marker | delete the comment | bug mode |
> (SDD §8) | bug-mode sibling + script (beside to-ticket) | ticket create/update, in-review move, evidence, fix version | diagnosis path or description file + optional type and key → `TICKET:` line | tracker adapters (`tracker_api` load of `call`), helper | ticket |
> (SDD §14 row "`/afk:to-ticket` bug mode, not through `publish_prd`") | `/afk:to-ticket` bug mode, not through `publish_prd` | (INV-024): `publish_prd.py:67-75` loads Jira-only symbols at import; the Jira client has no create, transition or versions | one new script driving adapter verbs through `tracker_api.load(("call",))`; files only from a file on disk; the diagnosis summary is the description only of a ticket it creates, comments only on an existing ticket (one sentence added to the description-ownership rules, `AGENTS.md:178`); proof files read back after upload; dry-run first | (INV-024): no test imports `publish_prd`; skill text `to-ticket/SKILL.md:3,8,10,16,25,29,90`; `test_tracker_create_assignee.py:58` expects exactly one request to create | carry the old bug publisher's safeguards: dry-run, fix-version check, 4xx bodies, retry 5xx; the type check is new (the old publisher hard-codes `Bug`, `publish_bug.py:157`); `call()` catches only `KeyError` and `SystemExit` (`jira/api.py:634-642`) | extends (ADR-0009) |
> (PRD Testing Decisions) M4: script tests against stub trackers for create, update, configured states, evidence comments and the fix-version backfill, on Jira and GitHub Issues.

## Parent PRD
docs/afk/small-lane/PRD.md

## Parent SDD
docs/afk/small-lane/SDD.md

## Blocked by
0001-diagnosis-format, 0002-developer-settings, 0003-tracker-attach

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
