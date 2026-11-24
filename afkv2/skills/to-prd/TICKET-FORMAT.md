# TICKET.md format

`TICKET.md` is the whole new description of a Jira ticket, written from `PRD.md` for a first-time reader who is not a developer. The standard is the section "Ticket descriptions" of the core behaviors; this file says how to write it for the publish.

## Keep lines

- A line `{{keep N}}` or `{{keep N-M}}`, alone on its line, puts the live top-level nodes N to M of `outline.json` at that place, exactly: pictures, tables, cards and marks stay as they are.
- Everything between keep lines is Markdown, converted to new text. A ` ```mermaid ` fence becomes a picture.
- Keep each node of the product owner that needs no change. To change words in a node, leave it out and write its new text in its place; keep the change minimal and exact.
- A node that holds a picture must be kept: the preview refuses `drops-media`. A node of an old block (`in_block` true) cannot be kept: write its content anew, or drop it.
- Each node you leave out is listed in the preview answer `dropped`. Check that list before you show the preview.

## Content

- First, 1 or 2 lines at a glance: what the feature gives, to whom.
- Write requirements as a product owner would, from the user's view (the clerk, the accountant). No code, no file paths, no module names.
- Pick the sections the reader needs: Overview, Requirements, Acceptance criteria, Worked examples, Work breakdown (Part A, Part B, ...), Dependencies, Open questions. Keep the product owner's own sections and their numbers.
- Take each fact from `PRD.md`. Leave out what only a developer acts on: implementation decisions, testing decisions, ids that only the plan reads.
- State the current scope. Apply each settled decision, update or meeting conclusion to the text it changes. Add a short source, such as "(Meeting A)", only where the reader needs it. Write no dated section, no update section, no meeting summary and no history: the preview refuses `dated-section`.
- Write a ticket key bare, such as `ABC-12`: the publish makes each key of the ticket's projects a link. Never write wiki link text `[ABC-12|url]`: the preview refuses `wiki-link`.
- Restate a fact only where the reader needs it there.
- Keep the visible text under 30000 characters: `over_jira_limit` true means Jira may refuse it.
