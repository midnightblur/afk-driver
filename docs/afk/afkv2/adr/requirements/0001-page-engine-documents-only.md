# Agents write page documents, never page HTML

> Status: Accepted
> Audited: 2026-10-29
> Layer: Requirements
> Context ticket: GitHub #153

Every grill and design page comes from one page engine. The agent writes only a JSON page document, and the engine renders it. The documents use composable components, and a freestyle component holds any HTML or SVG that no component covers. Each freestyle use is marked, so a repeated use can become a component. Why: a hand-built page took one build script per round, and a slip in the HTML broke the page in front of the human. The owner asked for the speed of a data-only page with full HTML reach (GRILL-LOG V-1, V-2, V-3).

## Considered Options

- Agents write page HTML by hand. Rejected: slow, and every round risks a broken page.
- The v1 kit with its 6 fixed components. Rejected: too rigid for maps, simulated runs and module diagrams.
