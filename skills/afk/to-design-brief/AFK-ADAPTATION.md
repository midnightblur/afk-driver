## AFK adaptation (core-services)

When the brief belongs to an Enhancement / Bug in the AFK workflow:

- **File location.** `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/DESIGN-BRIEF.md`. Service is derived from the Jira project key per the project's mapping (e.g. `P2P` → `11700-payable`).
- **Repo-only — does not touch the tracker.** This skill writes
  `DESIGN-BRIEF.md` to disk and stops. It does **not** splice a section into
  the Jira ticket: the brief is shared with stakeholders out of band (link
  the repo file, paste it into a review thread), not published to the
  Enhancement/Bug. Leave the ticket description entirely to its other owners
  (`## PRD` via `/afk:to-ticket`, `## SDD` via `/afk:to-sdd`). Subtask progress
  is local (`plan/PLAN.md`), not on the ticket.
- **Re-emit on SDD change.** Briefs go stale silently — when the SDD or any
  ADR changes materially, re-run this skill. The `Last updated` field is
  the canary.
