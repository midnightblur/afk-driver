# AFK adaptation (core-services)

When the SDD belongs to an Enhancement / Bug in the AFK workflow:

- **File location.** `SDD.md` and `adr/design/NNNN-*.md` land in the ticket spec folder, sibling to the PRD (path convention: `skills/afk/to-prd/SKILL.md`, "Monorepo conventions").
- **Parent ticket splice.** Add or update a `## SDD` section in the Enhancement / Bug description. A stakeholder reading the ticket gets the gist without repo access — three plain-language sentences (what the design does, the shape of the solution, what it deliberately doesn't do) plus the top decisions, then the path:

  ```
  ## SDD

  {2–3 sentences: the shape of the solution in plain domain language.}

  Key decisions:
  - {decision} — {one-clause why} (ADR-NNNN)
  - {…3–5 rows, the ones a stakeholder would ask about}

  Full architecture: `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/SDD.md`
  (this branch). Design ADRs in `.../adr/design/`.
  ```

  Leave `## PRD` and `## Implementation Notes (auto-maintained)` untouched.
