## Goal
Write the ship script beside `/afk:fix`: four named steps — open (push the fix branch, open one Draft change, then rationale-post), proof (one comment on the change: P-1 and P-2 as text and a link to the ticket's evidence comment), ready (CI wait as a tracked job, then ready and reviewer only on green) and land (fast-forward push onto a feature branch by plain git) — that skip listed outside writes and read back before each retry. Make GitLab's change-reviewers add a reviewer instead of replacing the list.

## Complexity
complex

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — adapter family rows "forge"
- SDD: SDD.md#§5 L4 — Cross-Cutting & Quality Attributes — AuthZ row "Open a change, mark ready, add reviewers"; Idempotency rows "Draft change", "Feature-branch push"; Retry + timeout row "CI wait"
- SDD: SDD.md#§7 L6 — Process & Coordination — "Feature-branch fix"; failure rows owned by the ship script
- SDD: SDD.md#§8 L7 — Module Decomposition — row "ship script (beside fix)"
- SDD: SDD.md#§9b External Seams & Failure Affordance — rows "Forge CI wait", "Feature-branch push"
- ADR: adr/design/0003-outside-writes-run-as-named-steps-with-read-back.md — named-step script over one helper
- ADR: adr/design/0006-feature-branch-fix-lands-by-fast-forward-push.md — fetch, fast-forward check, plain git push, never forced

## Scope
- skills/afk/fix/scripts/ship.py
- adapters/forge/gitlab/forge.sh
- adapters/forge/gitlab/CONTRACT.md
- SAFETY.md
- scripts/tests/test_ship.py
- scripts/tests/test_forge_adapters.py
- CHANGELOG.md

## Seams
- implement: forge scripts: `ci-wait`, `change-create-draft` — §9b boundary "Forge CI wait"; owns its stub-forge seam-test (INV-025)
- implement: feature-branch landing: plain git push, not `afk_adapter` — §9b boundary "Feature-branch push"; owns its git-in-temp-dir seam-test (INV-025)

## Acceptance
- [ ] The ship script's proof step posts the proof comment on the change through `change-comment` — P-1 and P-2 as text and a link to the ticket's evidence comment — and lists it in Outside writes; a re-run skips a listed comment (SDD §4)
- [ ] The script runs one named step (open, proof, ready or land) given the step name and a diagnosis path, and skips a step whose write is already listed in Outside writes (SDD §8)
- [ ] Open pushes the fix branch and opens one Draft change before rationale-post; it looks the change up by branch before opening and by its recorded number after (SDD §14 row "forge scripts: `ci-wait`, `change-create-draft`")
- [ ] Several GitLab changes on one branch end the step `blocked`; the script never opens a second change (SDD §7)
- [ ] The script refuses an empty change id and a protected target branch (SDD §5)
- [ ] Ready runs `ci-wait` as a tracked background job polling every 180 s for at most 5400 s, and routes on exit code and stdout together: green → change-ready, then change-reviewers when a reviewer is configured; red, timeout, unreadable, and no CI (exit 3 at once) → the change stays Draft and the step reports the reason (SDD §9b row "Forge CI wait")
- [ ] GitLab change-reviewers adds the reviewer instead of replacing the list, as on GitHub (SDD §3)
- [ ] Land fetches, checks the push is a fast-forward and pushes with upstream set by plain git, never forced, refusing a protected target; a non-fast-forward refusal is reported to the caller (SDD §9b row "Feature-branch push")
- [ ] `SAFETY.md` gains one sentence: a fix landed on a feature branch is covered by that feature's one Draft change; `BEHAVIORS.md` is unchanged (SDD §14 row "feature-branch landing: plain git push, not `afk_adapter`")
- [ ] Every successful write is appended through the outside-writes helper; a failed fix-branch push or change open is retried only after a read-back of the remote or of change-view by branch, and a re-run opens no duplicate change (SDD §10)
- [ ] Seam-tests assert on what the outside tool returns: a stub forge answering each `ci-wait` outcome including no CI, and a real git remote in a temp folder whose tip moved (SDD §9b)
- [ ] Implements the public interface of SDD §8 row "ship script (beside fix)" unmodified (SDD §8)
- [ ] Conforms to ADR-0003 and ADR-0006 design — no silent pattern substitution (design ADR-0006)

## Produces
- skills/afk/fix/scripts/ship.py#def run_ship_step( — step name + diagnosis path in → step result

## Consumes
- 0001-diagnosis-format skills/utils/diagnose/scripts/outside_writes.py#def append_outside_write( — list the push, the change link
- 0001-diagnosis-format skills/utils/diagnose/scripts/outside_writes.py#def retry_with_read_back( — retry after change-view or remote read-back
- 0002-developer-settings CONFIG.md#Developer settings (K1–K5) — the reviewer key and its `none` rule

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash hooks/plugin-source-gates.sh --staged`; grep the ## Produces anchor | gates pass; declared symbol present |
| unit | `afk-python -m pytest scripts/tests/test_ship.py -q` — step skipping, lookup by branch then number, several GitLab changes → `blocked`, empty id and protected target refused, no duplicate on re-run; the proof comment reaches the stub's `change-comment` once with the ticket link; open, proof, ready in order then all three again → each forge write exactly once, in that order | step logic against a stub forge |
| integration | `afk-python -m pytest scripts/tests/test_ship.py -q -k "ci_wait or fast_forward"` — stub forge per `ci-wait` answer incl. no CI (exit 3 at once); git-in-temp-dir remote with a moved tip refuses the push | the §9b seams as the forge and git really answer |
| integration | `afk-python -m pytest scripts/tests/test_forge_adapters.py -q` — GitLab change-reviewers sends a `+` name | reviewer is added, not replaced |
| integration | `afk-python -m pytest scripts/tests -q` and `bash hooks/tests/hook-smoke.sh`, on Windows and WSL | nothing else broke |

## Context excerpts
> (SDD §9b) | Forge CI wait | `ci-wait` forge verb | exit code + stdout carry green / red / timeout / unreadable; codes collide with other exits (INV-025) | routed on exit code and stdout together; a head commit with no checks, and forge `none`, exit 3 at once (INV-025) | stub-forge test per answer, incl. no CI |
> (SDD §9b) | Feature-branch push | git push, fast-forward only | remote refuses a non-fast-forward | rebase once, else `blocked` | git-in-temp-dir test with a moved remote tip |
> (SDD §3) | forge | change-create-draft, change-ready, change-reviewers, change-update-body, change-comment, ci-wait | ship script; change-update-body also by the executor for the dependency note | GitLab change-reviewers adds a reviewer instead of replacing the list, as on GitHub; the ship script routes `ci-wait` on exit code and output (§9b) |
> (SDD §5) | Open a change, mark ready, add reviewers | developer in a standalone fix; agent: one Draft change per blocking out-of-slice defect, never ready | in-place fix; ready in a hands-off run | `/afk:fix` text, ship script refuses an empty id and a protected target |
> (SDD §5) | CI wait (`ci-wait`) | 1 tracked background job | poll every 180 | 5400 |
> (SDD §7) | Fix branch push fails | git exit code | read-back: remote has the commit; retry | delete the remote branch | ship script |
> (SDD §7) | Draft change open fails | forge error | change-view by branch; retry | close the change | ship script |
> (SDD §7) | CI red, timeout, unreadable, no CI | `ci-wait` exit code and output | none; change stays Draft with the reason | mark ready by hand | ship script |
> (SDD §8) | ship script (beside fix) | named steps open, proof, ready, land | step name + diagnosis path in → step result; skips listed steps | forge adapters, helper | diagnosis |
> (SDD §14 row "forge scripts: …") INV-025: `ci-wait` exit codes collide; `Adapter.call` cannot route `ci-wait`; rationale-post on a Draft without assignee (`forge_ledger.py:1901-1904`) | ship script opens the change before rationale-post; routes `ci-wait` on exit and output; refuses an empty id and a protected target; looks the change up by recorded number; GitLab `change-reviewers` sends a `+` name so it adds (`gitlab/forge.sh:420`) | INV-025: preflight PF-6 numbers match | `git push` is not guarded by the plugin
> (SDD §14 row "feature-branch landing: …") INV-025: no forge kind has a `push` verb (`afk_adapter forge push` answers unsupported, exit 3); push is plain git | fetch, fast-forward check, push with upstream; refuse a protected target | INV-025: SAFETY "one Draft change" satisfied by the feature's Draft change | one SAFETY sentence; no BEHAVIORS change

> (SDD §4) | Proof | tracker: evidence comment text + attachments; standalone change: one comment with P-1 and P-2 as text and a link to the ticket's evidence comment; feature-branch fix: one comment on that branch's open change, else the run report | one per diagnosis | tracker's own | tracker's own; never in git (ADR-0004); Jira attachments read back for stored name and type | evidence marker grammar in the diagnosis format file | credentials removed by the shared redaction rules | no |
> (ADR-0003) Both outside-writing scripts (the ship script: open, proof, ready, land; the bug-mode script) are ordered lists of named steps. One helper is the only code that appends to the diagnosis's Outside writes list, straight after a write succeeds. A re-run skips listed steps. A failed write is retried at most twice, after 5 s and 20 s, and only after a read-back shows it did not take effect; a write with no read-back is never retried. The ship script opens the change before posting reasons, routes `ci-wait` on exit code and output together, refuses an empty change id and a protected target.

## Parent PRD
docs/afk/small-lane/PRD.md

## Parent SDD
docs/afk/small-lane/SDD.md

## Blocked by
0001-diagnosis-format, 0002-developer-settings

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
