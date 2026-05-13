## Goal

Add backend-dispatch preambles to the three AFK skills (`to-prd`, `prd-to-subtasks`, `afk-go`) so each detects whether the active context is Jira+GitLab or GitHub, then dispatches to the matching MCP namespace (`mcp__jira__*` vs `mcp__github__*`). Each skill keeps its name and entry point; only the body branches. PRD-path conventions and parent-issue-creation behaviour follow the rules pinned in the PRD.

## Design refs

- SDD: `../SDD.md` §3 — skills bypass Python protocols and use parallel MCP namespaces.
- SDD: `../SDD.md` §3 sequenceDiagram "sub-issue created by prd-to-subtasks" — the MCP wire shape.
- SDD: `../SDD.md` §8 module table — skills modified, `prd-to-subtasks` ensures the 4 phase labels exist.
- ADR: `../adr/0001-skill-seam-mcp-server.md` — skill seam is the official `github/github-mcp-server`.
- ADR: `../adr/0002-phase-labels-not-projects-v2.md` — `prd-to-subtasks` must create labels (`gh label create --force`) before tagging issues.
- PRD: `../PRD.md` §"Authoring features on GitHub" — User Stories 5-11 (PRD path, parent issue create-or-attach, sub-issue body template, label tagging).

## Scope

- `skills/to-prd/SKILL.md`
- `skills/prd-to-subtasks/SKILL.md`
- `skills/afk-go/SKILL.md`

## Acceptance

- [ ] Each of the three skills opens with a backend-detection preamble: inspect `git remote get-url origin`; `github.com` host → use `mcp__github__*` tools; otherwise → use existing `mcp__jira__*` tools (SDD §8 row "Skills")
- [ ] `to-prd` on GitHub backend: writes the PRD to the per-repo configured `spec_root` (default `.afk/specs/{N}/PRD.md`), edits the parent issue body to add a `## PRD` section pointing at the file path; if no parent issue key was passed, creates a new parent issue from the PRD title + summary first (PRD §"Authoring features on GitHub" — User Stories 6-8 + Q12 "either")
- [ ] `prd-to-subtasks` on GitHub backend: ensures the 4 phase labels exist in the target repo via `gh label create --force afk:pending` etc., creates one GitHub sub-issue per slice with the structured Goal/Scope/Acceptance/Test-command body, attaches each as a sub-issue of the parent via `gh api`, applies labels `afk-agents` + `afk:pending` (ADR-0002 + PRD §"Authoring features on GitHub" — User Stories 9-11)
- [ ] `afk-go` on GitHub backend: reads the parent issue + sub-issue body, drives the four phase-label transitions via `mcp__github__update_issue` (or equivalent), opens/updates the Draft PR via `mcp__github__create_pull_request`, splices the parent's `## Implementation Notes (auto-maintained)` block (PRD §"Running AFK on GitHub" — User Stories 22-28)
- [ ] Each skill's GitHub branch uses the same Markdown vocabulary the Jira branch uses (Goal, Scope, Acceptance, Test command) — a reader cannot tell which backend a SubTask was authored against from the body alone (PRD §"Authoring features on GitHub" — User Story 10)
- [ ] No skill embeds backend-specific tool names in shared prose — the dispatch happens once at the top, then prose references `tracker tool` / `scm tool` generically (SDD §3 — "skills stay backend-agnostic at the markdown level")
- [ ] Each skill ends with the existing "Next" stanza pointing to the next skill in the chain — unchanged across backends (PRD §"Backend abstraction" — same skill names)
- [ ] No tests required: skills are Markdown + Claude orchestration. Verification is the Step 8 anchor-quality + Step 9 round-trip parse the slicing skill enforces, plus manual inspection during the first GitHub-backend dry-run (PRD §"Testing Decisions" — "Skill dispatch logic. Skills are Markdown + Claude orchestration; testing the dispatch branch is testing the skill runner")

## Produces

- `skills/to-prd/SKILL.md### Backend dispatch (GitHub vs Jira+GitLab)` — preamble section, distinct anchor on the new H2 heading.
- `skills/prd-to-subtasks/SKILL.md### Backend dispatch (GitHub vs Jira+GitLab)` — same preamble pattern in prd-to-subtasks.
- `skills/afk-go/SKILL.md### Backend dispatch (GitHub vs Jira+GitLab)` — same preamble pattern in afk-go.
- `skills/prd-to-subtasks/SKILL.md#### Ensure phase labels exist (GitHub)` — H4 sub-section documenting the `gh label create --force` step required before tagging.

## Test command

```
python -c "import pathlib; [print(p, 'OK') for p in [pathlib.Path('skills/to-prd/SKILL.md'), pathlib.Path('skills/prd-to-subtasks/SKILL.md'), pathlib.Path('skills/afk-go/SKILL.md')] if 'Backend dispatch' in p.read_text(encoding='utf-8')]"
```

## Parent PRD

`tasks/github-backend/PRD.md`

## Parent SDD

`tasks/github-backend/SDD.md`

## Blocked by

- 04-github-issues-client
- 05-github-pr-client

## Consumes

- 04-github-issues-client `src/afk_driver/github_issues_client.py#class GitHubIssuesClient(IssueTracker):` — semantic reference for what the skill's MCP calls must accomplish; skill body uses MCP tools, but the operational model (verify-after-write, single-call label swap) mirrors the driver-side adapter.
- 05-github-pr-client `src/afk_driver/github_pr_client.py#def find_open_pr_by_parent(self, parent_issue_number` — semantic reference for `afk-go`'s "find open PR before creating" pattern.

## Conflict procedure

If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, exit with `design-conflict` status quoting the SDD section + the conflict. Do NOT override silently. Route back to `/afk:architect-grill` for a superseding ADR.

## Implementation Notes (auto-maintained)

<!-- AFK appends one bullet per completed SubTask -->
