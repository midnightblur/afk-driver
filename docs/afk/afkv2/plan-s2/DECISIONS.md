# Decisions — auto-taken hands-off (protocol + grammar: DECISIONS.md, workflow plugin root). Newest last.

## D-1 — component type names and props in the guide before the registry exists
- 2026-10-30 · decided by execute (0006-visualize-skill)
- Options: A — the guide names registry types and props now, and the S1 registry schema replaces them when it merges vs B — the guide waits for the S1 registry
- Chosen: A — SDD §4 fixes the component fields (`type`, `id`, `props`, `style`, `children`, `html`) but leaves props to "the type's own schema", which S1 0003/0004 write; the PLAN.md cross-session rule says to build against the frozen contract until the producer merges. Names: `map`, `graph`, `table`, `sequence`, `run-strip`, `chip`, `text`, `freestyle`; each entry of the document `maps` list is a `map` component; map node `state` is `open`, `settled` or `focus`; banner fields `settled`, `unlocks`, `parked` (lists of text); freestyle takes `props.reason`. The test runs `engine check` on every example once the S1 engine exists, so a name the registry does not know shows as a red test, not as silent drift.
- Supersedes: none
- To reverse: rename the types and props in `afkv2/skills/visualize/**` and the fake validator in `afkv2/tests/skills/test_visualize.py` to the S1 registry names

## D-2 — one component page per component, no PRD ids in the guide
- 2026-10-30 · decided by execute (0006-visualize-skill)
- Options: A — SKILL.md spine plus one page per component under `components/` vs B — one large file with every entry
- Chosen: A — the owner's V-7 note settles the guide as "SKILL.md + component pages", and an author loads only the pages it uses. The pages name components by name; the PRD catalog ids live only in the test, because an agent that reads the guide does not read the PRD, and the plugin genericity gate reads `CMP-<n>` as a ticket id.
- Supersedes: none
- To reverse: merge the pages into one file; the test reads the entry headings

## D-3 — an option of a debate card is a table column
- 2026-10-30 · decided by execute (0006-visualize-skill)
- Options: A — the guide shows debate options side by side as table columns with component ids `<item id>-opt-<letter>` vs B — invent an `options` item field
- Chosen: A — SDD §4 item fields have no options field (signed HL-1, so B would change a signed schema); a table is the component that holds things side by side. How the page offers the option mark is the engine's (S1 0003).
- Supersedes: none
- To reverse: change the debate example in `components/card.md` when the S1 card renderer names its option form
