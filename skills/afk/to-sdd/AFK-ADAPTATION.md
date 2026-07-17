# AFK adaptation (core-services)

SDD belongs to an Enhancement / Bug in the AFK workflow:

- **File location.** `SDD.md` and `adr/design/NNNN-*.md` land in the ticket spec folder, sibling to the PRD (path convention: `skills/afk/to-prd/SKILL.md`, "Monorepo conventions").

This skill writes **local artifacts only** — doesn't touch the parent ticket. Publishing to the tracker is `/afk:to-ticket`'s job (PRD only).
