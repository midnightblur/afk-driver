## Goal
Rewrite `/afk:fix` as the standalone fix: run `/afk:diagnose`, check the diagnosis, ask for approval of the proposal, fix test-first in an owned worktree, run every tier, collect proof, and ship through the bug mode and the ship script in the fixed write order — or, for a diagnosis started from a feature branch, land the fix on that branch. A shipping sibling file holds the write order and the feature-branch path.

## Complexity
standard

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — API contract row "`/afk:fix` with a ticket key, a description, or a diagnosis file path"
- SDD: SDD.md#§4 L3 — Data Architecture — rows "Diagnosis worktree", "Proof", "Proof files before upload"; field "Approval"
- SDD: SDD.md#§5 L4 — Cross-Cutting & Quality Attributes — AuthZ rows "Approve a fix proposal", "Change product code for a fix", "Open a change, mark ready, add reviewers"
- SDD: SDD.md#§6 L5 — Domain Model — invariants guarded by `/afk:fix` text
- SDD: SDD.md#§7 L6 — Process & Coordination — "Standalone fix", "Feature-branch fix", "Size call"; failure rows owned by `/afk:fix`
- SDD: SDD.md#§8 L7 — Module Decomposition — row "fix skill + shipping sibling"
- ADR: adr/design/0008-approval-held-by-skill-text.md — approval recorded, held by skill text, not checked
- ADR: adr/design/0006-feature-branch-fix-lands-by-fast-forward-push.md — feature-branch landing
- ADR: adr/design/0004-proof-on-the-ticket-through-tracker-attach.md — proof on the ticket, never in git

## Scope
- skills/afk/fix/SKILL.md
- skills/afk/fix/SHIPPING.md
- CHANGELOG.md

## Seams
- implement: `/afk:fix` standalone, worktree via `create-worktree` — the standalone flow and its owned worktree (INV-025)
- use: forge scripts: `ci-wait`, `change-create-draft` — through the ship script's open and ready steps (INV-025)
- use: feature-branch landing: plain git push, not `afk_adapter` — through the ship script's land step (INV-025)
- use: `/afk:to-ticket` bug mode, not through `publish_prd` — every ticket write (INV-024)

## Acceptance
- [ ] Fix takes a ticket key, a description or a diagnosis path; a diagnosis path must name a file the diagnosis check script accepts (SDD §3)
- [ ] Fix changes no code without (a) verdict V-1, or a V-2/V-3 diagnosis whose grill log carries a "still small" size-call row, and (b) an approval from the caller or a covering prior approval (PRD AC-011)
- [ ] With verdict V-4 or V-5 the fix stops with no code change and posts the diagnosis, or what was tried and what is needed, through the bug mode only after approval (PRD AC-012, AC-013)
- [ ] One approval covers the code change, the ticket writes and the change; the fix asks no second time in the same run (PRD AC-014)
- [ ] A steer sends the proposal back to diagnosis; no code changes until a revised proposal is approved (PRD AC-015)
- [ ] The fix never approves its own proposal; an agent caller approves under `DECISIONS.md` and, when the change is not easy to undo or no option is a clear winner, the run stops `needs_decision` (PRD AC-016)
- [ ] Fix writes only the Approval part of the diagnosis: who, their words or the prior approval, what it covers, and the date (SDD §4)
- [ ] When no ticket exists, fix creates one through the bug mode after approval and before changing code (PRD AC-019)
- [ ] Fix makes the diagnosis's failing test pass and declares success only when every tier is green (PRD AC-017)
- [ ] The outside writes run in this order: ticket (if none), ship open, proof comment with `tracker_attach`, proof comment on the change, in-review move, ship ready (SDD §7)
- [ ] At the change, fix posts the change link and the proof on the ticket and moves the ticket to the configured in-review state (PRD AC-020)
- [ ] A successful standalone fix leaves proof P-1, P-2 and P-3 on the ticket, and P-1 and P-2 plus a link to the ticket's proof on the change, with credentials removed by the shared redaction rules (PRD AC-018)
- [ ] The run ends at a change with tests passing; the change goes ready and gets a reviewer only on green CI with a reviewer configured; nothing merges (PRD AC-021)
- [ ] A missing assignee or reviewer is asked for when a person is present; a hands-off run leaves it unassigned and reports it (SDD §14 row "developer settings of `afk:bug`")
- [ ] A diagnosis started from a feature branch lands the fix on that branch through the land step with no ticket and no change; a moved tip gets one rebase and every tier again, else the run ends `blocked` with the commits left on the diagnosis branch; proof goes as one comment on that branch's open change, else into the run report (SDD §7)
- [ ] The fix worktree is cut in owned mode with a lower-cased name and a fetched base; a branch-pattern refusal is asked about, or parks `needs_decision` hands-off; at the end the worktree is removed from outside it through the remove script, whose report fix reads and repeats when a worktree is kept (SDD §14 row "`/afk:fix` standalone, worktree via `create-worktree`")
- [ ] Tracker or forge kind `none` is probed before the first write; the fix then stays local and stops (SDD §7)
- [ ] The fix runs in the current session; no background fixer, queue, local merge for re-test or push notification exists (PRD AC-024)
- [ ] A ticket key filed by the old pipeline works as input with no migration step (PRD AC-037)
- [ ] A re-run reuses the diagnosis, ticket key and branch it recorded and skips listed outside writes (SDD §3)
- [ ] The run ends with an `OUTCOME:` line from `fixed`, `works_as_specified`, `cannot_reproduce`, `needs_grill`, `needs_decision`, `blocked` and the plain-terms sentence (SDD §3)
- [ ] Implements the public interface of SDD §8 row "fix skill + shipping sibling" unmodified (SDD §8)
- [ ] Conforms to ADR-0008 design — approval is recorded, never checked by code (design ADR-0008)

