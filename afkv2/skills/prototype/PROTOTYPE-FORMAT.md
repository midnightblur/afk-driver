# PROTOTYPE.md format

`PROTOTYPE.md` is the settled record of a prototype run, in the spec folder of the ticket. Only the prototype skill writes `PROTOTYPE.md` and the `INDEX.md` Prototype row. Every other skill only reads them. `scripts/prototype_files.py settle` checks the file against this page and refuses `bad-prototype` with a list of `problems`.

The mockup sits in `prototype/` of the spec folder: 1 HTML file that holds every screen, each at its own `#/<screen>` route.

## Header

The title line `# Prototype — <ticket key>`, then 3 lines:

```markdown
> Frontend: <name>
> Fidelity: <mark>
> Date: <YYYY-MM-DD>
```

- `Frontend`: a name of the `frontends` list of the repository config.
- `Fidelity`: 1 mark of the table below.

| Mark | When | The line |
|------|------|----------|
| `live-verified` | the fidelity pass compared the mockup with screenshots of the live app | `> Fidelity: live-verified · screenshots: <file>, <file>`, each compared screenshot by its file name |
| `catalog` | the design catalog was the anchor, no app ran, and every card of the catalog is checked; `settle` refuses it on a catalog with an unchecked card | `> Fidelity: catalog` |
| `source-only` | no running app, and no catalog or a catalog with an unchecked card: the frontend source, or the catalog as a lead, was the anchor | `> Fidelity: source-only` |

The screenshots stay in the afkv2 data folder and are deleted at the end of the run. The names are the record of the comparison.

## Sections

The sections come in this order, each a `##` heading with the name in the first column.

| Section | Holds |
|---------|-------|
| `Screens` | the Screens table |
| `Coverage` | the Coverage table |
| `Fidelity` | the anchor used, what was compared, each difference left |
| `Decisions` | 1 line per screen or interaction decision, with why |
| `PRD gaps` | each point the PRD cannot answer, or `none` |

## Screens table

| Screen | Mockup | Entry point | Stories |
|--------|--------|-------------|---------|
| the screen name | the mockup file from the spec folder and the route of the screen, such as `prototype/orders.html#/detail` | where the user enters the screen | the story numbers, such as `1, 2` |

At least 1 row. The mockup file of each row exists in `prototype/`, and `prototype/` holds only 1 HTML file.

## Coverage table

| Story | Path | State |
|-------|------|-------|
| the story number of the PRD `## User Stories` list | the clicks from the entry screen | `reachable`, `gap` or `retired` |

1 row per story of the PRD: a top-level item of its `## User Stories` list, numbered by its own number, or a bullet item by its position from 1. No row for a story the PRD does not hold, except a `retired` row. A `gap` row logs a story the mockup cannot reach. A story that the PRD dropped keeps its row with the state `retired`; a story the PRD holds is never `retired`. Readers trace by the story number.

## Checks at settle

Settle checks every file in `prototype/` for `afkv2-runtime`, `network-call` and `page-leave`, and scans `PROTOTYPE.md` and every file in `prototype/` for secrets (`secrets`, with file, line and shape). A file over 2 MiB (2 097 152 bytes), past what the scan reads, refuses `bad-prototype`. Only after every check passes does settle set the `INDEX.md` Prototype row to `chosen <YYYY-MM-DD>`.
