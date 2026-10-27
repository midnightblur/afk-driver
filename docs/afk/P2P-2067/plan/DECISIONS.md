# Decisions — auto-taken hands-off (protocol + grammar: DECISIONS.md, workflow plugin root). Newest last.

## D-1 — Definition owner reference
- 2026-10-27 · decided by /afk:execute
- Options: canonical owning glossary path vs delivery-route ID or human account
- Chosen: canonical owning glossary path — ADR-0003 makes the map authoritative for glossary ownership and keeps human owner chains in the manifest.
- Supersedes: none
- To reverse: change the Markdown owner grammar, repository validation, fixtures, and dependent owner resolution together.
