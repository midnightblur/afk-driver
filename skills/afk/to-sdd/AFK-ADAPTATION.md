# AFK adaptation (core-services)

When the SDD belongs to an Enhancement / Bug in the AFK workflow:

- **File location.** `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/SDD.md` and `.../adr/design/NNNN-*.md`. Service is derived from the Jira project key per the project's mapping (e.g. `P2P` → `11700-payable`).
- **Parent ticket splice.** Add or update a `## SDD` section in the Enhancement / Bug description:

  ```
  ## SDD

  Architecture lives in the repo at `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/SDD.md`
  (this branch). Design ADRs in `.../adr/design/`.
  ```

  Leave `## PRD` and `## Implementation Notes (auto-maintained)` untouched.

- **Hand-off.** Each downstream subtask MUST cite the SDD section(s) and ADR(s) that constrain it, so the implementing agent has a binding contract — not just a feature ask.