## Produces
- skills/afk/fix/SHIPPING.md#Standalone write order — the fixed order of outside writes and what each lists
- skills/afk/fix/SHIPPING.md#Feature-branch fix (B-8) — the land path, rebase-once rule and proof destination

## Consumes
- 0001-diagnosis-format skills/utils/diagnose/scripts/check_diagnosis.py#def check_diagnosis( — accept the diagnosis before any change
- 0004-diagnose-rewrite skills/utils/diagnose/SKILL.md#DIAGNOSIS: <verdict> <path> — the diagnose run fix starts with
- 0004-diagnose-rewrite skills/afk/grill-requirements/GRILL-LOG-FORMAT.md#Size-call row — the "still small" row read before changing code
- 0005-bug-mode skills/afk/to-ticket/scripts/publish_bug_mode.py#def run_bug_mode( — every ticket write
- 0006-fix-procedure skills/afk/fix/IN-PLACE-FIX.md#In-place fix results — the test-first fix and tier loop
- 0007-ship-script skills/afk/fix/scripts/ship.py#def run_ship_step( — open, proof, ready, land

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash hooks/plugin-source-gates.sh --staged` (skill registry, genericity, native contract); `bash hooks/wiring-gate.sh`; grep each ## Produces anchor | prose gates pass; every script and file fix names is reachable |
| static | method: walk `SHIPPING.md`'s standalone write order against the SDD §7 diagram — ticket (if none), ship open, ticket proof with `tracker_attach`, ship proof, in-review move, ship ready — and check each outside write names the script step that skips it on a re-run (bug mode or ship script) | the prose order matches the SDD; a replay re-writes nothing |
| integration | `afk-python -m pytest scripts/tests/test_create_worktree_name.py scripts/tests/test_remove_worktree.py scripts/tests/test_worktree_owner.py -q` | owned-mode worktree create and outside removal behave as fix relies on |
| integration | `afk-python -m pytest scripts/tests -q` and `bash hooks/tests/hook-smoke.sh`, on Windows and WSL | nothing else broke |

## Context excerpts
> (SDD §3) | `/afk:fix` with a ticket key, a description, or a diagnosis file path | a developer; an agent caller for a blocking defect outside its slice, under prior approval | a caller with neither an approval nor a covering prior approval: stops before any code change | same input rule as diagnose; a diagnosis path must name a file the diagnosis check script accepts | `OUTCOME: fixed` with the change link and ticket key; for a diagnosis started from a feature branch: the pushed commit and that branch, no ticket, no change | `works_as_specified`, `cannot_reproduce`, `needs_grill`, `needs_decision`, `blocked`; a feature branch that keeps moving, or a red tier after the rebase → `blocked`, commits left on the diagnosis branch | reuses the diagnosis, ticket key and branch it recorded; skips listed outside writes; looks the change up by its branch before opening one and by its recorded number after; several GitLab changes on one branch → `blocked`, never a second change | compatible for humans; agent callers that fixed in place move to the shared fix procedure |
> (SDD §4) | Approval | who; their words or the prior approval; what it covers (code, ticket writes, change); date | yes | empty | date: ISO 8601 | written by `/afk:fix` only; emptied by every diagnose rewrite; nothing checks it (ADR-0008) | — | — |
> (SDD §4) | Diagnosis worktree | a linked worktree off the Base branch, made in the owned mode (name and base given) | one per diagnosis | none | retired by `/afk:fix` at its end, from outside it, through the plugin's remove script, whose report fix reads; which keeps a dirty worktree or one with unpushed commits and reports it; a stopped diagnosis keeps its worktree and names it |
> (SDD §4) | Proof | tracker: evidence comment text + attachments; standalone change: one comment with P-1 and P-2 as text and a link to the ticket's evidence comment; feature-branch fix: one comment on that branch's open change, else the run report | one per diagnosis | tracker's own | tracker's own; never in git (ADR-0004); Jira attachments read back for stored name and type | evidence marker grammar in the diagnosis format file | credentials removed by the shared redaction rules | no |
> (SDD §7)
> **Standalone fix** (B-1; D-28; HL-5 order).
>
> ```mermaid
> sequenceDiagram
>   participant P as Person
>   participant F as /afk:fix
>   participant T as /afk:to-ticket bug mode
>   participant S as Ship script
>   participant G as Forge
>   F->>F: run /afk:diagnose, check DIAGNOSIS.md
>   F->>P: proposal
>   P-->>F: approval or steer
>   opt no ticket
>     F->>T: create ticket, then list key
>   end
>   F->>F: test-first fix, every tier green
>   F->>S: open: push branch, Draft change, rationale-post
>   F->>T: proof comment and tracker_attach
>   F->>S: proof comment on the change: change-comment
>   F->>T: move ticket to in review
>   F->>S: ready: ci-wait, then ready and reviewer on green
> ```
>
> Caption: each outside write follows a fixed order and is listed in the diagnosis right after it succeeds.
> (SDD §7) **Feature-branch fix** (B-8; ADR-0006): fix commits on the diagnosis branch made from the feature tip → every tier green → fetch, fast-forward check, push with upstream → proof comment on the feature's open change, else the run report. A moved tip → one rebase, every tier again, push; else `blocked`, commits stay on the diagnosis branch.
> (SDD §7) | Feature-branch push rejected | non-fast-forward refusal | one rebase, every tier, push | pull; commits stay on the diagnosis branch | `/afk:fix` |
> (SDD §7) | Branch-pattern refusal | branch-name gate | none | person names the branch; hands-off parks `needs_decision` | `/afk:fix` |
> (SDD §7) | Worktree kept at the end | remove script report (it always exits 0) | none | developer removes it | `/afk:fix` |
> (SDD §7) | Tracker or forge kind `none` | probe before the first write | fix stays local and stops | — | `/afk:fix` |
> (SDD §14 row "`/afk:fix` standalone, worktree via `create-worktree`") INV-025: `create-worktree` never fetches or lower-cases; owner record only in `--name` mode (`create-worktree:443-445`); `remove-worktree` always exits 0 and acts only on owned worktrees (`remove-worktree.py:518`) | standalone: diagnose → approval → test-first fix → every tier → proof → ship script; cuts the worktree with `--name` and `--base`, retires it with `remove-worktree` from outside it and reads its report | … | lower-case the name, fetch the base; pattern refusal → ask, or `needs_decision` hands-off
> (PRD P) P-1 the test that failed before the fix and passes after, with its output · P-2 the result of every verification tier the fix ran · P-3 a capture from the running app before and after the fix, or the request and response for an API bug

## Parent PRD
docs/afk/small-lane/PRD.md

## Parent SDD
docs/afk/small-lane/SDD.md

## Blocked by
0004-diagnose-rewrite, 0005-bug-mode, 0006-fix-procedure, 0007-ship-script

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
