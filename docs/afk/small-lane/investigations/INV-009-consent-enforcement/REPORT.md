# INV-009 — consent enforcement

feat-small-lane@d346cfb · partial · boundaries 0/14 closed · unverified 1 (load-bearing 0) · ledger: COVERAGE.json

## Answer

Only one mechanism checks an approval record with a script: the `/afk:report-issue` receipt. No hook refuses a tracker write, a forge write or a push. Every other approval step is prose, a prompt a flag skips, or a flag set at launch.

| Mechanism | Guard site | Kind | Reuse for the fix-proposal rule |
|---|---|---|---|
| report-issue receipt | `publish.sh:185-199`, `:259-261` | script-checked record (sha256 over target, action, body); the agent asserts `--approved` (`adr/0007:58-60`) | partly: binds ticket writes to an approved preview; one script; cannot bind code written later |
| setup consent reuse | `setup/SKILL.md:105-107`, `MANIFEST.md:225` | prose; `install_block.py:328` takes no consent argument | partly: existing record stands for consent |
| /afk:bug publisher | `bug/SKILL.md:42-46` | prose; `publish_bug.py:303` checks nothing | no |
| to-ticket y/N prompt | `publish_prd.py:333-336`, `publish_meeting.py:146-149` | script prompt; `to-ticket/SKILL.md:51` passes `--yes` | no |
| protected-branch guard, git hooks | `protected_branch_guard.py:643`, `precommit-gates.sh:44`, `branch-name-gate.sh:65` | hook, local changes only; `AFK_ALLOW_PROTECTED=1` overrides | no |
| repo-handler "ask" | `run-hook.py:758-807` | hook plumbing; `.afk/hooks.json` is `[]` | partly: asks per tool call |
| DECISIONS.md agent approval | `DECISIONS.md:23-25` | prose; no script reads `plan/DECISIONS.md` | partly; conflicts: `:23`, `:25` exclude external writes and Jira |
| hands-off start as authorization | `autopilot/SKILL.md:24`, `execute/SKILL.md:30` | prose; excludes Jira | yes, as precedent; Jira exclusion needs amendment |
| human sign-off record | `GRILL-LOG-FORMAT.md:84-92`, `to-sdd/SKILL.md:37` | record checked by prose | partly: shape fits (verbatim words, scope clause, void on drift) |
| MR create, tracker MCP writes | `gitlab/forge.sh:394`, `server.py:96-101` | none | gap |
| merge | no forge merge verb | structural | keep |

Q5: no hook refuses tracker or forge writes (B1–B13 searched; B14 frontier). No shared approval-receipt primitive: `approval_receipt` exists only in `publish.sh`; the `forge_ledger.py:1863` receipt records rationale comments only.

## Findings

- `gc-check.sh:151-152` never fires: no plugin caller exports `AFK_DRIVEN` (only the gc smoke test); `MANIFEST.md:954` and `CHANGELOG.md:2143` claim hands-off callers export it.
- Inferred: a tracker MCP write passes the guard, which judges a tool call only by path arguments (`protected_branch_guard.py:91-95,431-438`); no test runs one.

## Unverified

- B1, B13 partial: "ask", "permission", "authorize" not searched.
- B3, B5, B6, B7, B10 judged by reading (no pre-pass method).
- `glab --yes` skips only glab's prompt: CLI knowledge.

## Frontier

B14: harness permission prompts; consuming repos' hook handlers.

Written by the orchestrator from the investigation's reply; the investigation's own REPORT.md write was refused.
