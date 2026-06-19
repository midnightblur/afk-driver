---
name: draw-charts
description: Render-safe diagrams. Use when writing any Mermaid (or other) chart into a file or message — steers away from the few constructs that break renderers and render-checks before shipping.
---

# draw-charts

Charts that render the first time. Mermaid-first; grow as new gotchas surface.

## Always

- **Render-check before you ship.** Lint Mermaid with `mmdc -i d.mmd -o d.svg`
  (mermaid-cli) — a clean SVG means it renders. No mmdc → stay in the safe subset
  below.
- **Target the oldest renderer in play.** A VSCode preview extension lags GitHub;
  lowest-common-denominator syntax renders everywhere.

## Mermaid — what breaks rendering

- First line is the diagram type. Prefer `graph` over `flowchart` (older alias,
  same result).
- **ASCII labels only.** No emoji, no `# { } < >`, no `§ ≥ ≤ · → —` or circled
  digits — any one aborts the parse. Use words, `-`, `,`.
- Quote any label with spaces or punctuation: `N["src/app: build"]`. Parentheses
  must be quoted or dropped.
- Subgraphs use the bracket-title form `subgraph id [Plain Title]` — not
  `subgraph id["..."]` (needs Mermaid ≥8.6, which old previews lack).
- Never name a node `end` (reserved word). Keep edge labels `-->|text|` ASCII.
- **Label a dotted/thick edge with the pipe form `-.->|text|` / `==>|text|`, not
  the inline `-. text .->` / `== text ==>`.** A `.` in an inline dotted label (a
  filename like `PROTOTYPE.md`) collides with the `.->` terminator and aborts the
  parse (`Lexical error … Unrecognized text`); the pipe-delimited label tolerates
  periods.
- State machines: use `stateDiagram-v2` (v1 has no `note`).

## Where it renders

Mermaid only renders where a viewer supports it (GitHub/GitLab natively; VSCode
needs the `bierner.markdown-mermaid` extension). Writing to a terminal/chat
instead → draw ASCII boxes.

## Grow this

When a chart fails to render, append the trigger + the fix here as one line. This
file is the accumulated render-safe knowledge — keep it terse.
