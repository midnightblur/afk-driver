# Share — frictionless Claude Design push (opt-in)

The local file is the fast loop; pushing to `claude.ai/design` is one move when
you want a hosted, link-shareable preview for non-technical stakeholders. Only
when the user asks ("push it" / "share this"):

1. `DesignSync list_projects` → **reuse** the team's design-system project if it
   exists (a stable, app/team-level project — *not* a per-ticket one); else
   `create_project` once. Verify the target is a design-system project.
2. Tag the chosen HTML with a `<!-- @dsCard group="{TICKET-ID}" -->` first-line
   marker so it lands as a labelled card grouped by ticket and is **findable later**
   (`list_projects` → `list_files` re-finds any ticket's mockup months on).
3. `finalize_plan` (the one permission prompt) → `write_files` → print the
   shareable URL.

First run only: if design scopes aren't granted, tell the user to run
`/design-login` once, then retry — after that it's silent. (Canonicality of the
pushed project: `SKILL.md` → Boundary.)
