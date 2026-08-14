# Share — frictionless Claude Design push (opt-in)

The local file is the fast loop; pushing to `claude.ai/design` is one move for a
hosted, link-shareable preview for non-technical stakeholders. Only when the user
asks ("push it" / "share this"):

1. Resolve the target project per [PUBLISH.md](../design-system/PUBLISH.md)
   step 1 — reuse the team's design-system project, never a per-ticket one.
2. Tag the chosen HTML with a `<!-- @dsCard group="{TICKET-ID}" -->` first-line
   marker so it lands as a labelled card grouped by ticket and is **findable later**
   (`list_projects` → `list_files` re-finds any ticket's mockup months on).
3. `finalize_plan` (the one permission prompt) → `write_files` with that one
   file → print the shareable URL.

(Canonicality of the pushed project: `SKILL.md` → Boundary.)
